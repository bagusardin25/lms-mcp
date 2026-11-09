"""Tenggat dari kalender LMS, termasuk yang sudah lewat tetapi belum selesai.

Kalender Moodle hanya memuat aktivitas yang masih perlu dikerjakan: tugas yang sudah
dikumpulkan dan kuis yang sudah dikerjakan hilang dengan sendirinya. Tugas yang lewat
tenggat tetapi belum ditutup masih bisa dikumpulkan, jadi ikut ditampilkan.

Ada tiga hal yang membuat kalender saja belum cukup akurat:
- Mata kuliah sering disalin dari semester lalu, sehingga ada tugas lama yang belum
  ditutup. Tugas seperti ini disaring supaya tidak terbaca sebagai tugas terlambat.
- Kalender menyembunyikan aktivitas yang sudah ditandai selesai (activity completion),
  misalnya kuis yang selesai cukup dengan dibuka, walaupun belum dikerjakan. Tugas dan
  kuis dalam periode yang tidak ada di kalender karena itu dicek langsung.
- Kalender tidak membedakan tugas yang belum diunggah dengan draft yang belum dikirim.
"""

from __future__ import annotations

from typing import Any

from .assignments import is_left_over, status_label
from .formatting import (
    CONTENT_NOTE,
    clean_text,
    describe_remaining,
    end_of_day,
    format_time,
    format_time_text,
    mark_untrusted,
)
from .moodle import MoodleClient, MoodleError, run_parallel

MAX_DEADLINE_DAYS = 365
DAY = 86400
# Batas dari Moodle untuk core_calendar_get_action_events_by_timesort.
EVENTS_PER_PAGE = 50
MAX_PAGES = 6
# Tugas terlambat dicari sampai sejauh ini ke belakang, kira-kira satu semester.
OVERDUE_LOOKBACK_DAYS = 180

_EVENT_LABELS = {
    "due": "tenggat",
    "close": "ditutup",
    "open": "dibuka",
    "expectcompletionon": "target_selesai",
    "gradingdue": "batas_penilaian",
    "opensubmission": "dibuka",
    "closesubmission": "tenggat",
    "openassessment": "penilaian_dibuka",
    "closeassessment": "tenggat_penilaian",
}
_OPENING_EVENTS = {"open", "opensubmission", "openassessment"}
_HIDDEN_NOTE = (
    "Tidak tampil di kalender LMS, kemungkinan karena aktivitasnya sudah ditandai selesai. "
    "Statusnya sudah dicek langsung dan memang belum dikerjakan."
)

# Satu baris hasil: data aktivitas berbentuk event kalender, dan field tambahan.
_Entry = tuple[dict[str, Any], dict[str, Any]]


def get_deadlines(client: MoodleClient, days: int, now: int) -> dict[str, Any]:
    if not 1 <= days <= MAX_DEADLINE_DAYS:
        raise ValueError(f"days harus antara 1 dan {MAX_DEADLINE_DAYS}.")

    # Sampai akhir hari ke-days, supaya tenggat pukul 23.59 di hari terakhir ikut terhitung.
    until = end_of_day(now, days)
    events, complete = _fetch_events(client, now - OVERDUE_LOOKBACK_DAYS * DAY, until)
    # Tenggat terdekat setelah periode ini, supaya jawaban "tidak ada" tetap punya konteks.
    later = _fetch_page(client, until + 1, None, None, 1)["events"]

    courses = _current_courses(client)
    course_ids = set(courses) | {
        (event.get("course") or {}).get("id")
        for event in events + later
        if event.get("modulename") == "assign"
    }
    assignments = _assignments_by_cmid(client, sorted(course_ids - {None}))

    upcoming: list[_Entry] = []
    overdue: list[_Entry] = []
    skipped = 0
    for event in events:
        if event["timesort"] >= now:
            upcoming.append((event, {}))
        elif _is_current(event, now):
            overdue.append((event, {}))
        else:
            skipped += 1

    # Kalau kalender terpotong, aktivitas yang tidak terambil bukan berarti tersembunyi.
    if complete:
        shown = {event.get("instance") for event in events}
        upcoming += _hidden_assignments(client, assignments, courses, shown, now, until)
        upcoming += _hidden_quizzes(client, courses, shown, now, until)
        upcoming.sort(key=lambda entry: entry[0]["timesort"])
    _check_drafts(client, upcoming + overdue, assignments)

    def items(entries: list[_Entry]) -> list[dict[str, Any]]:
        return [{**_item(event, now, assignments), **extra} for event, extra in entries]

    later_items = items([(event, {}) for event in later])
    result: dict[str, Any] = {
        "content_note": CONTENT_NOTE,
        "now": format_time(now),
        "now_text": format_time_text(now),
        "days": days,
        "period_end": format_time(until),
        "upcoming_count": len(upcoming),
        "upcoming": items(upcoming),
        "overdue_count": len(overdue),
        "overdue": items(overdue),
        "next_after_period": later_items[0] if later_items else None,
        "may_have_more": not complete,
    }
    if skipped:
        result["skipped_old_count"] = skipped
        result["skipped_note"] = (
            "Aktivitas ini tidak ditampilkan karena tenggatnya jauh sebelum mata kuliah "
            "dimulai (sisa semester lalu) atau mata kuliahnya sudah berakhir."
        )
    return result


