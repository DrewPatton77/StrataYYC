"""
Extract daily weather for Calgary International Airport from the ECCC climate-daily API.

1. run(): for each year, fetches the daily rows and writes raw/weather/YYYY.parquet.
2. run_incremental(): refetches the last few days (recent days are often revised or filled in later)
   and writes raw/weather/incremental/YYYY-MM-DD.parquet.
3. Every fetch logs its row count against the API's own count in raw/weather/_manifest.csv.
4. upload_to_s3() (from BaseExtractor) copies the raw files to S3, like the 311 extractor.

Re-running is safe, since past years that already have a file are skipped. The current year is always refetched. The same data can appear in several files,
so downstream keeps the latest version of each local_date by _ingested_at.

Use:
    from extract_weather import CalgaryWeatherExtractor
    CalgaryWeatherExtractor().run(2012, 2012)   # one year, handy for a first test.
    CalgaryWeatherExtractor().run()             # 2012 to the current year.
    CalgaryWeatherExtractor().run_incremental() # the last 14 days (daily)
    CalgaryWeatherExtractor().upload_to_s3()    # needs S3_BUCKET and AWS keys
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import polars as pl
from base_extractor import BaseExtractor


class CalgaryWeatherExtractor(BaseExtractor):
    # Station constants: kept here and not in the data, because the station never changes.
    CLIMATE_IDENTIFIER = "3031092"
    STATION_NAME = "CALGARY INTL A"
    STN_ID = 50430
    PROVINCE_CODE = "AB"

    BASE_URL = "https://api.weather.gc.ca/collections/climate-daily/items"
    FIRST_YEAR = 2012
    PAGE_SIZE = 1_000
    DAYS_BACK = (
        14  # incremental window: recent days can be revised after the first publish
    )

    WEATHER_SCHEMA: ClassVar[dict[str, pl.DataType]] = {
        "LOCAL_DATE": pl.String,
        "MEAN_TEMPERATURE": pl.Float64,
        "MIN_TEMPERATURE": pl.Float64,
        "MAX_TEMPERATURE": pl.Float64,
        "TOTAL_PRECIPITATION": pl.Float64,
        "TOTAL_RAIN": pl.Float64,
        "TOTAL_SNOW": pl.Float64,
        "SNOW_ON_GROUND": pl.Float64,
        "DIRECTION_MAX_GUST": pl.Float64,
        "SPEED_MAX_GUST": pl.Float64,
        "COOLING_DEGREE_DAYS": pl.Float64,
        "HEATING_DEGREE_DAYS": pl.Float64,
        "MIN_REL_HUMIDITY": pl.Float64,
    }
    MANIFEST_FIELDS = ("range", "expected", "fetched", "status", "at")
    S3_PREFIX = "raw/weather"

    def __init__(self, out_dir: str | Path = "raw/weather") -> None:
        super().__init__(out_dir, self.BASE_URL)

    # ---- API ----------------------------------------------------

    def _fetch_range(self, start: date, end: date) -> tuple[pl.DataFrame, int]:
        """
        Return (rows from start to end inclusive, the API's count of matching rows).
        """
        params = {
            "CLIMATE_IDENTIFIER": self.CLIMATE_IDENTIFIER,
            # a full interval needs a time on BOTH ends
            "datetime": f"{start:%Y-%m-%d}T00:00:00Z/{end:%Y-%m-%d}T00:00:00Z",
            "sortby": "LOCAL_DATE",
            "f": "json",
            "limit": self.PAGE_SIZE,
        }
        rows: list[dict] = []
        expected = None
        offset = 0
        while True:
            page = self._get({**params, "offset": offset})
            features = page.get("features", [])
            if expected is None:
                expected = page.get("numberMatched")
            rows += [f["properties"] for f in features]
            if len(features) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE
            time.sleep(self.PAUSE_SECONDS)

        df = pl.from_dicts(rows, schema=self.WEATHER_SCHEMA)
        df = df.with_columns(
            pl.col("LOCAL_DATE")
            .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
            .dt.date(),
        )
        df = df.rename({c: c.lower() for c in df.columns})
        df = df.with_columns(
            pl.lit(datetime.now(UTC).isoformat()).alias("_ingested_at")
        )
        return df, (len(rows) if expected is None else expected)

    # --- run --------------------------------------------------------------------

    def run(self, start_year: int | None = None, end_year: int | None = None) -> None:
        """
        Fetch one file per year. Past years that already have a file are skipped.
        """
        self.out_dir.mkdir(parents=True, exist_ok=True)
        today = date.today()
        for year in range(start_year or self.FIRST_YEAR, (end_year or today.year) + 1):
            path = self.out_dir / f"{year}.parquet"
            if path.exists() and year < today.year:
                print(f"{year}: already have {path.name}, skipping")
                continue
            df, expected = self._fetch_range(
                date(year, 1, 1), min(date(year, 12, 31), today)
            )
            df.write_parquet(path)
            self._log(str(year), df.height, expected)
            time.sleep(self.PAUSE_SECONDS)

    def run_incremental(
        self, days_back: int | None = None, strict: bool = False
    ) -> int:
        """
        Refetch the last few days and store them as one dated file.

        Files go to raw/weather/incremental/YYYY-MM-DD.parquet. Running again on the same day overwrites that day's file.
        With strict=True a count mismatch raises after the file and manifest are written, so a scheduler marks the run
        failed and retries it.

        Returns the number of rows fetched.
        """
        today = date.today()
        start = today - timedelta(
            days=self.DAYS_BACK if days_back is None else days_back
        )
        df, expected = self._fetch_range(start, today)

        path = self.out_dir / "incremental" / f"{today:%Y-%m-%d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)

        label = f"incremental: {today:%Y-%m-%d}"
        if self._log(label, df.height, expected) != "ok" and strict:
            raise RuntimeError(f"{label}: fetched {df.height:,} of {expected:,} rows")
        return df.height
