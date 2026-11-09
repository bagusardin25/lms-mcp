from urllib.parse import parse_qs

import httpx
import pytest

from lms_mcp import service as service_module
from lms_mcp.auth import TokenError
from lms_mcp.config import Config
from lms_mcp.moodle import MoodleClient, MoodleError
from lms_mcp.service import (
    LmsService,
    clean_text,
    create_client,
    format_time,
    safe_file_name,
)

BASE_URL = "https://lms.contoh.test"
FILE_URL = f"{BASE_URL}/webservice/pluginfile.php/1/mod_resource/content/1/Materi%201.pdf"
# Sabtu, 7 November 2026 04.20 WIB
NOW = 1794000000
DAY = 86400


def make_service(tmp_path, responses, calls=None):
    """responses berisi balasan per fungsi, atau fungsi yang menerima isi permintaan."""

    def handler(request):
        if request.url.path.endswith("/rest/server.php"):
            body = parse_qs(request.content.decode())
            function = body["wsfunction"][0]
            if calls is not None:
                calls.append(body)
            response = responses[function]
            return httpx.Response(200, json=response(body) if callable(response) else response)
        return httpx.Response(
            200, content=b"isi-file", headers={"content-type": "application/pdf"}
        )

    client = MoodleClient(BASE_URL, "token", httpx.MockTransport(handler))
    return LmsService(client, tmp_path / "unduhan", clock=lambda: NOW)


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
                        "progress": 40.9,
                        "hasprogress": True,
                        "startdate": 1794000000,
                        "enddate": 0,
                        "viewurl": f"{BASE_URL}/course/view.php?id=7",
                    },
                    {
                        "id": 8,
                        "fullname": "Tanpa pelacakan",
                        "progress": 0,
                        "hasprogress": False,
                    },
                ]
            }
        },
        calls,
    )

    result = service.list_courses("past")

    assert calls[0]["classification"] == ["past"]
    assert result["count"] == 2
    assert result["courses"][0]["id"] == 7
    assert result["courses"][0]["name"] == "Basis Data & SQL"
    assert result["courses"][0]["progress_percent"] == 40
    # Progres 0 dari LMS di sini berarti tidak diukur, bukan belum ada yang selesai.
    assert result["courses"][1]["progress_percent"] is None
    assert result["courses"][0]["start"].endswith("+07:00")
    assert result["courses"][0]["end"] is None


COURSE = {
    "id": 7,
    "fullname": "Basis Data &amp; SQL",
    "startdate": NOW - 60 * DAY,
    "enddate": NOW + 60 * DAY,
}


def event(name, timesort, *, actionable=True, cmid=0, course=COURSE, **fields):
    return {
        "id": abs(hash(name)) % 100000,
        "name": f"{name} is due",
        "activityname": name,
        "modulename": "assign" if cmid else "quiz",
        "eventtype": "due" if cmid else "close",
        "instance": cmid,
        "timesort": timesort,
        "course": course,
        "action": {"name": "Add submission", "actionable": actionable},
        "url": f"{BASE_URL}/mod/assign/view.php?id={cmid}",
        **fields,
    }


def assign_info(assignment_id, cmid, opens=0, due=0, cutoff=0, drafts=0, name=""):
    return {
        "id": assignment_id,
        "cmid": cmid,
        "course": 7,
        "name": name or f"Tugas {assignment_id}",
        "allowsubmissionsfromdate": opens,
        "duedate": due,
        "cutoffdate": cutoff,
        "submissiondrafts": drafts,
    }


def submission(status, canedit=True):
    return {
        "lastattempt": {
            "submissionsenabled": True,
            "canedit": canedit,
            "submission": {"status": status},
        }
    }


def deadline_service(tmp_path, window, *, later=(), assignments=(), statuses=None,
                     quizzes=(), attempts=None, calls=None):  # fmt: skip
    def calendar(body):
        return {"events": list(window if "timesortto" in body else later), "lastid": 1}

    return make_service(
        tmp_path,
        {
            "core_calendar_get_action_events_by_timesort": calendar,
            "core_course_get_enrolled_courses_by_timeline_classification": {
                "courses": [COURSE]
            },
            "mod_assign_get_assignments": {
                "courses": [{"id": 7, "assignments": list(assignments)}]
            },
            "mod_assign_get_submission_status": lambda body: (statuses or {})[
                int(body["assignid"][0])
            ],
            "mod_quiz_get_quizzes_by_courses": {"quizzes": list(quizzes)},
            "mod_quiz_get_user_attempts": lambda body: {
                "attempts": (attempts or {})[int(body["quizid"][0])]
            },
        },
        calls,
    )


