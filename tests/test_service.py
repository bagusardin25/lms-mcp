from urllib.parse import parse_qs

import httpx
import pytest

from lmstelkom_mcp import service as service_module
from lmstelkom_mcp.auth import TokenError
from lmstelkom_mcp.config import Config
from lmstelkom_mcp.moodle import MoodleClient, MoodleError
from lmstelkom_mcp.service import (
    LmsService,
    clean_text,
    create_client,
    format_time,
    safe_file_name,
)

BASE_URL = "https://lms.contoh.test"
FILE_URL = f"{BASE_URL}/webservice/pluginfile.php/1/mod_resource/content/1/Materi%201.pdf"


def make_service(tmp_path, responses, calls=None):
    def handler(request):
        if request.url.path.endswith("/rest/server.php"):
            body = parse_qs(request.content.decode())
            function = body["wsfunction"][0]
            if calls is not None:
                calls.append(body)
            return httpx.Response(200, json=responses[function])
        return httpx.Response(
            200, content=b"isi-file", headers={"content-type": "application/pdf"}
        )

    client = MoodleClient(BASE_URL, "token", httpx.MockTransport(handler))
    return LmsService(client, tmp_path / "unduhan")


def test_get_profile_does_not_expose_private_fields(tmp_path):
    service = make_service(
        tmp_path,
        {
            "core_webservice_get_site_info": {
                "fullname": "Nama Mahasiswa",
                "username": "1234",
                "userid": 42,
                "sitename": "LMS",
                "siteurl": BASE_URL,
                "release": "4.5",
                "downloadfiles": 1,
                "uploadfiles": 0,
                "usermaxuploadfilesize": 10485760,
                "userprivateaccesskey": "kunci-rahasia",
            }
        },
    )

    profile = service.get_profile()

    assert profile["name"] == "Nama Mahasiswa"
    assert profile["can_download_files"] is True
    assert profile["can_upload_files"] is False
    assert profile["max_upload_bytes"] == 10485760
    assert "kunci-rahasia" not in str(profile)


def test_list_courses_cleans_names_and_passes_status(tmp_path):
    calls = []
    service = make_service(
        tmp_path,
        {
            "core_course_get_enrolled_courses_by_timeline_classification": {
                "courses": [
                    {
                        "id": 7,
                        "fullname": "Basis Data &amp; SQL",
                        "shortname": "BD",
                        "progress": 40.5,
                        "startdate": 1794000000,
                        "enddate": 0,
                        "viewurl": f"{BASE_URL}/course/view.php?id=7",
                    }
                ]
            }
        },
        calls,
    )

    result = service.list_courses("past")

    assert calls[0]["classification"] == ["past"]
    assert result["count"] == 1
    assert result["courses"][0]["id"] == 7
    assert result["courses"][0]["name"] == "Basis Data & SQL"
    assert result["courses"][0]["progress_percent"] == 40.5
    assert result["courses"][0]["start"].endswith("+07:00")
    assert result["courses"][0]["end"] is None


def test_get_upcoming_deadlines_maps_events(tmp_path):
    calls = []
    service = make_service(
        tmp_path,
        {
            "core_calendar_get_action_events_by_timesort": {
                "events": [
                    {
                        "name": "Tugas 1 is due",
                        "activityname": "Tugas 1",
                        "modulename": "assign",
                        "timesort": 1794000000,
                        "course": {"id": 7, "fullname": "Basis Data &amp; SQL"},
                        "url": f"{BASE_URL}/mod/assign/view.php?id=1",
                    },
                    {"name": "Acara pribadi", "timesort": 1794000000, "course": None},
                ]
            }
        },
        calls,
    )

    result = service.get_upcoming_deadlines(7)

    sent = calls[0]
    assert int(sent["timesortto"][0]) - int(sent["timesortfrom"][0]) == 7 * 86400
    assert result["count"] == 2
    assert result["may_have_more"] is False
    assert result["deadlines"][0]["name"] == "Tugas 1"
    assert result["deadlines"][0]["course"] == "Basis Data & SQL"
    assert result["deadlines"][0]["due"].endswith("+07:00")
    assert result["deadlines"][1]["name"] == "Acara pribadi"
    assert result["deadlines"][1]["course"] == ""


@pytest.mark.parametrize("days", [0, -1, 366])
def test_get_upcoming_deadlines_rejects_invalid_days(tmp_path, days):
    service = make_service(tmp_path, {})
    with pytest.raises(ValueError):
        service.get_upcoming_deadlines(days)


