import csv
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
import requests

# Adjust the import path to match your project structure
from include.extract_311 import ServiceRequestExtractor


@pytest.fixture
def extractor(tmp_path):
    """Creates a ServiceRequestExtractor instance using a temporary directory."""
    return ServiceRequestExtractor(out_dir=tmp_path, app_token="test-token-123")


# ---- _get() method --------------------------------------------------


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


# ---- monthly_counts() method -----------------------------------------------


def test_monthly_counts_returns_formatted_dict(extractor):
    """Verifies valid API rows are parsed into a {'YYYY-MM': int} dictionary."""
    mock_rows = [
        {"month": "2020-01-01T00:00:00.000", "n": "150"},
        {"month": "2020-02-01T00:00:00.000", "n": "200"},
    ]

    with patch.object(extractor, "_get", return_value=mock_rows) as mock_get:
        result = extractor.monthly_counts()

    assert result == {"2020-01": 150, "2020-02": 200}
    mock_get.assert_called_once_with(
        {
            "$select": "date_trunc_ym(requested_date) as month, count(*) as n",
            "$group": "month",
            "$order": "month",
            "$limit": 5_000,
        }
    )


def test_monthly_counts_skips_missing_month_and_warns(extractor, capsys):
    """Verifies rows without a 'month' key are skipped and trigger a warning."""
    mock_rows = [
        {"n": "12"},
        {"month": "2020-03-01T00:00:00.000", "n": "345"},
    ]

    with patch.object(extractor, "_get", return_value=mock_rows):
        result = extractor.monthly_counts()

    captured = capsys.readouterr()
    assert result == {"2020-03": 345}
    assert "Warning: 12 rows have no requested_date. Skipped." in captured.out


def test_monthly_counts_empty_response(extractor):
    """Verifies an empty API response returns an empty dictionary."""
    with patch.object(extractor, "_get", return_value=[]):
        result = extractor.monthly_counts()

    assert result == {}


# ----- month_bounds() method -------------------------------------------------


@pytest.mark.parametrize(
    ("month", "expected_start", "expected_end"),
    [
        ("2020-01", "2020-01-01T00:00:00", "2020-02-01T00:00:00"),
        ("2020-02", "2020-02-01T00:00:00", "2020-03-01T00:00:00"),
        ("2020-11", "2020-11-01T00:00:00", "2020-12-01T00:00:00"),
    ],
)
def test_month_bounds_standard_months(month, expected_start, expected_end):
    """Verifies standard months return the 1st of the month and 1st of the next month."""
    start, end = ServiceRequestExtractor.month_bounds(month)
    assert start == expected_start
    assert end == expected_end


def test_month_bounds_december_rollover():
    """Verifies December rolls over cleanly to January of the following year."""
    start, end = ServiceRequestExtractor.month_bounds("2020-12")
    assert start == "2020-12-01T00:00:00"
    assert end == "2021-01-01T00:00:00"


def test_month_bounds_invalid_format_raises_value_error():
    """Verifies non-numeric month strings raise a ValueError."""
    with pytest.raises(ValueError):
        ServiceRequestExtractor.month_bounds("invalid")


# ----- _fetch_where() method ----------------------------------------------------


def _make_sample_row(req_id: str) -> dict[str, str | None]:
    """Helper to build a complete API row matching ServiceRequestExtractor.COLUMNS."""
    return {
        "service_request_id": req_id,
        "requested_date": "2020-01-01T00:00:00.000",
        "updated_date": "2020-01-14T00:00:00.000",
        "closed_date": None,
        "status_description": "Closed",
        "source": "Web",
        "service_name": "Parks - Wildlife Sightings",
        "agency_responsible": "CS - Calgary Parks",
        "comm_code": "WSP",
        "comm_name": "WEST SPRINGS",
        "location_type": "Community Centrepoint",
        "longitude": "-114.20616821197828",
        "latitude": "51.05971960915254",
    }


