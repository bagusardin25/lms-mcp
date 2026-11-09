import base64
import json

import anyio
import httpx
from fake_moodle import ASSIGNMENT_ID, COURSE_ID, FakeMoodle
from mcp import Client
from test_service import FILE_URL, make_service

from lms_mcp.auth import TokenError
from lms_mcp.confirm import Confirmation
from lms_mcp.moodle import MoodleClient
from lms_mcp.server import build_server, embedded_icons
from lms_mcp.service import LmsService

BASE_URL = "https://lms.contoh.test"
SITE_INFO = {
    "fullname": "Nama Mahasiswa",
    "username": "1234",
    "userid": 42,
    "sitename": "LMS",
    "siteurl": BASE_URL,
    "release": "4.5",
}


def working_service(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=SITE_INFO))
    client = MoodleClient(BASE_URL, "token", transport)
    return LmsService(client, tmp_path)


def with_client(get_service, action, **server_options):
    async def run():
        async with Client(build_server(get_service, **server_options)) as client:
            return await action(client)

    return anyio.run(run)


def test_all_tools_are_registered_with_safe_annotations(tmp_path):
    result = with_client(lambda: working_service(tmp_path), lambda c: c.list_tools())
    tools = {tool.name: tool for tool in result.tools}

    assert set(tools) == {
        "get_profile",
        "list_courses",
        "get_upcoming_deadlines",
        "get_course_materials",
        "read_file_text",
        "list_assignments",
        "get_assignment",
        "get_file_link",
        "download_file",
    }
    for name, tool in tools.items():
        assert tool.description
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.read_only_hint is (name != "download_file")


def test_local_write_tools_are_off_by_default_and_marked_when_on(tmp_path):
    async def tool_map(**options):
        server = build_server(lambda: working_service(tmp_path), **options)
        async with Client(server) as client:
            return {tool.name: tool for tool in (await client.list_tools()).tools}

    default_tools = anyio.run(tool_map)
    assert "save_assignment_file" not in default_tools
    assert "submit_assignment" not in default_tools

    tools = anyio.run(lambda: tool_map(enable_write=True))
    assert tools["save_assignment_file"].annotations.destructive_hint is True
    assert tools["submit_assignment"].annotations.destructive_hint is True
    assert "create_upload_link" not in tools
    assert "allow_immediate" not in tools["save_assignment_file"].input_schema["properties"]
    assert "statement_accepted" not in tools["submit_assignment"].input_schema["properties"]
    assert set(tools["save_assignment_file"].input_schema["properties"]) == {
        "course_id",
        "assignment_id",
        "file_path",
    }


def test_list_courses_schema_limits_status_values(tmp_path):
    result = with_client(lambda: working_service(tmp_path), lambda c: c.list_tools())
    tool = next(tool for tool in result.tools if tool.name == "list_courses")

    assert set(tool.input_schema["properties"]["status"]["enum"]) == {
        "inprogress",
        "past",
        "future",
        "all",
    }


def test_local_server_embeds_icon_without_public_address(tmp_path):
    async def run():
        server = build_server(lambda: working_service(tmp_path), icons=embedded_icons())
        async with Client(server) as client:
            return client.server_info.icons

    icons = anyio.run(run)

    assert icons[0].mime_type == "image/png"
    prefix, data = icons[0].src.split(",", 1)
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(data).startswith(b"\x89PNG")


def test_call_tool_returns_data(tmp_path):
    result = with_client(
        lambda: working_service(tmp_path), lambda c: c.call_tool("get_profile", {})
    )

    assert result.is_error is False
    assert result.structured_content is None
    assert json.loads(result.content[0].text)["name"] == "Nama Mahasiswa"
    assert ": " not in result.content[0].text


def test_missing_token_becomes_readable_tool_error():
    def no_token():
        raise TokenError("Belum ada token. Isi LMS_TOKEN di file .env, lihat README.")

    result = with_client(no_token, lambda c: c.call_tool("get_profile", {}))

    assert result.is_error is True
    assert ".env" in result.content[0].text


def test_invalid_days_becomes_readable_tool_error(tmp_path):
    result = with_client(
        lambda: working_service(tmp_path),
        lambda c: c.call_tool("get_upcoming_deadlines", {"days": 0}),
    )

    assert result.is_error is True
    assert "days harus" in result.content[0].text