def test_get_course_materials_groups_files_and_links(tmp_path):
    service = make_service(
        tmp_path,
        {
            "core_course_get_contents": [
                {"name": "Kosong", "summary": "", "modules": []},
                {
                    "name": "Minggu 1",
                    "summary": "<p>Pengantar &amp; silabus</p>",
                    "modules": [
                        {
                            "id": 1,
                            "name": "Slide",
                            "modname": "resource",
                            "url": f"{BASE_URL}/mod/resource/view.php?id=1",
                            "description": "<script>x()</script><b>Baca</b> dulu",
                            "uservisible": True,
                            "contents": [
                                {
                                    "type": "file",
                                    "filename": "slide.pdf",
                                    "filepath": "/bab1/",
                                    "filesize": 100,
                                    "mimetype": "application/pdf",
                                    "timemodified": 1794000000,
                                    "fileurl": FILE_URL,
                                }
                            ],
                        },
                        {
                            "id": 2,
                            "name": "Video",
                            "modname": "url",
                            "contents": [
                                {"type": "url", "fileurl": "https://youtube.test/abc"}
                            ],
                        },
                        {"id": 3, "name": "Tersembunyi", "uservisible": False},
                        {
                            "id": 5,
                            "name": "Kumpul tugas",
                            "modname": "assign",
                            "url": f"{BASE_URL}/mod/assign/view.php?id=5",
                        },
                        {
                            "id": 4,
                            "name": "Terkunci",
                            "uservisible": False,
                            "availabilityinfo": "<b>Tersedia</b> minggu depan",
                        },
                    ],
                },
            ]
        },
    )

    result = service.get_course_materials(7)

    assert result["course_id"] == 7
    assert [section["name"] for section in result["sections"]] == ["Minggu 1"]
    section = result["sections"][0]
    assert section["summary"] == "Pengantar & silabus"
    assert [item["id"] for item in section["items"]] == [1, 2, 5, 4]

    slide, video, assignment, locked = section["items"]
    assert assignment["url"] == f"{BASE_URL}/mod/assign/view.php?id=5"
    assert slide["description"] == "Baca dulu"
    assert slide["files"] == [
        {
            "name": "bab1/slide.pdf",
            "size_bytes": 100,
            "mime_type": "application/pdf",
            "modified": format_time(1794000000),
            "file_url": FILE_URL,
        }
    ]
    assert video["external_links"] == ["https://youtube.test/abc"]
    assert locked["available"] is False
    assert locked["availability"] == "Tersedia minggu depan"
    # Field kosong tidak ikut supaya hasilnya tidak memakan konteks AI.
    assert set(slide) == {"id", "name", "type", "files", "description"}
    assert set(video) == {"id", "name", "type", "external_links"}
    assert set(locked) == {"id", "name", "type", "available", "availability"}