def test_fetch_where_single_page_parses_schema_and_dates(extractor):
    """Verifies a single batch is converted to a Polars DataFrame with parsed datetimes."""
    sample_rows = [_make_sample_row("20-00000001"), _make_sample_row("20-00000002")]

    with patch.object(extractor, "_get", return_value=sample_rows) as mock_get:
        df = extractor._fetch_where("requested_date >= '2020-01-01T00:00:00'")

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    assert df.schema["requested_date"] == pl.Datetime("ms")
    assert df.schema["updated_date"] == pl.Datetime("ms")
    assert df.schema["closed_date"] == pl.Datetime("ms")
    assert df["closed_date"].null_count() == 2
    assert "_ingested_at" in df.columns
    mock_get.assert_called_once()


def test_fetch_where_paginates_across_multiple_batches(extractor):
    """Verifies _fetch_where loops with increasing $offset until a partial page returns."""
    extractor.PAGE_SIZE = 2
    page_1 = [_make_sample_row("20-00000001"), _make_sample_row("20-00000002")]
    page_2 = [_make_sample_row("20-00000003")]

    with (
        patch.object(extractor, "_get", side_effect=[page_1, page_2]) as mock_get,
        patch("include.extract_311.time.sleep") as mock_sleep,
    ):
        df = extractor._fetch_where("1=1")

    assert len(df) == 3
    assert df["service_request_id"].to_list() == [
        "20-00000001",
        "20-00000002",
        "20-00000003",
    ]
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0][0][0]["$offset"] == 0
    assert mock_get.call_args_list[1][0][0]["$offset"] == 2
    mock_sleep.assert_called_once_with(extractor.PAUSE_SECONDS)


def test_fetch_where_empty_response_returns_empty_dataframe(extractor):
    """Verifies an empty API result returns a 0-row DataFrame with the expected columns."""
    with patch.object(extractor, "_get", return_value=[]):
        df = extractor._fetch_where("1=0")

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 0
    assert "_ingested_at" in df.columns
    assert "service_request_id" in df.columns


# --- fetch_month() method -------------------------------------------------------------


def test_fetch_month_builds_correct_where_clause(extractor):
    """Verifies fetch_month passes the expected timestamp range to _fetch_where."""
    expected_df = pl.DataFrame({"service_request_id": ["20-00000001"]})

    with patch.object(
        extractor, "_fetch_where", return_value=expected_df
    ) as mock_fetch:
        result = extractor.fetch_month("2020-12")

    assert result.equals(expected_df)
    mock_fetch.assert_called_once_with(
        "requested_date >= '2020-12-01T00:00:00' AND requested_date < '2021-01-01T00:00:00'"
    )


# ----- _path() method -------------------------------------


def test_path_returns_parquet_filepath(extractor, tmp_path):
    """Verifies _path builds the expected <out_dir>/<month>.parquet Path object."""
    extractor.out_dir = tmp_path
    assert extractor._path("2020-01") == tmp_path / "2020-01.parquet"


def test_already_done_returns_false_for_current_month(extractor, tmp_path):
    """Verifies _already_done always returns False for the current active month."""
    extractor.out_dir = tmp_path
    current_month = f"{date.today():%Y-%m}"
    file_path = tmp_path / f"{current_month}.parquet"

    # Even if a valid file with the exact expected row count exists, current month must re-run
    pl.DataFrame({"id": [1, 2, 3]}).write_parquet(file_path)

    assert extractor._already_done(current_month, expected=3) is False


def test_already_done_checks_parquet_row_count(extractor, tmp_path):
    """Verifies _already_done returns True only when a past month's row count matches expected."""
    extractor.out_dir = tmp_path
    file_path = tmp_path / "2020-01.parquet"
    pl.DataFrame({"id": [1, 2, 3]}).write_parquet(file_path)

    assert extractor._already_done("2020-01", expected=3) is True
    assert extractor._already_done("2020-01", expected=5) is False


# ----- _already_done() method ------------------------------


def test_already_done_returns_false_when_file_missing(extractor, tmp_path):
    """Verifies _already_done returns False if the Parquet file does not exist."""
    extractor.out_dir = tmp_path
    assert extractor._already_done("2020-01", expected=100) is False


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


# --- run() method ---------------------------------------------------------------------


