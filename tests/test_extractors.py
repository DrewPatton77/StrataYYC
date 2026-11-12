from unittest.mock import MagicMock, patch

import pytest
import requests

# Adjust the import path to match your project structure
from include.extract_311 import ServiceRequestExtractor


@pytest.fixture
def extractor(tmp_path):
    """Creates a ServiceRequestExtractor instance using a temporary directory."""
    return ServiceRequestExtractor(out_dir=tmp_path, app_token="test-token-123")


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


@patch("extract_311.requests.get")
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


@patch("extract_311.time.sleep")
@patch("extract_311.requests.get")
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


@patch("extract_311.time.sleep")
@patch("extract_311.requests.get")
def test_get_exhausts_retries_and_raises_runtime_error(mock_get, mock_sleep, extractor):
    """Verifies RuntimeError is raised after MAX_RETRIES consecutive retryable failures."""
    mock_get.return_value = _mock_response(500, text="Internal Server Error")

    with pytest.raises(
        RuntimeError, match=f"Gave up after {extractor.MAX_RETRIES} attempts"
    ):
        extractor._get({"$limit": 50000})

    assert mock_get.call_count == extractor.MAX_RETRIES
    assert mock_sleep.call_count == extractor.MAX_RETRIES


@patch("extract_311.time.sleep")
@patch("extract_311.requests.get")
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