def test_get_upcoming_deadlines_separates_upcoming_and_overdue(tmp_path):
    window = [
        event("Terlambat masih bisa", NOW - 5 * DAY, cmid=501),
        event("Terlambat ditutup", NOW - 3 * DAY, cmid=502, actionable=False),
        # Sisa salinan semester lalu: tenggatnya jauh sebelum mata kuliah dimulai.
        event("Tugas tahun lalu", NOW - 100 * DAY, cmid=503),
        event(
            "Mata kuliah selesai",
            NOW - 2 * DAY,
            cmid=504,
            course={**COURSE, "id": 8, "enddate": NOW - DAY},
        ),
        event("Kuis 1", NOW + 2 * 3600),
        event("Belum dibuka", NOW + 3 * DAY, cmid=505, actionable=False),
        event("Kuis 2", NOW + 4 * DAY, eventtype="open", actionable=False),
    ]
    later = [event("Tugas besar", NOW + 40 * DAY, cmid=506, actionable=False)]
    calls = []
    service = deadline_service(
        tmp_path,
        window,
        later=later,
        assignments=[
            assign_info(11, 501, due=NOW - 5 * DAY),
            assign_info(12, 502, due=NOW - 3 * DAY, cutoff=NOW - DAY),
            assign_info(15, 505, opens=NOW + DAY, due=NOW + 3 * DAY),
            assign_info(16, 506, opens=NOW + 37 * DAY, due=NOW + 40 * DAY),
        ],
        calls=calls,
    )

    result = service.get_upcoming_deadlines(7)

    sent = calls[0]
    assert sent["limittononsuspendedevents"] == ["1"]
    assert format_time(int(sent["timesortto"][0])) == "2026-11-14T23:59:59+07:00"
    assert result["now_text"] == "Sabtu, 7 November 2026 04.20 WIB"
    assert result["period_end"] == "2026-11-14T23:59:59+07:00"

    assert [item["name"] for item in result["upcoming"]] == ["Kuis 1", "Belum dibuka", "Kuis 2"]
    quiz, not_open, quiz_opens = result["upcoming"]
    assert quiz["status"] == "bisa_dikerjakan"
    assert quiz["event"] == "ditutup"
    assert quiz["time_left"] == "2 jam lagi"
    assert quiz["course"] == "Basis Data & SQL"
    assert "assignment_id" not in quiz
    assert not_open["status"] == "belum_dibuka"
    assert not_open["opens"] == format_time(NOW + DAY)
    assert not_open["assignment_id"] == 15
    # Event dibuka bukan tenggat, jadi tanggalnya tidak disebut due.
    assert quiz_opens["event"] == "dibuka"
    assert quiz_opens["status"] == "belum_dibuka"
    assert "due" not in quiz_opens

    assert [item["name"] for item in result["overdue"]] == [
        "Terlambat masih bisa",
        "Terlambat ditutup",
    ]
    still_open, closed = result["overdue"]
    assert still_open["status"] == "terlambat_masih_bisa"
    assert still_open["assignment_id"] == 11
    assert still_open["time_left"] == "lewat 5 hari"
    assert still_open["date_text"] == "Senin, 2 November 2026 04.20 WIB"
    assert "closes" not in still_open
    assert "submission_status" not in still_open
    assert closed["status"] == "terlambat_ditutup"
    assert closed["closes"] == format_time(NOW - DAY)

    assert result["skipped_old_count"] == 2
    assert result["next_after_period"]["name"] == "Tugas besar"
    assert result["next_after_period"]["status"] == "belum_dibuka"
    assert result["may_have_more"] is False


def test_get_upcoming_deadlines_marks_drafts_that_were_never_sent(tmp_path):
    service = deadline_service(
        tmp_path,
        [
            event("Draft tertahan", NOW + DAY, cmid=501),
            event("Draft ditutup", NOW - DAY, cmid=502, actionable=False),
        ],
        assignments=[
            assign_info(11, 501, due=NOW + DAY, drafts=1),
            assign_info(12, 502, due=NOW - DAY, drafts=1),
        ],
        statuses={11: submission("draft")},
    )

    result = service.get_upcoming_deadlines(7)

    assert result["upcoming"][0]["submission_status"] == "draft"
    # Tugas yang sudah ditutup tidak perlu dicek lagi.
    assert "submission_status" not in result["overdue"][0]


