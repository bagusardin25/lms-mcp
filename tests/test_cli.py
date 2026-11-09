import pytest

from lms_mcp import cli
from lms_mcp.auth import TokenError
from lms_mcp.config import Config, ConfigError
from lms_mcp.moodle import MoodleError

SITE_INFO = {
    "fullname": "Nama Mahasiswa",
    "userid": 42,
    "sitename": "LMS",
    "release": "4.5",
    "downloadfiles": 1,
    "uploadfiles": 0,
    "usermaxuploadfilesize": 104857600,
    "functions": [
        {"name": "core_course_get_contents", "version": "1"},
        {"name": "mod_assign_save_submission", "version": "1"},
    ],
}


class FakeClient:
    def __init__(self):
        self.responses = {
            "core_webservice_get_site_info": SITE_INFO,
            "core_course_get_enrolled_courses_by_timeline_classification": {
                "courses": [{"fullname": "Basis Data &amp; SQL"}]
            },
            "core_calendar_get_action_events_by_timesort": {
                "events": [
                    {
                        "name": "Tugas 1 is due",
                        "activityname": "Tugas 1",
                        "timesort": 1794000000,
                        "course": {"fullname": "Basis Data &amp; SQL"},
                    },
                    {"name": "Acara pribadi", "timesort": 1794000000, "course": None},
                ]
            },
        }

    def call(self, function, **params):
        response = self.responses[function]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(cli, "load_config", lambda: Config("https://x.test", "token"))
    monkeypatch.setattr(cli, "create_client", lambda config: client)
    return client


def test_check_without_token_points_to_env_file(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_config", lambda: Config("https://x.test", None))

    assert cli.main(["check"]) == 1
    assert ".env" in capsys.readouterr().err


def test_check_reports_broken_token(monkeypatch, capsys):
    def broken(config):
        raise TokenError("Isi LMS_TOKEN tidak terbaca.")

    monkeypatch.setattr(cli, "create_client", broken)

    assert cli.main(["check"]) == 1
    assert "tidak terbaca" in capsys.readouterr().err


def test_check_prints_summary(capsys, fake_client):
    assert cli.main(["check"]) == 0

    output = capsys.readouterr().out
    assert "Nama Mahasiswa (userid 42)" in output
    assert "Mata kuliah berjalan: 1" in output
    assert "Basis Data & SQL" in output
    assert "[Basis Data & SQL] Tugas 1" in output
    assert "WIB" in output
    assert "Acara pribadi" in output
    assert "[ada] core_course_get_contents" in output
    assert "[ - ] mod_quiz_get_quizzes_by_courses" in output
    assert "Unduh : ya" in output
    assert "Upload: tidak" in output
    assert "Batas ukuran upload: 100 MB" in output
    assert "[ada] mod_assign_save_submission" in output
    assert "[ - ] mod_assign_submit_for_grading" in output


@pytest.mark.parametrize(
    "size, expected",
    [(None, "tidak diketahui"), (-1, "tanpa batas"), (0, "0 MB"), (2097152, "2 MB")],
)
def test_format_upload_limit(size, expected):
    assert cli.format_upload_limit(size) == expected


def test_check_continues_after_one_step_fails(capsys, fake_client):
    fake_client.responses[
        "core_course_get_enrolled_courses_by_timeline_classification"
    ] = MoodleError("accessexception", "Ditolak")

    assert cli.main(["check"]) == 1

    output = capsys.readouterr().out
    assert "accessexception" in output
    assert "Deadline 14 hari ke depan: 2" in output


def test_invalid_token_points_to_env_file(capsys, fake_client):
    fake_client.responses["core_webservice_get_site_info"] = MoodleError(
        "invalidtoken", "Invalid token"
    )

    assert cli.main(["check"]) == 1
    assert ".env" in capsys.readouterr().err


def test_serve_starts_server(monkeypatch):
    started = []
    monkeypatch.setattr(cli, "run_server", lambda: started.append("stdio"))
    monkeypatch.setattr(cli, "run_http_server", lambda: started.append("http"))

    assert cli.main(["serve"]) == 0
    assert cli.main(["serve", "--http"]) == 0
    assert started == ["stdio", "http"]


def test_serve_http_reports_missing_config(monkeypatch, capsys):
    def missing():
        raise ConfigError("LMS_PUBLIC_URL belum diisi")

    monkeypatch.setattr(cli, "run_http_server", missing)

    assert cli.main(["serve", "--http"]) == 1
    assert "LMS_PUBLIC_URL" in capsys.readouterr().err