def test_download_rejection_becomes_tool_error(tmp_path, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("konfirmasi tidak boleh muncul untuk URL yang ditolak")

    monkeypatch.setattr("lms_mcp.server.ask_user", explode)
    result = with_client(
        lambda: working_service(tmp_path),
        lambda c: c.call_tool(
            "download_file",
            {"file_url": "https://penyerang.test/webservice/pluginfile.php/1/a.pdf"},
        ),
    )

    assert result.is_error is True
    assert "invalidfileurl" in result.content[0].text


def _course_file(status="inprogress"):
    def courses(body):
        if body["classification"][0] == status:
            return {"courses": [{"id": 7, "fullname": "Data Mining Advance"}]}
        return {"courses": []}

    return {
        "core_course_get_enrolled_courses_by_timeline_classification": courses,
        "core_course_get_contents": [
            {
                "name": "Minggu 3",
                "modules": [
                    {
                        "id": 1,
                        "name": "Slide preprocessing",
                        "modname": "resource",
                        "url": "https://lms.contoh.test/mod/resource/view.php?id=1",
                        "uservisible": True,
                        "contents": [
                            {
                                "type": "file",
                                "filename": "slide.pdf",
                                "filepath": "/bab1/",
                                "filesize": 2048,
                                "timemodified": 1794000000,
                                "fileurl": FILE_URL,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_download_shows_the_course_page_and_saves_nothing_when_cancelled(tmp_path, monkeypatch):
    pages = []

    def capture(page, **_kwargs):
        pages.append(page)
        return Confirmation("cancel")

    monkeypatch.setattr("lms_mcp.server.ask_user", capture)
    result = with_client(
        lambda: make_service(tmp_path, _course_file()),
        lambda c: c.call_tool("download_file", {"file_url": FILE_URL}),
    )

    assert result.is_error is True
    assert "membatalkan" in result.content[0].text
    assert "Data Mining Advance" in pages[0]
    assert "Minggu 3" in pages[0]
    assert "Slide preprocessing" in pages[0]
    assert "bab1/slide.pdf" in pages[0]
    assert not (tmp_path / "unduhan").exists()
    log = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert '"action": "download_file"' in log
    assert '"outcome": "dibatalkan"' in log
    assert "slide.pdf" in log
    assert "moodlemobile" not in log


def test_executable_download_never_opens_a_page(tmp_path, monkeypatch):
    html_url = FILE_URL.replace("Materi%201.pdf", "halaman.html")

    def explode(*_args, **_kwargs):
        raise AssertionError("halaman konfirmasi tidak boleh terbuka")

    monkeypatch.setattr("lms_mcp.server.ask_user", explode)
    result = with_client(
        lambda: make_service(
            tmp_path,
            {
                "core_course_get_enrolled_courses_by_timeline_classification": lambda body: (
                    {"courses": [{"id": 7, "fullname": "Data Mining Advance"}]}
                    if body["classification"][0] == "inprogress"
                    else {"courses": []}
                ),
                "core_course_get_contents": [
                    {
                        "name": "Minggu 3",
                        "modules": [
                            {
                                "name": "Halaman",
                                "contents": [
                                    {
                                        "type": "file",
                                        "filename": "halaman.html",
                                        "filepath": "/",
                                        "fileurl": html_url,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ),
        lambda c: c.call_tool("download_file", {"file_url": html_url}),
    )

    assert result.is_error is True
    assert "bisa dijalankan" in result.content[0].text
    assert not (tmp_path / "unduhan").exists()


def test_download_saves_only_after_the_user_allows(tmp_path, monkeypatch):
    monkeypatch.setattr("lms_mcp.server.ask_user", lambda *_args, **_kwargs: Confirmation("allow"))
    result = with_client(
        lambda: make_service(tmp_path, _course_file()),
        lambda c: c.call_tool("download_file", {"file_url": FILE_URL}),
    )

    saved = json.loads(result.content[0].text)
    assert result.is_error is False
    assert saved["course"] == "Data Mining Advance"
    assert saved["section"] == "Minggu 3"
    assert saved["activity"] == "Slide preprocessing"
    assert saved["confirmation"].startswith("Disetujui pengguna")
    assert list((tmp_path / "unduhan").iterdir())


def test_unknown_file_is_not_downloaded_and_does_not_ask(tmp_path, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("file yang tidak ketemu tidak perlu dikonfirmasi")

    monkeypatch.setattr("lms_mcp.server.ask_user", explode)
    responses = _course_file()
    responses["core_course_get_contents"] = [{"name": "Minggu 3", "modules": []}]
    result = with_client(
        lambda: make_service(tmp_path, responses),
        lambda c: c.call_tool("download_file", {"file_url": FILE_URL}),
    )

    assert result.is_error is True
    assert "tidak ketemu" in result.content[0].text
    assert not (tmp_path / "unduhan").exists()


def test_save_shows_assignment_page_and_uploads_nothing_when_cancelled(tmp_path, monkeypatch):
    report = tmp_path / "laporan.pdf"
    report.write_bytes(b"isi")
    pages = []

    def capture(page, **_kwargs):
        pages.append(page)
        return Confirmation("cancel")

    monkeypatch.setattr("lms_mcp.server.ask_user", capture)
    moodle = FakeMoodle()
    service = LmsService(moodle.client(), tmp_path / "unduhan", [tmp_path])
    result = with_client(
        lambda: service,
        lambda c: c.call_tool(
            "save_assignment_file",
            {"course_id": COURSE_ID, "assignment_id": ASSIGNMENT_ID, "file_path": str(report)},
        ),
        enable_write=True,
    )

    assert result.is_error is True
    assert "membatalkan" in result.content[0].text
    assert "Data Mining Advance" in pages[0]
    assert "Minggu 3" in pages[0]
    assert "Tugas &amp; Latihan" in pages[0]
    assert "langsung terkumpul" in pages[0]
    assert "laporan.pdf" in pages[0]
    assert moodle.uploads == []


def test_save_uploads_only_after_the_page_checkbox(tmp_path, monkeypatch):
    report = tmp_path / "laporan.pdf"
    report.write_bytes(b"isi")
    moodle = FakeMoodle()
    service = LmsService(moodle.client(), tmp_path / "unduhan", [tmp_path])

    def call(answer):
        monkeypatch.setattr("lms_mcp.server.ask_user", lambda *_a, **_k: answer)
        return with_client(
            lambda: service,
            lambda c: c.call_tool(
                "save_assignment_file",
                {
                    "course_id": COURSE_ID,
                    "assignment_id": ASSIGNMENT_ID,
                    "file_path": str(report),
                },
            ),
            enable_write=True,
        )

    refused = call(Confirmation("allow"))
    assert refused.is_error is True
    assert moodle.uploads == []

    saved = call(Confirmation("allow", {"confirm_immediate": "yes"}))
    assert saved.is_error is False
    assert moodle.uploads == ["laporan.pdf"]
    assert "Disetujui pengguna" in saved.content[0].text


def test_submit_waits_for_the_user_and_the_statement(tmp_path, monkeypatch):
    moodle = FakeMoodle(drafts=True, statement="Ini karya saya sendiri")
    moodle.status = "draft"
    service = LmsService(moodle.client(), tmp_path / "unduhan", [tmp_path])
    pages = []

    def capture(page, **_kwargs):
        pages.append(page)
        return Confirmation("cancel")

    monkeypatch.setattr("lms_mcp.server.ask_user", capture)
    cancelled = with_client(
        lambda: service,
        lambda c: c.call_tool(
            "submit_assignment",
            {"course_id": COURSE_ID, "assignment_id": ASSIGNMENT_ID},
        ),
        enable_write=True,
    )

    assert cancelled.is_error is True
    assert "Data Mining Advance" in pages[0]
    assert "Minggu 3" in pages[0]
    assert "Ini karya saya sendiri" in pages[0]
    assert moodle.status == "draft"

    monkeypatch.setattr("lms_mcp.server.ask_user", lambda *_a, **_k: Confirmation("allow"))
    missing = with_client(
        lambda: service,
        lambda c: c.call_tool(
            "submit_assignment",
            {"course_id": COURSE_ID, "assignment_id": ASSIGNMENT_ID},
        ),
        enable_write=True,
    )
    assert missing.is_error is True
    assert moodle.status == "draft"

    monkeypatch.setattr(
        "lms_mcp.server.ask_user",
        lambda *_a, **_k: Confirmation("allow", {"accept_statement": "yes"}),
    )
    sent = with_client(
        lambda: service,
        lambda c: c.call_tool(
            "submit_assignment",
            {"course_id": COURSE_ID, "assignment_id": ASSIGNMENT_ID},
        ),
        enable_write=True,
    )
    assert sent.is_error is False
    assert moodle.status == "submitted"
