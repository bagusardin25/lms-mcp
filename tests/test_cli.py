import base64
import time

import pytest

from lms_mcp import cli
from lms_mcp.auth import TokenError
from lms_mcp.config import Config, ConfigError, load_config
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
        soon = int(time.time()) + 3600
        self.responses = {
            "core_webservice_get_site_info": SITE_INFO,
            "core_course_get_enrolled_courses_by_timeline_classification": {
                "courses": [{"id": 7, "fullname": "Basis Data &amp; SQL"}]
            },
            "mod_assign_get_assignments": {"courses": []},
            "mod_quiz_get_quizzes_by_courses": {"quizzes": []},
            "core_calendar_get_action_events_by_timesort": {
                "events": [
                    {
                        "name": "Tugas 1 is due",
                        "activityname": "Tugas 1",
                        "timesort": soon,
                        "course": {"fullname": "Basis Data &amp; SQL"},
                        "action": {"actionable": True},
                    },
                    {"name": "Acara pribadi", "timesort": soon, "course": None},
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


def test_check_without_token_points_to_login(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_config", lambda: Config("https://x.test", None))

    assert cli.main(["check"]) == 1
    assert "lms-mcp login" in capsys.readouterr().err


TOKEN_PAGE = (
    "https://lms.contoh.test/admin/tool/mobile/launch.php?service=moodle_mobile_app"
    "&passport=1&urlscheme=moodlemobile&confirmed=1"
)
WS_TOKEN = "f" * 32
PRIVATE_TOKEN = "rahasia-untuk-masuk-situs"
LINK = "moodlemobile://token=" + base64.b64encode(
    f"{'a' * 32}:::{WS_TOKEN}:::{PRIVATE_TOKEN}".encode()
).decode()


def test_token_prints_token_page_of_configured_lms(monkeypatch, capsys):
    monkeypatch.setattr(cli, "read_settings", lambda: {"LMS_BASE_URL": "https://lms.contoh.test"})

    assert cli.main(["token"]) == 0

    output = capsys.readouterr().out
    assert TOKEN_PAGE in output
    assert "lms-mcp login" in output


@pytest.fixture
def login(monkeypatch, tmp_path):
    """Menjalankan lms-mcp login dengan tautan yang ditempel dan LMS tiruan."""
    token_path = tmp_path / "di-luar-proyek" / "token.txt"
    seen = {}

    class FakeLms:
        def __init__(self, base_url, token):
            seen["token"] = token

        def call(self, function):
            if seen.get("rejected"):
                raise MoodleError("invalidtoken", "Invalid token")
            return {"fullname": "Ani"}

    def run(pasted, settings=None, rejected=False):
        seen["rejected"] = rejected
        values = {
            "LMS_BASE_URL": "https://lms.contoh.test",
            "LMS_TOKEN_FILE": str(token_path),
            **(settings or {}),
        }
        monkeypatch.setattr(cli, "read_settings", lambda: values)
        monkeypatch.setattr(cli, "MoodleClient", FakeLms)

        def paste(prompt):
            if isinstance(pasted, BaseException):
                raise pasted
            return pasted

        monkeypatch.setattr(cli.getpass, "getpass", paste)
        return cli.main(["login"])

    run.token_path = token_path
    run.seen = seen
    return run


def test_login_saves_only_the_lms_key_outside_the_project(login, capsys):
    assert login(LINK) == 0

    output = capsys.readouterr().out
    assert TOKEN_PAGE in output
    assert "Terhubung sebagai Ani" in output
    assert str(login.token_path) in output
    # Bagian tautan untuk masuk ke situs LMS tidak ikut disimpan atau ditampilkan.
    assert login.token_path.read_text(encoding="utf-8").strip() == WS_TOKEN
    assert PRIVATE_TOKEN not in output
    assert WS_TOKEN not in output
    assert login.seen["token"] == WS_TOKEN


def test_login_result_is_read_back_by_the_server(login, monkeypatch, tmp_path):
    assert login(LINK) == 0
    env_path = tmp_path / ".env"
    env_path.write_text(f'LMS_TOKEN_FILE="{login.token_path.as_posix()}"', encoding="utf-8")
    monkeypatch.delenv("LMS_TOKEN", raising=False)

    assert load_config(env_path).token == WS_TOKEN


@pytest.mark.parametrize("pasted", ["", "bukan tautan", "moodlemobile://token=!!!"])
def test_login_rejects_unreadable_link_without_saving(login, capsys, pasted):
    assert login(pasted) == 1

    assert "tidak terbaca" in capsys.readouterr().err
    assert not login.token_path.exists()


def test_login_does_not_save_a_key_the_lms_rejects(login, capsys):
    assert login(LINK, rejected=True) == 1

    assert "invalidtoken" in capsys.readouterr().err
    assert not login.token_path.exists()


def test_login_can_be_cancelled(login, capsys):
    assert login(KeyboardInterrupt()) == 1

    assert "Dibatalkan" in capsys.readouterr().err
    assert not login.token_path.exists()


def test_login_warns_when_env_file_still_wins(login, capsys):
    assert login(LINK, settings={"LMS_TOKEN": "kunci-lama"}) == 0

    assert "LMS_TOKEN di file .env masih terisi" in capsys.readouterr().out


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
    assert "bisa_dikerjakan" in output
    assert "Lewat tenggat dan belum dikumpulkan: 0" in output
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


def test_invalid_token_points_to_login(capsys, fake_client):
    fake_client.responses["core_webservice_get_site_info"] = MoodleError(
        "invalidtoken", "Invalid token"
    )

    assert cli.main(["check"]) == 1
    assert "lms-mcp login" in capsys.readouterr().err


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