def test_get_upcoming_deadlines_finds_activities_missing_from_calendar(tmp_path):
    service = deadline_service(
        tmp_path,
        [],
        assignments=[
            # Tidak ada di kalender karena sudah ditandai selesai, padahal belum dikumpulkan.
            assign_info(21, 601, due=NOW + 2 * DAY, name="Ditandai selesai"),
            assign_info(22, 602, due=NOW + 2 * DAY, name="Sudah dikumpulkan"),
            assign_info(23, 603, due=NOW + 30 * DAY, name="Di luar periode"),
        ],
        statuses={21: submission("new"), 22: submission("submitted")},
        quizzes=[
            {"id": 31, "coursemodule": 701, "course": 7, "name": "Kuis dibuka saja",
             "timeopen": NOW - DAY, "timeclose": NOW + DAY},
            {"id": 32, "coursemodule": 702, "course": 7, "name": "Kuis selesai",
             "timeopen": NOW - DAY, "timeclose": NOW + DAY},
            {"id": 33, "coursemodule": 703, "course": 7, "name": "Kuis setengah jalan",
             "timeopen": NOW - DAY, "timeclose": NOW + 3 * DAY},
        ],  # fmt: skip
        attempts={31: [], 32: [{"state": "finished"}], 33: [{"state": "inprogress"}]},
    )

    upcoming = service.get_upcoming_deadlines(7)["upcoming"]

    assert [item["name"] for item in upcoming] == [
        "Kuis dibuka saja",
        "Ditandai selesai",
        "Kuis setengah jalan",
    ]
    quiz, assignment, unfinished = upcoming
    assert quiz["status"] == "bisa_dikerjakan"
    assert "kalender" in quiz["note"]
    assert quiz["url"] == f"{BASE_URL}/mod/quiz/view.php?id=701"
    assert assignment["assignment_id"] == 21
    assert assignment["submission_status"] == "belum_dikumpulkan"
    assert assignment["status"] == "bisa_dikerjakan"
    assert assignment["course"] == "Basis Data & SQL"
    assert unfinished["quiz_status"] == "percobaan_belum_selesai"


def test_get_upcoming_deadlines_reads_every_page(tmp_path):
    first = [event(f"Tugas {i}", NOW + i * 60, cmid=600 + i) for i in range(50)]
    second = [event("Tugas akhir", NOW + DAY, cmid=700)]

    def calendar(body):
        if "timesortto" not in body:
            return {"events": []}
        if body.get("aftereventid") == ["99"]:
            return {"events": second, "lastid": 100}
        return {"events": first, "lastid": 99}

    service = make_service(
        tmp_path,
        {
            "core_calendar_get_action_events_by_timesort": calendar,
            "core_course_get_enrolled_courses_by_timeline_classification": {"courses": []},
            "mod_assign_get_assignments": {"courses": []},
        },
    )

    result = service.get_upcoming_deadlines(7)

    assert result["upcoming_count"] == 51
    assert result["upcoming"][-1]["name"] == "Tugas akhir"
    assert result["may_have_more"] is False
    assert result["next_after_period"] is None


def test_get_upcoming_deadlines_survives_failed_lookups(tmp_path):
    denied = {"exception": "moodle_exception", "errorcode": "nopermissions", "message": "x"}
    service = make_service(
        tmp_path,
        {
            "core_calendar_get_action_events_by_timesort": {
                "events": [event("Tugas 1", NOW + DAY, cmid=501, actionable=False)]
            },
            "core_course_get_enrolled_courses_by_timeline_classification": denied,
            "mod_assign_get_assignments": denied,
        },
    )

    item = service.get_upcoming_deadlines(7)["upcoming"][0]

    assert item["status"] == "belum_bisa_dikerjakan"
    assert "assignment_id" not in item


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
                            "instance": 11,
                            "url": f"{BASE_URL}/mod/assign/view.php?id=5",
                            "dates": [
                                {"label": "Opened:", "timestamp": NOW - DAY},
                                {"label": "Due:", "timestamp": NOW + DAY},
                            ],
                            "completiondata": {"state": 0, "hascompletion": True},
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

    assert result["now_text"] == "Sabtu, 7 November 2026 04.20 WIB"
    slide, video, assignment, locked = section["items"]
    assert assignment["url"] == f"{BASE_URL}/mod/assign/view.php?id=5"
    # Id modul (5) berbeda dengan id tugas (11) yang dipakai get_assignment.
    assert assignment["assignment_id"] == 11
    assert assignment["dates"] == [
        {"label": "Opened", "time": format_time(NOW - DAY)},
        {"label": "Due", "time": format_time(NOW + DAY)},
    ]
    assert assignment["completion"] == "belum"
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
