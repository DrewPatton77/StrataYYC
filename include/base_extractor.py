"""
Shared plumbing for the extractors: a retrying GET, the manifest, count checks, and S3 upload.

A subclass supplies what is different between the sources. For example, how to fetch one partition, the schema, the folder layout, and the incremental rule.
It sets MANIFEST_FIELDS and S3_prefix, and implements run() and run_incremental().
"""

from __future__ import annotations

import csv
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import requests


class BaseExtractor:
    PAUSE_SECONDS = 0.2
    MAX_RETRIES = 5
    TIMEOUT_SECONDS = 120
    RETRY_STATUSES = (429, 500, 502, 503, 504)
    MANIFEST_FIELDS = ("label", "expected", "fetched", "status", "at")
    S3_PREFIX = "raw"

    def __init__(
        self, out_dir: str | Path, base_url: str, headers: dict | None = None
    ) -> None:
        self.out_dir = Path(out_dir)
        self.manifest_path = self.out_dir / "_manifest.csv"
        self.base_url = base_url
        self.headers = headers or {}

    # --- API -------------------------------------------------------

    def _get(self, params: dict) -> dict | list:
        """
        HTTP GET, retries on rate limits and server errors. Prints the API's status description for status codes 4xx.
        """
        for attempt in range(self.MAX_RETRIES):
            r = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=self.TIMEOUT_SECONDS,
            )
            if r.status_code in self.RETRY_STATUSES:
                wait = 2**attempt
                print(f"    HTTP {r.status_code}, retrying in {wait}s")
                time.sleep(wait)
                continue
            if not r.ok:
                print(r.status_code, r.text)
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Gave up after {self.MAX_RETRIES} attempts: {params}")

    # --- Manifest ------------------------------------------------------

    def _append_manifest(self, row: dict) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        is_new = not self.manifest_path.exists()
        with self.manifest_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.MANIFEST_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    def _log(self, label: str, fetched: int, expected: int) -> str:
        """
        Print and record on load. Rows getched against the API's expected count.
        """
        status = "ok" if fetched == expected else "COUNT MISMATCH"
        print(f"{label}: fetched {fetched:,} of {expected:,} expected - {status}")
        self._append_manifest(
            {
                self.MANIFEST_FIELDS[0]: label,
                "expected": expected,
                "fetched": fetched,
                "status": status,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        return status

    # ---- to implement ----------------------------------------------------

    def run(self, *args, **kwargs) -> None:
        """
        Backfill every partition (month, year, ...)
        """
        raise NotImplementedError

    def run_incremental(self, *args, **kwargs) -> int:
        """
        Fetch what changed recently and store it as one dated file. Returns the rows fetched.
        """
        raise NotImplementedError

    # --- Cloud Storage: AWS S3 Bucket -------------------------------------

    def upload_to_s3(self, bucket: str | None = None, prefix: str | None = None) -> int:
        """
        Copy the raw files (and the manifest) to S3.

        A file is uploaded when it is NOT in the bucket yet or was written AFTER the copy's date.
        So, re-running only sends what is new or changed.

        Returns the number of files uploaded.
        """
        import boto3
        from botocore.exceptions import ClientError

        bucket = bucket or os.environ["S3_BUCKET"]
        prefix = prefix or self.S3_PREFIX
        s3 = boto3.client("s3")
        uploaded = 0
        for path in sorted(self.out_dir.rglob("*")):
            if not path.is_file():
                continue
            key = f"{prefix}/{path.relative_to(self.out_dir).as_posix()}"
            written = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            try:
                if s3.head_object(Bucket=bucket, Key=key)["LastModified"] >= written:
                    continue
            except ClientError as e:
                if e.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
                    raise
            s3.upload_file(str(path), bucket, key)
            uploaded += 1
        print(f"s3//{bucket}/{prefix}: uploaded {uploaded} file(s)")
        return uploaded
