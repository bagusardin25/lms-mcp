"""Perintah baris: lms-mcp check dan lms-mcp serve."""

from __future__ import annotations

import argparse
import html
import sys
import time
from datetime import datetime

import httpx

from .auth import TokenError
from .config import ConfigError, load_config
from .moodle import MoodleClient, MoodleError
from .server import run_http_server, run_server
from .service import WIB, create_client

DEADLINE_DAYS = 14

# Fungsi yang dipakai atau direncanakan untuk tool MCP.
READ_FUNCTIONS = (
    "core_course_get_enrolled_courses_by_timeline_classification",
    "core_course_get_contents",
    "core_calendar_get_action_events_by_timesort",
    "mod_assign_get_assignments",
    "mod_assign_get_submission_status",
    "gradereport_user_get_grade_items",
    "mod_forum_get_forums_by_courses",
    "mod_forum_get_forum_discussions",
    "message_popup_get_popup_notifications",
    "mod_quiz_get_quizzes_by_courses",
    "mod_attendance_get_courses_with_today_sessions",
)
WRITE_FUNCTIONS = (
    "mod_assign_save_submission",
    "mod_assign_submit_for_grading",
    "mod_forum_add_discussion_post",
    "core_message_send_instant_messages",
    "core_completion_update_activity_completion_status_manually",
    "enrol_self_enrol_user",
)


def print_courses(client: MoodleClient) -> None:
    courses = client.call(
        "core_course_get_enrolled_courses_by_timeline_classification",
        classification="inprogress",
    )["courses"]

    print(f"\nMata kuliah berjalan: {len(courses)}")
    for course in courses:
        print(f"  - {html.unescape(course['fullname'])}")


def print_deadlines(client: MoodleClient) -> None:
    now = int(time.time())
    events = client.call(
        "core_calendar_get_action_events_by_timesort",
        timesortfrom=now,
        timesortto=now + DEADLINE_DAYS * 86400,
        limitnum=20,
    )["events"]

    print(f"\nDeadline {DEADLINE_DAYS} hari ke depan: {len(events)}")
    for event in events:
        due = datetime.fromtimestamp(event["timesort"], WIB)
        course = (event.get("course") or {}).get("fullname", "-")
        name = event.get("activityname") or event["name"]
        print(
            f"  - {due:%d-%m-%Y %H:%M} WIB  "
            f"[{html.unescape(course)}] {html.unescape(name)}"
        )


def format_upload_limit(size: int | None) -> str:
    if size is None:
        return "tidak diketahui"
    if size < 0:
        return "tanpa batas"
    return f"{size / (1024 * 1024):.0f} MB"


def print_file_permissions(info: dict) -> None:
    print("\nIzin file:")
    print(f"  Unduh : {'ya' if info.get('downloadfiles') else 'tidak'}")
    print(f"  Upload: {'ya' if info.get('uploadfiles') else 'tidak'}")
    print(f"  Batas ukuran upload: {format_upload_limit(info.get('usermaxuploadfilesize'))}")


def print_functions(info: dict) -> None:
    available = {function["name"] for function in info.get("functions", [])}

    for title, names in (
        ("Fungsi API baca", READ_FUNCTIONS),
        ("Fungsi API tulis", WRITE_FUNCTIONS),
    ):
        print(f"\n{title}:")
        for name in names:
            print(f"  [{'ada' if name in available else ' - '}] {name}")


def cmd_check() -> int:
    sys.stdout.reconfigure(errors="replace", line_buffering=True)

    client = create_client(load_config())
    info = client.call("core_webservice_get_site_info")
    print(f"Terhubung sebagai {info['fullname']} (userid {info['userid']})")
    print(f"Situs: {info['sitename']}, Moodle {info['release']}")

    # Satu langkah yang gagal tidak menghentikan pemeriksaan lainnya.
    failed = False
    for step in (print_courses, print_deadlines):
        try:
            step(client)
        except MoodleError as error:
            print(f"\nGagal: {error}")
            failed = True

    print_file_permissions(info)
    print_functions(info)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lms-mcp", description="MCP untuk LMS Telkom")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="uji akses ke API LMS")
    serve = commands.add_parser("serve", help="jalankan MCP server")
    serve.add_argument(
        "--http", action="store_true", help="mode online lewat HTTP dengan login OAuth"
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "serve":
            if args.http:
                run_http_server()
            else:
                run_server()
            return 0
        return cmd_check()
    except ConfigError as error:
        print(f"Konfigurasi belum lengkap: {error}", file=sys.stderr)
    except (TokenError, MoodleError) as error:
        print(f"Gagal: {error}", file=sys.stderr)
    except httpx.HTTPError as error:
        print(f"Gagal menghubungi LMS: {error}", file=sys.stderr)
    return 1
