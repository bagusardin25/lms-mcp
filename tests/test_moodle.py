import time
from urllib.parse import parse_qs

import httpx
import pytest

from lms_mcp.moodle import MoodleClient, MoodleError, run_parallel

BASE_URL = "https://lms.contoh.test"
TOKEN = "token-rahasia"
FILE_URL = f"{BASE_URL}/webservice/pluginfile.php/1/mod_resource/content/1/materi.pdf"
MAX_BYTES = 1024


def client_returning(response=None, on_request=None):
    def handler(request):
        if on_request:
            on_request(request)
        return response or httpx.Response(200, json={})

    return MoodleClient(BASE_URL, TOKEN, httpx.MockTransport(handler))


def test_call_sends_token_in_body_not_url():
    seen = {}

    def on_request(request):
        seen["url"] = str(request.url)
        seen["body"] = parse_qs(request.content.decode())

    client = client_returning(on_request=on_request)
    client.call("core_course_get_contents", courseid=7)

    assert TOKEN not in seen["url"]
    assert seen["url"].endswith("/webservice/rest/server.php")
    assert seen["body"]["wstoken"] == [TOKEN]
    assert seen["body"]["wsfunction"] == ["core_course_get_contents"]
    assert seen["body"]["moodlewsrestformat"] == ["json"]
    assert seen["body"]["courseid"] == ["7"]


def test_call_flattens_lists_and_dicts_for_moodle():
    seen = {}

    def on_request(request):
        seen["body"] = parse_qs(request.content.decode())

    client = client_returning(on_request=on_request)
    client.call("fungsi", courseids=[7, 8], plugindata={"files_filemanager": 77})

    assert seen["body"]["courseids[0]"] == ["7"]
    assert seen["body"]["courseids[1]"] == ["8"]
    assert seen["body"]["plugindata[files_filemanager]"] == ["77"]


def test_upload_draft_file_sends_token_in_body_and_returns_item_id():
    seen = {}

    def on_request(request):
        seen["url"] = str(request.url)
        seen["body"] = request.content

    client = client_returning(
        httpx.Response(200, json=[{"filename": "a.pdf", "itemid": 77}]), on_request
    )

    assert client.upload_draft_file("a.pdf", b"isi-file") == 77
    assert seen["url"].endswith("/webservice/upload.php")
    assert TOKEN not in seen["url"]
    assert TOKEN.encode() in seen["body"]
    assert b'filename="a.pdf"' in seen["body"]
    assert b"isi-file" in seen["body"]


@pytest.mark.parametrize(
    "payload, errorcode",
    [
        ({"exception": "x", "errorcode": "invalidtoken", "message": "Salah"}, "invalidtoken"),
        ([{"error": "Terlalu besar", "errortype": "fileoversized"}], "fileoversized"),
        ([], "uploadfailed"),
    ],
)
def test_upload_draft_file_reports_errors(payload, errorcode):
    client = client_returning(httpx.Response(200, json=payload))

    with pytest.raises(MoodleError) as error:
        client.upload_draft_file("a.pdf", b"isi")

    assert error.value.errorcode == errorcode


def flaky_client(failures):
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) <= failures:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, json={"ok": True})

    return MoodleClient(BASE_URL, TOKEN, httpx.MockTransport(handler)), requests


def test_read_call_retries_once_when_connection_drops():
    client, requests = flaky_client(failures=1)

    assert client.call("core_course_get_contents") == {"ok": True}
    assert len(requests) == 2


def test_read_call_gives_up_after_second_drop():
    client, requests = flaky_client(failures=2)

    with pytest.raises(httpx.RemoteProtocolError):
        client.call("core_course_get_contents")
    assert len(requests) == 2


@pytest.mark.parametrize(
    "function", ["mod_assign_save_submission", "mod_assign_submit_for_grading"]
)
def test_write_call_is_not_retried_when_connection_drops(function):
    client, requests = flaky_client(failures=1)

    with pytest.raises(httpx.RemoteProtocolError):
        client.call(function)
    assert len(requests) == 1


def test_call_returns_list_payload():
    client = client_returning(httpx.Response(200, json=[{"id": 1}]))
    assert client.call("fungsi") == [{"id": 1}]


def test_call_raises_on_moodle_exception_with_http_200():
    client = client_returning(
        httpx.Response(
            200,
            json={
                "exception": "moodle_exception",
                "errorcode": "accessexception",
                "message": "Ditolak",
            },
        )
    )
    with pytest.raises(MoodleError) as error:
        client.call("fungsi")
    assert error.value.errorcode == "accessexception"


