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