def _fetch_page(
    client: MoodleClient, start: int, end: int | None, after: int | None, limit: int
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "timesortfrom": start,
        "limitnum": limit,
        # Sama seperti dashboard LMS: mata kuliah yang pendaftarannya ditangguhkan tidak ikut.
        "limittononsuspendedevents": 1,
    }
    if end is not None:
        params["timesortto"] = end
    if after:
        params["aftereventid"] = after
    return client.call("core_calendar_get_action_events_by_timesort", **params)


def _fetch_events(
    client: MoodleClient, start: int, end: int
) -> tuple[list[dict[str, Any]], bool]:
    """Moodle membatasi 50 aktivitas per panggilan, jadi sisanya diambil per halaman."""
    events: list[dict[str, Any]] = []
    after = None
    for _ in range(MAX_PAGES):
        page = _fetch_page(client, start, end, after, EVENTS_PER_PAGE)
        events.extend(page["events"])
        after = page.get("lastid")
        if len(page["events"]) < EVENTS_PER_PAGE or not after:
            return events, len(page["events"]) < EVENTS_PER_PAGE
    return events, False


def _is_current(event: dict[str, Any], now: int) -> bool:
    course = event.get("course") or {}
    if is_left_over(event["timesort"], course.get("startdate")):
        return False
    end = course.get("enddate")
    return not end or end >= now


def _current_courses(client: MoodleClient) -> dict[int, dict[str, Any]]:
    try:
        courses = client.call(
            "core_course_get_enrolled_courses_by_timeline_classification",
            classification="inprogress",
        )["courses"]
    except MoodleError:
        return {}
    return {course["id"]: course for course in courses}


