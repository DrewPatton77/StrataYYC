"""
Unit tests for the shared plumbing in BaseExtractor. No network, no AWS.
"""

import csv
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests
from botocore.exceptions import ClientError

from include.base_extractor import BaseExtractor


@pytest.fixture
def extractor(tmp_path):
    return BaseExtractor(
        tmp_path, "https://example.test/api", {"X-App-Token": "test-token-123"}
    )


# ---- _get() method ------------------------------------------


def _mock_response(status_code: int, json_data=None, text: str = "") -> MagicMock:
    """Helper to build a mock requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.ok = 200 <= status_code < 300
    mock_resp.text = text
    mock_resp.json.return_value = json_data if json_data is not None else []

    if not mock_resp.ok:
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            f"HTTP {status_code} Error", response=mock_resp
        )
    else:
        mock_resp.raise_for_status.return_value = None

    return mock_resp


@patch("base_extractor.requests.get")
def test_get_success(mock_get, extractor):
    """Verifies a standard 200 OK response returns parsed JSON with proper headers."""
    expected_data = [{"service_request_id": "24-00123456"}]
    mock_get.return_value = _mock_response(200, json_data=expected_data)

    params = {"$limit": 10}
    result = extractor._get(params)

    assert result == expected_data
    mock_get.assert_called_once_with(
        extractor.base_url,
        params=params,
        headers={"X-App-Token": "test-token-123"},
        timeout=extractor.TIMEOUT_SECONDS,
    )


@patch("base_extractor.time.sleep")
@patch("base_extractor.requests.get")
def test_get_retries_on_transient_errors_then_succeeds(mock_get, mock_sleep, extractor):
    """Verifies exponential backoff on retryable status codes (e.g., 429, 503) before succeeding."""
    expected_data = [{"service_request_id": "24-00999999"}]
    mock_get.side_effect = [
        _mock_response(429, text="Too Many Requests"),
        _mock_response(503, text="Service Unavailable"),
        _mock_response(200, json_data=expected_data),
    ]

    result = extractor._get({"$offset": 0})

    assert result == expected_data
    assert mock_get.call_count == 3
    # Verify exponential backoff wait times: 2^0 = 1s, 2^1 = 2s
    assert mock_sleep.call_args_list[0][0] == (1,)
    assert mock_sleep.call_args_list[1][0] == (2,)


@patch("base_extractor.time.sleep")
@patch("base_extractor.requests.get")
def test_get_exhausts_retries_and_raises_runtime_error(mock_get, mock_sleep, extractor):
    """Verifies RuntimeError is raised after MAX_RETRIES consecutive retryable failures."""
    mock_get.return_value = _mock_response(500, text="Internal Server Error")

    with pytest.raises(
        RuntimeError, match=f"Gave up after {extractor.MAX_RETRIES} attempts"
    ):
        extractor._get({"$limit": 50000})

    assert mock_get.call_count == extractor.MAX_RETRIES
    assert mock_sleep.call_count == extractor.MAX_RETRIES


@patch("base_extractor.time.sleep")
@patch("base_extractor.requests.get")
def test_get_raises_immediately_on_non_retryable_client_error(
    mock_get, mock_sleep, extractor, capsys
):
    """Verifies non-retryable 4xx errors (like 400 or 404) fail fast without retrying and log output."""
    mock_get.return_value = _mock_response(400, text="Malformed SoQL query")

    with pytest.raises(requests.HTTPError):
        extractor._get({"$where": "bad syntax"})

    # Should fail on the very first try without sleeping
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()

    # Verify it printed the status code and error text as documented
    captured = capsys.readouterr()
    assert "400 Malformed SoQL query" in captured.out


# ----- _append_manifest() method --------------------------


def test_append_manifest_creates_header_and_appends_rows(extractor, tmp_path):
    """Verifies _append_manifest writes headers once and appends subsequent rows cleanly."""
    extractor.manifest_path = tmp_path / "_manifest.csv"

    # Build two valid rows matching whatever keys are defined in extractor.MANIFEST_FIELDS
    row_1 = {field: f"val1_{field}" for field in extractor.MANIFEST_FIELDS}
    row_2 = {field: f"val2_{field}" for field in extractor.MANIFEST_FIELDS}

    extractor._append_manifest(row_1)
    extractor._append_manifest(row_2)

    with extractor.manifest_path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0] == row_1
    assert rows[1] == row_2


# --- upload_to_s3() method ---------------------------------------


def _make_client_error(code: str) -> ClientError:
    """Helper to construct a botocore ClientError with a specific error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": "Mocked S3 error"}},
        "HeadObject",
    )


