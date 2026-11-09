from test_service import BASE_URL, FILE_URL, make_service

from lms_mcp.moodle import MoodleError


def _courses(body):
    status = body["classification"][0]
    if status == "inprogress":
        return {"courses": [{"id": 7, "fullname": "Data Mining Advance"}]}
    if status == "past":
        return {"courses": [{"id": 8, "fullname": "Semester lalu"}]}
    return {"courses": []}


def _contents(body):
    if body["courseid"][0] != "7":
        return [
            {
                "name": "Minggu 1",
                "modules": [
                    {
                        "name": "Arsip",
                        "contents": [
                            {
                                "type": "file",
                                "filename": "lama.pdf",
                                "filepath": "/",
                                "fileurl": f"{BASE_URL}/webservice/pluginfile.php/9/lama.pdf",
                            }
                        ],
                    }
                ],
            }
        ]
    return [
        {
            "name": "<b>Minggu 3</b>",
            "modules": [
                {
                    "name": "Slide preprocessing",
                    "url": f"{BASE_URL}/mod/resource/view.php?id=1",
                    "contents": [
                        {"type": "url", "fileurl": "https://youtube.test/abc"},
                        {
                            "type": "file",
                            "filename": "slide.pdf",
                            "filepath": "/bab1/",
                            "filesize": 2048,
                            "timemodified": 1794000000,
                            "fileurl": FILE_URL,
                        },
                    ],
                }
            ],
        }
    ]


def test_locate_file_uses_the_course_page_not_the_model(tmp_path):
    service = make_service(
        tmp_path,
        {
            "core_course_get_enrolled_courses_by_timeline_classification": _courses,
            "core_course_get_contents": _contents,
        },
    )

    place, folder = service.locate_file(FILE_URL)

    assert place["course"] == "Data Mining Advance"
    assert place["course_status"] == "sedang berjalan"
    assert place["section"] == "Minggu 3"
    assert place["activity"] == "Slide preprocessing"
    assert place["file_name"] == "bab1/slide.pdf"
    assert place["size_bytes"] == 2048
    assert place["modified"] == "Sabtu, 7 November 2026 04.20 WIB"
    assert folder.endswith("unduhan")


def test_locate_file_can_find_a_past_course(tmp_path):
    old = f"{BASE_URL}/webservice/pluginfile.php/9/lama.pdf"
    service = make_service(
        tmp_path,
        {
            "core_course_get_enrolled_courses_by_timeline_classification": _courses,
            "core_course_get_contents": _contents,
        },
    )

    place, _folder = service.locate_file(old)

    assert place["course"] == "Semester lalu"
    assert place["course_status"] == "sudah selesai"
    assert place["file_name"] == "lama.pdf"


def test_executable_download_is_refused(tmp_path):
    exe = f"{BASE_URL}/webservice/pluginfile.php/1/slide.exe"
    service = make_service(
        tmp_path,
        {
            "core_course_get_enrolled_courses_by_timeline_classification": _courses,
            "core_course_get_contents": [
                {
                    "name": "Minggu 3",
                    "modules": [
                        {
                            "name": "Berkas",
                            "contents": [
                                {
                                    "type": "file",
                                    "filename": "slide.exe",
                                    "filepath": "/",
                                    "fileurl": exe,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )

    try:
        service.locate_file(exe)
    except ValueError as error:
        assert "bisa dijalankan" in str(error)
    else:
        raise AssertionError("file yang bisa dijalankan harus ditolak")


def test_locate_file_rejects_other_hosts_and_unknown_files(tmp_path):
    service = make_service(
        tmp_path,
        {
            "core_course_get_enrolled_courses_by_timeline_classification": _courses,
            "core_course_get_contents": _contents,
        },
    )

    try:
        service.locate_file("https://penyerang.test/webservice/pluginfile.php/1/a.pdf")
    except MoodleError as error:
        assert error.errorcode == "invalidfileurl"
    else:
        raise AssertionError("host lain harus ditolak")

    missing = f"{BASE_URL}/webservice/pluginfile.php/1/tidak-ada.pdf"
    try:
        service.locate_file(missing)
    except ValueError as error:
        assert "tidak ketemu" in str(error)
    else:
        raise AssertionError("file yang tidak ada harus ditolak")