def test_run_fetches_all_months_and_writes_parquet_and_manifest(extractor, tmp_path):
    """Verifies run() fetches all months when months=None, saves Parquet files, and logs 'ok'."""
    extractor.out_dir = tmp_path / "raw" / "311"
    extractor.manifest_path = extractor.out_dir / "_manifest.csv"

    sample_df = pl.DataFrame({"service_request_id": ["20-00000001", "20-00000002"]})

    with (
        patch.object(
            extractor, "monthly_counts", return_value={"2020-01": 2, "2020-02": 2}
        ),
        patch.object(extractor, "_already_done", return_value=False),
        patch.object(extractor, "fetch_month", return_value=sample_df) as mock_fetch,
        patch.object(extractor, "_append_manifest") as mock_manifest,
        patch("include.extract_311.time.sleep") as mock_sleep,
    ):
        extractor.run()

    assert extractor.out_dir.exists()
    assert (extractor.out_dir / "2020-01.parquet").exists()
    assert (extractor.out_dir / "2020-02.parquet").exists()
    assert mock_fetch.call_count == 2
    assert mock_manifest.call_count == 2
    assert mock_sleep.call_count == 2

    logged_row = mock_manifest.call_args_list[0][0][0]
    assert logged_row["month"] == "2020-01"
    assert logged_row["expected"] == 2
    assert logged_row["fetched"] == 2
    assert logged_row["status"] == "ok"
    assert "at" in logged_row


def test_run_skips_missing_and_already_done_months(extractor, tmp_path, capsys):
    """Verifies run() skips months missing from API counts or already marked complete."""
    extractor.out_dir = tmp_path

    with (
        patch.object(extractor, "monthly_counts", return_value={"2020-01": 10}),
        patch.object(extractor, "_already_done", return_value=True),
        patch.object(extractor, "fetch_month") as mock_fetch,
        patch.object(extractor, "_append_manifest") as mock_manifest,
    ):
        extractor.run(months=["1999-01", "2020-01"])

    captured = capsys.readouterr()
    assert "1999-01: not in the API counts, skipping" in captured.out
    assert "2020-01: already complete (10 rows)" in captured.out
    mock_fetch.assert_not_called()
    mock_manifest.assert_not_called()


def test_run_records_count_mismatch_when_fetched_differs_from_expected(
    extractor, tmp_path, capsys
):
    """Verifies run() logs 'COUNT MISMATCH' when fetched row count does not match expected."""
    extractor.out_dir = tmp_path

    # API expected 5 rows, but fetch_month only returned 1 row
    partial_df = pl.DataFrame({"service_request_id": ["20-00000001"]})

    with (
        patch.object(extractor, "monthly_counts", return_value={"2020-03": 5}),
        patch.object(extractor, "_already_done", return_value=False),
        patch.object(extractor, "fetch_month", return_value=partial_df),
        patch.object(extractor, "_append_manifest") as mock_manifest,
        patch("include.extract_311.time.sleep"),
    ):
        extractor.run(months=["2020-03"])

    captured = capsys.readouterr()
    assert "2020-03: fetched 1 of 5 expected - COUNT MISMATCH" in captured.out

    logged_row = mock_manifest.call_args[0][0]
    assert logged_row["status"] == "COUNT MISMATCH"
    assert logged_row["expected"] == 5
    assert logged_row["fetched"] == 1


# --- _count_where() method -------------------------------------
def test_count_where_returns_integer_count(extractor):
    """Verifies _count_where queries count(*) and casts the result to int."""
    with patch.object(extractor, "_get", return_value=[{"n": "42"}]) as mock_get:
        count = extractor._count_where("status_description = 'Open'")

    assert count == 42
    mock_get.assert_called_once_with(
        {"$select": "count(*) as n", "$where": "status_description = 'Open'"}
    )