@pytest.mark.parametrize(
    "errorcode, message",
    [
        ("invalidtoken", "Invalid token - token not found"),
        # Balasan Moodle untuk token yang baru saja kedaluwarsa.
        ("accessexception", "Access control exception"),
    ],
)
def test_token_errors_explain_what_to_do(errorcode, message):
    client = client_returning(
        httpx.Response(
            200,
            json={
                "exception": "moodle_exception",
                "errorcode": errorcode,
                "message": message,
            },
        )
    )
    with pytest.raises(MoodleError) as error:
        client.call("fungsi")
    assert error.value.errorcode == errorcode
    assert ".env" in str(error.value)


def test_call_raises_on_non_json_response():
    client = client_returning(httpx.Response(200, text="<html>Maintenance</html>"))
    with pytest.raises(MoodleError) as error:
        client.call("fungsi")
    assert error.value.errorcode == "invalidresponse"


def test_call_raises_on_http_error():
    client = client_returning(httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError) as error:
        client.call("fungsi")
    assert TOKEN not in str(error.value)


def test_download_saves_file_and_sends_token_in_body(tmp_path):
    seen = {}

    def on_request(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = parse_qs(request.content.decode())

    client = client_returning(
        httpx.Response(200, content=b"isi-pdf", headers={"content-type": "application/pdf"}),
        on_request,
    )
    destination = tmp_path / "materi.pdf"

    content_type = client.download(FILE_URL, destination, MAX_BYTES)

    assert destination.read_bytes() == b"isi-pdf"
    assert content_type == "application/pdf"
    assert seen["method"] == "POST"
    assert TOKEN not in seen["url"]
    assert seen["body"]["token"] == [TOKEN]
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize(
    "url",
    [
        "https://penyerang.test/webservice/pluginfile.php/1/a.pdf",
        "http://lms.contoh.test/webservice/pluginfile.php/1/a.pdf",
        "https://lms.contoh.test.penyerang.test/webservice/pluginfile.php/1/a.pdf",
        "https://user@lms.contoh.test/webservice/pluginfile.php/1/a.pdf",
        f"{BASE_URL}/login/index.php",
        f"{BASE_URL}/webservice/pluginfile.php/../../login/index.php",
        "file:///C:/Windows/win.ini",
        "bukan-url",
    ],
)
def test_download_rejects_url_before_sending_token(tmp_path, url):
    requests = []
    client = client_returning(on_request=requests.append)

    with pytest.raises(MoodleError) as error:
        client.download(url, tmp_path / "a.pdf", MAX_BYTES)

    assert error.value.errorcode == "invalidfileurl"
    assert requests == []
    assert list(tmp_path.iterdir()) == []


def test_file_path_converts_public_file_url():
    client = client_returning()
    assert (
        client.file_path(f"{BASE_URL}/pluginfile.php/1/a.pdf?token=lama")
        == "/webservice/pluginfile.php/1/a.pdf"
    )


def test_download_does_not_follow_redirect(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://penyerang.test/"})

    client = MoodleClient(BASE_URL, TOKEN, httpx.MockTransport(handler))

    with pytest.raises(MoodleError):
        client.download(FILE_URL, tmp_path / "a.pdf", MAX_BYTES)

    assert len(requests) == 1
    assert list(tmp_path.iterdir()) == []


def test_download_removes_partial_file_when_too_large(tmp_path):
    client = client_returning(httpx.Response(200, content=b"x" * (MAX_BYTES + 1)))

    with pytest.raises(MoodleError) as error:
        client.download(FILE_URL, tmp_path / "a.pdf", MAX_BYTES)

    assert error.value.errorcode == "filetoolarge"
    assert list(tmp_path.iterdir()) == []


def test_download_raises_when_lms_returns_json_error(tmp_path):
    client = client_returning(
        httpx.Response(200, json={"error": "Ditolak", "errorcode": "accessexception"})
    )

    with pytest.raises(MoodleError) as error:
        client.download(FILE_URL, tmp_path / "a.pdf", MAX_BYTES)

    assert error.value.errorcode == "accessexception"
    assert list(tmp_path.iterdir()) == []


def test_download_keeps_real_json_file(tmp_path):
    client = client_returning(httpx.Response(200, json={"soal": [1, 2]}))
    destination = tmp_path / "data.json"

    client.download(FILE_URL, destination, MAX_BYTES)

    assert destination.exists()


def test_run_parallel_keeps_input_order():
    def slow_double(value):
        # Yang selesai lebih dulu justru item terakhir, tetapi urutan hasil tidak berubah.
        time.sleep(0.01 * (5 - value))
        return value * 2

    assert run_parallel(slow_double, [1, 2, 3, 4]) == [2, 4, 6, 8]
    assert run_parallel(slow_double, []) == []
