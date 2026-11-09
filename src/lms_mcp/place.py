"""Mencari letak file di halaman mata kuliah.

Teks konfirmasi harus datang dari data LMS, bukan dari perkiraan AI. Nama bagian
dipakai apa adanya, misalnya "Minggu 3", karena itulah yang terlihat mahasiswa.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from .formatting import clean_text, format_time_text
from .moodle import MoodleClient, MoodleError

_COURSE_STATUS = {
    "inprogress": "sedang berjalan",
    "past": "sudah selesai",
    "future": "belum mulai",
}


def find_file_place(client: MoodleClient, file_url: str) -> dict[str, Any] | None:
    """Mencari file di mata kuliah berjalan, lalu yang selesai, lalu yang akan datang.

    Melempar MoodleError kalau URL-nya bukan file di LMS ini.
    """
    wanted = _file_key(client, file_url)
    if wanted is None:
        # _file_key menelan error URL isi mata kuliah. URL yang diminta AI tidak boleh
        # gagal diam-diam: host lain harus tetap ditolak.
        client.file_path(file_url)
        return None

    for status, label in _COURSE_STATUS.items():
        courses = client.call(
            "core_course_get_enrolled_courses_by_timeline_classification",
            classification=status,
        ).get("courses") or []
        for course in courses:
            try:
                sections = client.call("core_course_get_contents", courseid=course["id"])
            except MoodleError:
                continue
            place = _match(client, wanted, course, sections, label)
            if place is not None:
                return place
    return None


def _file_key(client: MoodleClient, url: str) -> str | None:
    try:
        return unquote(client.file_path(url))
    except MoodleError:
        return None


def _match(
    client: MoodleClient,
    wanted: str,
    course: dict[str, Any],
    sections: list[dict[str, Any]],
    course_status: str,
) -> dict[str, Any] | None:
    for section in sections or []:
        for module in section.get("modules") or []:
            for content in module.get("contents") or []:
                if content.get("type") == "url":
                    continue
                url = content.get("fileurl")
                if not url or _file_key(client, url) != wanted:
                    continue
                folder = (content.get("filepath") or "/").lstrip("/")
                place: dict[str, Any] = {
                    "course": clean_text(course.get("fullname")) or "Tanpa nama",
                    "course_status": course_status,
                    "section": clean_text(section.get("name")) or "Tanpa nama bagian",
                    "activity": clean_text(module.get("name")) or "Tanpa nama aktivitas",
                    "activity_url": module.get("url") or "",
                    "file_name": folder + (content.get("filename") or "file"),
                    "stored_outside_lms": bool(content.get("isexternalfile")),
                }
                if content.get("filesize"):
                    place["size_bytes"] = content["filesize"]
                modified = format_time_text(content.get("timemodified"))
                if modified:
                    place["modified"] = modified
                if not module.get("uservisible", True):
                    place["hidden"] = True
                return place
    return None