# --- _since() method ------------------------------------------
def test_since_finds_latest_date_and_subtracts_overlap(extractor, tmp_path):
    """Verifies _since scans nested Parquet files, finds the max date, and subtracts overlap."""
    extractor.out_dir = tmp_path
    sub_dir = tmp_path / "incremental"
    sub_dir.mkdir(parents=True)

    # Write a monthly file and an incremental file with a newer updated_date
    pl.DataFrame(
        {"updated_date": [datetime(2026, 11, 1, 10, 0), datetime(2026, 11, 5, 14, 30)]}
    ).write_parquet(tmp_path / "2026-11.parquet")

    pl.DataFrame({"updated_date": [datetime(2026, 11, 10, 8, 15)]}).write_parquet(
        sub_dir / "2026-11-10.parquet"
    )

    result = extractor._since(overlap_days=3)
    assert result == "2026-11-07T00:00:00"


def test_since_raises_runtime_error_when_no_data_on_disk(extractor, tmp_path):
    """Verifies _since raises RuntimeError if Parquet files exist but contain only null dates."""
    extractor.out_dir = tmp_path
    pl.DataFrame(
        {"updated_date": pl.Series([None], dtype=pl.Datetime("ms"))}
    ).write_parquet(tmp_path / "empty.parquet")

    with pytest.raises(
        RuntimeError, match="No raw data found. Run the monthly extract first"
    ):
        extractor._since(overlap_days=3)


# ---- _changed_since() method -------------------------------------------------------


def test_changed_since_builds_fallback_soql_filter():
    """Verifies _changed_since builds the OR fallback chain across date columns."""
    query = ServiceRequestExtractor._changed_since("2026-11-07T00:00:00")
    assert "updated_date >= '2026-11-07T00:00:00'" in query
    assert "OR (updated_date IS NULL AND closed_date >= '2026-11-07T00:00:00')" in query
    assert (
        "OR (updated_date IS NULL AND closed_date IS NULL AND requested_date >= '2026-11-07T00:00:00')"
        in query
    )


# ---- run_incremental() method -----------------------------------------------------


def test_run_incremental_writes_dated_parquet_and_manifest(extractor, tmp_path):
    """Verifies run_incremental writes to incremental/YYYY-MM-DD.parquet and returns row count."""
    extractor.out_dir = tmp_path
    extractor.manifest_path = tmp_path / "_manifest.csv"

    sample_df = pl.DataFrame({"service_request_id": ["26-00000001", "26-00000002"]})
    today_label = f"{date.today():%Y-%m-%d}"

    with (
        patch.object(
            extractor, "_since", return_value="2026-11-07T00:00:00"
        ) as mock_since,
        patch.object(extractor, "_count_where", return_value=2),
        patch.object(extractor, "_fetch_where", return_value=sample_df),
        patch.object(extractor, "_append_manifest") as mock_manifest,
    ):
        fetched_count = extractor.run_incremental()

    assert fetched_count == 2
    mock_since.assert_called_once_with(extractor.OVERLAP_DAYS)

    expected_file = tmp_path / "incremental" / f"{today_label}.parquet"
    assert expected_file.exists()

    logged_row = mock_manifest.call_args[0][0]
    assert logged_row["month"] == f"incremental:{today_label}"
    assert logged_row["expected"] == 2
    assert logged_row["fetched"] == 2
    assert logged_row["status"] == "ok"


def test_run_incremental_strict_mode_raises_on_mismatch_after_writing(
    extractor, tmp_path
):
    """Verifies strict=True writes the file and manifest first, then raises RuntimeError on mismatch."""
    extractor.out_dir = tmp_path
    sample_df = pl.DataFrame({"service_request_id": ["26-00000001"]})
    today_label = f"{date.today():%Y-%m-%d}"

    with (
        patch.object(extractor, "_since", return_value="2026-11-07T00:00:00"),
        patch.object(extractor, "_count_where", return_value=5),
        patch.object(extractor, "_fetch_where", return_value=sample_df),
        patch.object(extractor, "_append_manifest") as mock_manifest,
        pytest.raises(RuntimeError, match=f"Incremental {today_label}"),
    ):
        extractor.run_incremental(overlap_days=5, strict=True)

    # Confirm the Parquet file and manifest were still written before raising
    assert (tmp_path / "incremental" / f"{today_label}.parquet").exists()
    assert mock_manifest.call_args[0][0]["status"] == "COUNT MISMATCH"
