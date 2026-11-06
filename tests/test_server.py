import json

import anyio
import httpx
from mcp import Client

from lmstelkom_mcp.auth import TokenError
from lmstelkom_mcp.moodle import MoodleClient
from lmstelkom_mcp.server import build_server
from lmstelkom_mcp.service import LmsService

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


def with_client(get_service, action):
    async def run():
        async with Client(build_server(get_service)) as client:
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
        "get_file_link",
        "download_file",
    }
    for name, tool in tools.items():
        assert tool.description
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.read_only_hint is (name != "download_file")


def test_list_courses_schema_limits_status_values(tmp_path):
    result = with_client(lambda: working_service(tmp_path), lambda c: c.list_tools())
    tool = next(tool for tool in result.tools if tool.name == "list_courses")

    assert set(tool.input_schema["properties"]["status"]["enum"]) == {
        "inprogress",
        "past",
        "future",
        "all",
    }


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


def test_download_rejection_becomes_tool_error(tmp_path):
    result = with_client(
        lambda: working_service(tmp_path),
        lambda c: c.call_tool(
            "download_file",
            {"file_url": "https://penyerang.test/webservice/pluginfile.php/1/a.pdf"},
        ),
    )

    assert result.is_error is True
    assert "invalidfileurl" in result.content[0].text
