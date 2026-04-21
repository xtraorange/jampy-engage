import csv
import os

from src.db import DatabaseExecutor


class DummyClient:
    def __init__(self):
        self.queries = []

    def query(self, sql, return_type=None, run_async=True):
        class Job:
            def __init__(self, sql):
                self._sql = sql

            def result(self):
                return [("a@x.com",)]

        self.queries.append(sql)
        return Job(sql)

    def close(self):
        pass


def test_executor(monkeypatch, tmp_path):
    # patch jampy_db.create to return dummy client
    import jampy_db

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "general.yaml").write_text("db_environment: oracle\n", encoding="utf-8")

    monkeypatch.setattr(jampy_db, "create", lambda profile, **props: DummyClient())
    execu = DatabaseExecutor("dummy")
    rows = execu.run_query("select 1")
    assert rows == [("a@x.com",)]
    out_file = tmp_path / "temp.csv"
    execu.write_csv(rows, None, str(out_file))
    with open(out_file, newline="", encoding="utf-8") as f:
        written_rows = list(csv.reader(f))
    assert written_rows[0] == ["ObjectId"]
    assert written_rows[1] == ["a@x.com"]
    assert execu.client.queries
    execu.close()


def test_username_domain(tmp_path, monkeypatch):
    # patch executor to simulate returning rows/dicts
    from src.generate_reports import process_group
    class DummyExec:
        def __init__(self):
            pass
        def run_query(self, q):
            return [{"USERNAME": "bob"}, ("alice",)]
        def write_csv(self, rows, headers, out):
            # rows should be collapsed single-item tuples containing email
            assert rows == [("bob@fastenal.com",), ("alice@fastenal.com",)]
    tracker = type("T", (), {"update": lambda self,h,m:None, "increment": lambda self,h:None})()
    cfg = {"output_dir": str(tmp_path)}
    gfolder = tmp_path / "g"
    gfolder.mkdir()
    # create minimal group config
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump({"handle": "g", "display_name": "G"}, f)
    with open(gfolder / "query.sql", "w") as f:
        f.write("select")
    from src.group import Group
    group = Group(str(gfolder))
    execu = DummyExec()
    # provide dummy job numbering but they are unused in this unit test
    process_group(group, cfg, execu, tracker, should_email=False, job_num=1, job_total=1)


def test_process_group_sanitizes_output_filename(tmp_path):
    from src.generate_reports import process_group
    from src.group import Group

    class DummyExec:
        def run_query(self, q):
            return [{"USERNAME": "bob"}]

        def write_csv(self, rows, headers, out):
            filename = os.path.basename(out)
            assert "/" not in filename
            assert "\\" not in filename
            assert ":" not in filename
            assert "?" not in filename
            assert "*" not in filename
            assert '"' not in filename
            assert "<" not in filename
            assert ">" not in filename
            assert "|" not in filename

    tracker = type("T", (), {"update": lambda self, h, m: None, "increment": lambda self, h: None})()
    cfg = {"output_dir": str(tmp_path)}

    gfolder = tmp_path / "gslash"
    gfolder.mkdir()
    with open(gfolder / "group.yaml", "w") as f:
        import yaml

        yaml.safe_dump({"handle": "us_south_gms_mms_viva_engage", "display_name": "US South GMs/MMs"}, f)
    with open(gfolder / "query.sql", "w") as f:
        f.write("select")

    group = Group(str(gfolder))
    execu = DummyExec()
    csv_path = process_group(group, cfg, execu, tracker, should_email=False, job_num=1, job_total=1)
    assert csv_path
