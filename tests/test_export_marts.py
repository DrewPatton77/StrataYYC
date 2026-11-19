import export_marts
import pytest


class FakeAthena:
    def __init__(self, state="SUCCEEDED"):
        self.state = state

    def start_query_execution(self, QueryString, WorkGroup):
        self.sql = QueryString
        return {"QueryExecutionId": "q1"}

    def get_query_execution(self, QueryExecutionId):
        return {
            "QueryExecution": {
                "Status": {"State": self.state, "StateChangeReason": "boom"},
                "ResultConfiguration": {
                    "OutputLocation": "s3://results-bucket/athena/q1.csv"
                },
            }
        }


class FakeS3:
    def __init__(self, body):
        self.body = body
        self.copies = []

    def download_file(self, bucket, key, filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.body)

    def copy_object(self, **kwargs):
        self.copies.append(kwargs)


class FakeSession:
    def __init__(self, athena, s3):
        self.clients = {"athena": athena, "s3": s3}

    def client(self, name):
        return self.clients[name]


def test_export_writes_csv_and_copies_to_stable_s3_key(tmp_path):
    s3 = FakeS3("day,requests\n2026-11-01,10\n2026-11-02,12\n")
    session = FakeSession(FakeAthena(), s3)

    rows = export_marts.export_tables(
        ["fct_daily_requests"], tmp_path, "my-bucket", session=session, poll=0
    )

    assert rows == {"fct_daily_requests": 2}
    assert (tmp_path / "fct_daily_requests.csv").read_text().startswith("day,requests")
    assert not (tmp_path / "fct_daily_requests.csv.tmp").exists()
    assert s3.copies[0]["Key"] == "exports/fct_daily_requests.csv"


def test_empty_result_keeps_the_previous_export(tmp_path):
    old = tmp_path / "fct_daily_requests.csv"
    old.write_text("day,requests\n2026-11-01,10\n")
    session = FakeSession(FakeAthena(), FakeS3("day,requests\n"))

    with pytest.raises(RuntimeError, match="no rows"):
        export_marts.export_tables(
            ["fct_daily_requests"], tmp_path, "my-bucket", session=session, poll=0
        )

    assert old.read_text() == "day,requests\n2026-11-01,10\n"


def test_failed_query_raises(tmp_path):
    session = FakeSession(FakeAthena(state="FAILED"), FakeS3(""))

    with pytest.raises(RuntimeError, match="failed: boom"):
        export_marts.export_tables(
            ["fct_daily_requests"], tmp_path, "my-bucket", session=session, poll=0
        )