def _assignments_by_cmid(
    client: MoodleClient, course_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """Tanggal buka, batas akhir, dan id tugas tidak ada di kalender, jadi diambil dari
    daftar tugas. Kalau gagal, daftar tenggat tetap ditampilkan tanpa data tambahan ini."""
    if not course_ids:
        return {}
    try:
        courses = client.call("mod_assign_get_assignments", courseids=course_ids)["courses"]
    except MoodleError:
        return {}
    return {
        assignment["cmid"]: assignment
        for course in courses
        for assignment in course.get("assignments", [])
    }


def _assignment_status(client: MoodleClient, assignment_id: int) -> dict[str, Any] | None:
    try:
        return client.call("mod_assign_get_submission_status", assignid=assignment_id)
    except MoodleError:
        return None


def _quiz_attempts(client: MoodleClient, quiz_id: int) -> list[dict[str, Any]] | None:
    try:
        return client.call("mod_quiz_get_user_attempts", quizid=quiz_id, status="all")[
            "attempts"
        ]
    except MoodleError:
        return None


def _hidden_assignments(
    client: MoodleClient,
    assignments: dict[int, dict[str, Any]],
    courses: dict[int, dict[str, Any]],
    shown: set[Any],
    now: int,
    until: int,
) -> list[_Entry]:
    candidates = [
        assignment
        for cmid, assignment in assignments.items()
        if cmid not in shown
        and assignment.get("course") in courses
        and now <= (assignment.get("duedate") or 0) <= until
    ]
    statuses = run_parallel(lambda item: _assignment_status(client, item["id"]), candidates)

    found = []
    for assignment, status in zip(candidates, statuses):
        if status is None:
            continue
        label = status_label(status)
        if label in {"terkumpul", "tanpa_pengumpulan_online"}:
            continue
        attempt = status.get("lastattempt") or {}
        event = {
            "activityname": assignment.get("name"),
            "modulename": "assign",
            "eventtype": "due",
            "instance": assignment["cmid"],
            "timesort": attempt.get("extensionduedate") or assignment["duedate"],
            "course": courses[assignment["course"]],
            "action": {"actionable": bool(attempt.get("canedit"))},
            "url": f"{client.base_url}/mod/assign/view.php?id={assignment['cmid']}",
        }
        found.append((event, {"submission_status": label, "note": _HIDDEN_NOTE}))
    return found


def _hidden_quizzes(
    client: MoodleClient,
    courses: dict[int, dict[str, Any]],
    shown: set[Any],
    now: int,
    until: int,
) -> list[_Entry]:
    if not courses:
        return []
    try:
        quizzes = client.call("mod_quiz_get_quizzes_by_courses", courseids=sorted(courses))[
            "quizzes"
        ]
    except MoodleError:
        return []
    candidates = [
        quiz
        for quiz in quizzes
        if quiz.get("coursemodule") not in shown
        and quiz.get("course") in courses
        and now <= (quiz.get("timeclose") or 0) <= until
    ]
    attempts = run_parallel(lambda quiz: _quiz_attempts(client, quiz["id"]), candidates)

    found = []
    for quiz, tries in zip(candidates, attempts):
        if tries is None:
            continue
        unfinished = [item for item in tries if item.get("state") in {"inprogress", "overdue"}]
        # Kuis yang sudah pernah diselesaikan dianggap sudah dikerjakan, sama seperti di LMS.
        if tries and not unfinished:
            continue
        event = {
            "activityname": quiz.get("name"),
            "modulename": "quiz",
            "eventtype": "close",
            "instance": quiz["coursemodule"],
            "timesort": quiz["timeclose"],
            "course": courses[quiz["course"]],
            "action": {"actionable": (quiz.get("timeopen") or 0) <= now},
            "url": f"{client.base_url}/mod/quiz/view.php?id={quiz['coursemodule']}",
        }
        extra: dict[str, Any] = {"note": _HIDDEN_NOTE}
        if unfinished:
            extra["quiz_status"] = "percobaan_belum_selesai"
        found.append((event, extra))
    return found


def _check_drafts(
    client: MoodleClient, entries: list[_Entry], assignments: dict[int, dict[str, Any]]
) -> None:
    """Di tugas yang perlu dikirim final, file yang sudah diunggah bisa tertahan sebagai
    draft. Kalender tidak membedakannya, jadi status tugas seperti ini dicek langsung."""
    targets = []
    for event, extra in entries:
        assignment = _assignment_of(event, assignments)
        if (
            assignment.get("submissiondrafts")
            and "submission_status" not in extra
            and (event.get("action") or {}).get("actionable")
        ):
            targets.append((assignment["id"], extra))
    statuses = run_parallel(lambda target: _assignment_status(client, target[0]), targets)
    for (_, extra), status in zip(targets, statuses):
        if status is not None:
            extra["submission_status"] = status_label(status)


def _assignment_of(
    event: dict[str, Any], assignments: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    # Di kalender, instance berisi id modul (cmid), bukan id tugas.
    if event.get("modulename") != "assign":
        return {}
    return assignments.get(event.get("instance")) or {}


def _item(
    event: dict[str, Any], now: int, assignments: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    date = event["timesort"]
    course = event.get("course") or {}
    event_type = event.get("eventtype")
    # Field tanggal sengaja tidak bernama due, karena ada juga event dibuka.
    item: dict[str, Any] = {
        "name": clean_text(event.get("activityname") or event.get("name")),
        "type": event.get("modulename"),
        "event": _EVENT_LABELS.get(event_type, event_type),
        "course": clean_text(course.get("fullname")),
        "course_id": course.get("id"),
        "date": format_time(date),
        "date_text": format_time_text(date),
        "time_left": describe_remaining(date, now),
    }
    mark_untrusted(item, "name")
    mark_untrusted(item, "course")

    assignment = _assignment_of(event, assignments)
    opens = assignment.get("allowsubmissionsfromdate") or 0
    closes = assignment.get("cutoffdate") or 0
    if assignment:
        item["assignment_id"] = assignment["id"]
    if opens > now:
        item["opens"] = format_time(opens)
    if closes:
        item["closes"] = format_time(closes)

    actionable = bool((event.get("action") or {}).get("actionable"))
    if date >= now:
        if actionable:
            status = "bisa_dikerjakan"
        elif opens > now or event_type in _OPENING_EVENTS:
            status = "belum_dibuka"
        else:
            status = "belum_bisa_dikerjakan"
    else:
        status = "terlambat_masih_bisa" if actionable else "terlambat_ditutup"
    item["status"] = status
    item["url"] = event.get("url")
    return item