def test_upload_to_s3_uploads_new_files_preserving_folder_layout(
    extractor, tmp_path, monkeypatch
):
    """Verifies files missing in S3 (404) are uploaded with nested paths preserved."""
    extractor.out_dir = tmp_path
    monkeypatch.setenv("S3_BUCKET", "test-calgary-bucket")

    # Create a root file and a nested incremental file
    root_file = tmp_path / "2020-01.parquet"
    root_file.write_bytes(b"parquet-data")

    inc_dir = tmp_path / "incremental"
    inc_dir.mkdir()
    inc_file = inc_dir / "2026-11-12.parquet"
    inc_file.write_bytes(b"inc-data")

    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = _make_client_error("404")

    with patch("boto3.client", return_value=mock_s3) as mock_boto_client:
        uploaded = extractor.upload_to_s3()

    assert uploaded == 2
    mock_boto_client.assert_called_once_with("s3")
    assert mock_s3.upload_file.call_count == 2
    mock_s3.upload_file.assert_any_call(
        str(root_file), "test-calgary-bucket", "raw/2020-01.parquet"
    )
    mock_s3.upload_file.assert_any_call(
        str(inc_file),
        "test-calgary-bucket",
        "raw/incremental/2026-11-12.parquet",
    )


def test_upload_to_s3_skips_unchanged_and_uploads_newer_files(extractor, tmp_path):
    """Verifies files older than S3 LastModified are skipped, while newer files are uploaded."""
    extractor.out_dir = tmp_path

    unchanged_file = tmp_path / "old.parquet"
    unchanged_file.write_bytes(b"old")

    modified_file = tmp_path / "new.parquet"
    modified_file.write_bytes(b"new")

    now = datetime.now(UTC)
    future_s3_time = now + timedelta(hours=1)
    past_s3_time = now - timedelta(hours=1)

    def head_object_side_effect(Bucket, Key):
        if Key.endswith("old.parquet"):
            return {"LastModified": future_s3_time}
        return {"LastModified": past_s3_time}

    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = head_object_side_effect

    with patch("boto3.client", return_value=mock_s3):
        uploaded = extractor.upload_to_s3(
            bucket="explicit-bucket", prefix="custom/prefix"
        )

    assert uploaded == 1
    mock_s3.upload_file.assert_called_once_with(
        str(modified_file), "explicit-bucket", "custom/prefix/new.parquet"
    )


def test_upload_to_s3_reraises_non_404_client_errors(extractor, tmp_path):
    """Verifies permission or server errors (like 403 AccessDenied) are raised immediately."""
    extractor.out_dir = tmp_path
    (tmp_path / "2020-01.parquet").write_bytes(b"data")

    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = _make_client_error("403")

    with (
        patch("boto3.client", return_value=mock_s3),
        pytest.raises(ClientError),
    ):
        extractor.upload_to_s3(bucket="test-bucket")

    mock_s3.upload_file.assert_not_called()


def test_upload_to_s3_raises_key_error_when_bucket_missing(
    extractor, tmp_path, monkeypatch
):
    """Verifies missing bucket argument and unset S3_BUCKET env var raises KeyError."""
    extractor.out_dir = tmp_path
    monkeypatch.delenv("S3_BUCKET", raising=False)

    with pytest.raises(KeyError):
        extractor.upload_to_s3()


# ---- _log() method --------------------------------------------------


def test_log_flags_a_count_mismatch(extractor, tmp_path):
    assert extractor._log("2020-01", 10, 10) == "ok"
    assert extractor._log("2020-02", 9, 10) == "COUNT MISMATCH"
    with (tmp_path / "_manifest.csv").open() as f:
        assert [r["status"] for r in csv.DictReader(f)] == ["ok", "COUNT MISMATCH"]
