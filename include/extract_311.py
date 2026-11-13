"""
Extract Calgary 311 services-and-requests in montly chunks as raw parquet files to be stored into an AWS S3 bucket.

1. Asks the API to count how many rows each month has.
2. For each month, fetches the rows page by page and writes it into raw/311/YYYY-MM.parquet.
3. Checks each month's fetched row count against the API count and logs the result.

Re-running is allowed, since the months that already match their expected count are cached and skipped.
The current month is always refetched because the data changes daily.

To use:
    from extract_311 import ServiceRequestExtractor
    ServiceRequestExtractor().run('2020-01')    # Runs a single month (for testing)
    ServiceRequestExtractor().run()             # Runs all months from 2012-01 to current month (the backfill)
    ServiceRequestExtractor.run_incremental()   # Rows changed since the last load (runs daily)
    ServiceRequestExtractor().upload_to_s3()    # copy raw files to S3 (needs boto3 and AWS keys)

For upload_to_s3: set S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_DEFAULT_REGION (see: .env.example)
"""

from __future__ import annotations

import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import polars as pl
from base_extractor import BaseExtractor


class ServiceRequestExtractor(BaseExtractor):
    DATASET_ID: str = "iahh-g8bj"  # This is a public id.
    PAGE_SIZE: int = 50_000  # Maximum allowed rows to extract per page.
    OVERLAP_DAYS: int = 3  # re-read this many days before the last load, since dates have no time of day.
    COLUMNS: tuple[str] = (
        "service_request_id",
        "requested_date",
        "updated_date",
        "closed_date",
        "status_description",
        "source",
        "service_name",
        "agency_responsible",
        "comm_code",
        "comm_name",
        "location_type",
        "longitude",
        "latitude",
    )
    # Consider putting this into init as a parameter.
    SERVICE_REQUEST_SCHEMA: ClassVar[dict[str, pl.DataType]] = {
        "service_request_id": pl.String,
        "requested_date": pl.String,
        "updated_date": pl.String,
        "closed_date": pl.String,
        "status_description": pl.String,
        "source": pl.String,
        "service_name": pl.String,
        "agency_responsible": pl.String,
        "comm_code": pl.String,
        "comm_name": pl.String,
        "location_type": pl.String,
        "longitude": pl.Float64,
        "latitude": pl.Float64,
    }
    MANIFEST_FIELDS: tuple[str] = ("month", "expected", "fetched", "status", "at")
    S3_PREFIX = "raw/311"

    def __init__(
        self, out_dir: str | Path = Path, app_token: str | None = None
    ) -> None:
        token = app_token or os.environ.get("SODA_APP_TOKEN")
        super().__init__(
            out_dir,
            f"https://data.calgary.ca/resource/{self.DATASET_ID}.json",
            {"X-App-Token"} if token else {},
        )

    # -------- API -----------------------------------------------------------

    def monthly_counts(self) -> dict[str, int]:
        """
        Return {'YYYY-MM': row_count} for every month, from one grouped query.
        """

        rows = self._get(
            {
                "$select": "date_trunc_ym(requested_date) as month, count(*) as n",
                "$group": "month",
                "$order": "month",
                "$limit": 5_000,
            }
        )
        counts = {}
        for row in rows:
            if "month" not in row:
                print(f"Warning: {row.get('n')} rows have no requested_date. Skipped.")
                continue
            counts[row["month"][:7]] = int(row["n"])
        return counts

    @staticmethod
    def month_bounds(month: str) -> tuple[str, str]:
        """
        First day of the month and of the next month, in the API's timestamp format.
        """
        year, mon = int(month[:4]), int(month[5:7])
        nxt = date(year + (mon == 12), mon % 12 + 1, 1)
        return f"{month}-01T00:00:00", f"{nxt:%Y-%m}-01T00:00:00"

    def _fetch_where(self, where: str) -> pl.DataFrame:
        """
        Page through every row that matches a $where filter.
        """
        rows, offset = [], 0
        while True:
            batch = self._get(
                {
                    "$select": ", ".join(self.COLUMNS),
                    "$where": where,
                    "$order": "service_request_id",
                    "$limit": self.PAGE_SIZE,
                    "$offset": offset,
                }
            )
            rows.extend(batch)
            if len(batch) < self.PAGE_SIZE:
                print(
                    f"Batch size is greater than the number of allowed extracted rows: {self.PAGE_SIZE}."
                )
                break
            offset += self.PAGE_SIZE
            time.sleep(self.PAUSE_SECONDS)
        df = pl.from_dicts(rows, schema=self.SERVICE_REQUEST_SCHEMA)
        df = df.with_columns(
            [
                pl.col("requested_date").str.to_datetime(
                    "%Y-%m-%dT%H:%M:%S%.3f", strict=False
                ),
                pl.col("updated_date").str.to_datetime(
                    "%Y-%m-%dT%H:%M:%S%.3f", strict=False
                ),
                pl.col("closed_date").str.to_datetime(
                    "%Y-%m-%dT%H:%M:%S%.3f", strict=False
                ),
            ]
        )
        return df.with_columns(
            pl.lit(datetime.now(UTC).isoformat()).alias("_ingested_at")
        )

    def fetch_month(self, month: str) -> pl.DataFrame:
        """
        Fetches the rows that match the month.
        """
        start, end = self.month_bounds(month)
        return self._fetch_where(
            f"requested_date >= '{start}' AND requested_date < '{end}'"
        )

    def _count_where(self, where: str) -> int:
        """
        How many rows the API says match a $where filter.
        """
        return int(self._get({"$select": "count(*) as n", "$where": where})[0]["n"])

    # ----- Storage ----------------------------------------------------

    def _path(self, month: str) -> Path:
        return self.out_dir / f"{month}.parquet"

    def _already_done(self, month: str, expected: int) -> bool:
        """
        Check whether the specified month was already extracted AND matches the expected number rows.
        """
        path = self._path(month)
        if (
            month == f"{date.today():%Y-%m}" or not path.exists()
        ):  # skip the months before current month.
            return False
        return pl.scan_parquet(path).select(pl.len()).collect().item() == expected

    # ---- run ------------------------------------------------------------

    def run(self, months: list[str] | None = None) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        counts = self.monthly_counts()
        print(f"{len(counts)} months, {sum(counts.values()):,} rows in total")
        for m, n in list(counts.items())[:3] + list(counts.items())[-3:]:
            print(f"    {m}: {n:,}")

        for month in months or list(counts):
            expected = counts.get(month)
            if expected is None:
                print(f"{month}: not in the API counts, skipping")
                continue
            if self._already_done(month, expected):
                print(f"{month}: already complete ({expected:,} rows)")
                continue
            df = self.fetch_month(month)
            df.write_parquet(self._path(month))
            status = "ok" if df.height == expected else "COUNT MISMATCH"
            print(f"{month}: fetched {df.height:,} of {expected:,} expected - {status}")
            self._append_manifest(
                {
                    "month": month,
                    "expected": expected,
                    "fetched": df.height,
                    "status": status,
                    "at": datetime.now(UTC).isoformat(),
                }
            )
            time.sleep(self.PAUSE_SECONDS)

    # ---- Incremental (daily run for data streaming) -----------------------------------------------

    def _since(self, overlap_days: int) -> str:
        """
        Latest updated_date already on disk, minus an overlap, as an API timestamp.
        """
        latest = (
            pl.scan_parquet(str(self.out_dir / "**" / "*.parquet"))
            .select(pl.col("updated_date").dt.date().max())
            .collect()
            .item()
        )
        if latest is None:
            raise RuntimeError("No raw data found. Run the monthly extract first")
        return f"{latest - timedelta(days=overlap_days):%Y-%m-%d}T00:00:00"

    @staticmethod
    def _changed_since(since: str) -> str:
        """
        Rows changed since a date: by updated_date, else closed_date, else requested_date
        """
        return (
            f"updated_date >= '{since}'"
            f" OR (updated_date IS NULL AND closed_date >= '{since}')"
            f" OR (updated_date IS NULL AND closed_date IS NULL AND requested_date >= '{since}')"
        )

    def run_incremental(
        self, overlap_days: int | None = None, strict: bool = False
    ) -> int:
        """
        Fetch rows changed since the last load and store them as one dated file.

        Files go to raw/311/incremental/YYYY-MM-DD.parquet. Running again on the same day overwrites that day's file.
        The same request can appear in several files, so when merging downstream keep the latest version of each
        service_request_id.
        With strict=True, a count mismatch raises after the file and manifest are written, so a scheduler will mark
        the run as failed and retries it.

        Returns the number of rows fetched.
        """
        since = self._since(self.OVERLAP_DAYS if overlap_days is None else overlap_days)
        where = self._changed_since(since)
        expected = self._count_where(where)
        df = self._fetch_where(where)

        label = f"{date.today():%Y-%m-%d}"
        path = self.out_dir / "incremental" / f"{label}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)

        status = "ok" if df.height == expected else "COUNT MISMATCH"
        print(
            f"incremental {label}: rows changed since {since[:10]}: "
            f"fetched {df.height:,} of {expected:,} expected - {status}"
        )
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._append_manifest(
            {
                "month": f"incremental:{label}",
                "expected": expected,
                "fetched": df.height,
                "status": status,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        if strict and status != "ok":
            raise RuntimeError(
                f"Incremental {label}: fetched {df.height:,} of {expected:,} rows"
            )
        return df.height