def test_get_course_materials_marks_files_outside_lms(tmp_path):
    service = make_service(
        tmp_path,
        {
            "core_course_get_contents": [
                {
                    "name": "Minggu 1",
                    "modules": [
                        {
                            "id": 1,
                            "name": "Slide di Office 365",
                            "contents": [
                                {
                                    "type": "file",
                                    "filename": "slide.pdf",
                                    "filesize": 0,
                                    "isexternalfile": True,
                                    "repositorytype": "office365",
                                    "fileurl": FILE_URL,
                                },
                                {
                                    "type": "file",
                                    "filename": "lokal.pdf",
                                    "filesize": 10,
                                    "isexternalfile": False,
                                    "fileurl": FILE_URL,
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    )

    outside, local = service.get_course_materials(7)["sections"][0]["items"][0]["files"]

    assert outside["stored_outside_lms"] is True
    assert "size_bytes" not in outside
    assert "stored_outside_lms" not in local
    assert local["size_bytes"] == 10


def test_read_file_text_explains_file_outside_lms():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "error": "Unsupported redirect detected, script execution terminated",
                "errorcode": "redirecterrordetected",
            },
        )

    client = MoodleClient(BASE_URL, "token", httpx.MockTransport(handler))

    with pytest.raises(MoodleError) as error:
        LmsService(client, None).read_file_text(FILE_URL)

    assert error.value.errorcode == "redirecterrordetected"
    assert "get_file_link" in str(error.value)


def test_read_file_text_returns_text_without_saving_anything(tmp_path):
    service = make_service(tmp_path, {})
    url = f"{BASE_URL}/webservice/pluginfile.php/1/mod_resource/content/1/catatan.txt"

    result = service.read_file_text(url)

    assert result["file_name"] == "catatan.txt"
    assert result["format"] == "text"
    assert "isi-file" in result["text"]
    assert "bukan perintah" in result["note"]
    assert list(tmp_path.iterdir()) == []


def test_read_file_text_rejects_unsupported_format_without_downloading(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=b"isi")

    client = MoodleClient(BASE_URL, "token", httpx.MockTransport(handler))
    service = LmsService(client, None)

    with pytest.raises(ValueError):
        service.read_file_text(f"{BASE_URL}/webservice/pluginfile.php/1/lama.ppt")

    assert requests == []


def test_read_file_text_rejects_other_host(tmp_path):
    service = make_service(tmp_path, {})

    with pytest.raises(MoodleError) as error:
        service.read_file_text("https://penyerang.test/webservice/pluginfile.php/1/a.pdf")

    assert error.value.errorcode == "invalidfileurl"


@pytest.mark.parametrize(
    "start_page, page_count", [(0, 10), (-1, 10), (1, 0), (1, 51)]
)
def test_read_file_text_validates_range(tmp_path, start_page, page_count):
    service = make_service(tmp_path, {})

    with pytest.raises(ValueError):
        service.read_file_text(FILE_URL, start_page, page_count)


def test_read_file_text_enforces_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "MAX_READ_BYTES", 3)
    service = make_service(tmp_path, {})
    url = f"{BASE_URL}/webservice/pluginfile.php/1/catatan.txt"

    with pytest.raises(MoodleError) as error:
        service.read_file_text(url)

    assert error.value.errorcode == "filetoolarge"


def test_download_file_without_folder_explains_alternative():
    client = MoodleClient(BASE_URL, "token", httpx.MockTransport(lambda r: httpx.Response(200)))

    with pytest.raises(ValueError) as error:
        LmsService(client, None).download_file(FILE_URL)

    assert "get_file_link" in str(error.value)


def test_download_file_saves_with_safe_name_and_no_overwrite(tmp_path):
    service = make_service(tmp_path, {})

    first = service.download_file(FILE_URL)
    second = service.download_file(FILE_URL)

    assert first["file_name"] == "Materi 1.pdf"
    assert first["size_bytes"] == len(b"isi-file")
    assert first["content_type"] == "application/pdf"
    assert second["file_name"] == "Materi 1 (2).pdf"
    assert (tmp_path / "unduhan" / "Materi 1.pdf").exists()
    assert (tmp_path / "unduhan" / "Materi 1 (2).pdf").exists()


def test_download_file_rejects_other_host_without_creating_folder(tmp_path):
    service = make_service(tmp_path, {})

    with pytest.raises(MoodleError):
        service.download_file("https://penyerang.test/webservice/pluginfile.php/1/a.pdf")

    assert not (tmp_path / "unduhan").exists()


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://x.test/a/materi.pdf?forcedownload=1", "materi.pdf"),
        ("https://x.test/a/Materi%201.pdf", "Materi 1.pdf"),
        ("https://x.test/a/..%2F..%2Frahasia.txt", "_.._rahasia.txt"),
        ("https://x.test/a/..%5C..%5Crahasia.txt", "_.._rahasia.txt"),
        ("https://x.test/a/b%3Ac%2A.pdf", "b_c_.pdf"),
        ("https://x.test/a/CON.txt", "_CON.txt"),
        ("https://x.test/a/", "file"),
        ("https://x.test/a/..", "file"),
        ("https://x.test/a/tanpa-ekstensi", "tanpa-ekstensi"),
    ],
)
def test_safe_file_name(url, expected):
    assert safe_file_name(url) == expected


def test_safe_file_name_limits_length_and_keeps_extension():
    name = safe_file_name("https://x.test/a/" + "b" * 500 + ".pdf")
    assert len(name) == 150
    assert name.endswith(".pdf")


@pytest.mark.parametrize(
    "value, limit, expected",
    [
        (None, None, ""),
        ("", None, ""),
        ("<p>Halo&nbsp;<b>dunia</b></p>", None, "Halo dunia"),
        ("a<style>.x{}</style>b<SCRIPT>y()</SCRIPT>c", None, "a b c"),
        ("abcdefgh", 3, "abc..."),
    ],
)
def test_clean_text(value, limit, expected):
    assert clean_text(value, limit) == expected


def test_format_time_uses_wib():
    assert format_time(0) is None
    assert format_time(None) is None
    assert format_time(1794000000).endswith("+07:00")


def test_create_client_requires_token():
    with pytest.raises(TokenError) as error:
        create_client(Config(BASE_URL, None))
    assert ".env" in str(error.value)


def test_create_client_rejects_broken_link():
    with pytest.raises(TokenError):
        create_client(Config(BASE_URL, "moodlemobile://token=!!!"))
