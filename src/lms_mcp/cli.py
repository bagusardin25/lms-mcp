"""Perintah baris: lms-mcp check dan lms-mcp serve."""

from __future__ import annotations

import argparse
import html
import sys
import time

import httpx

from .auth import TokenError, token_page_url
from .config import ConfigError, load_config
from .deadlines import get_deadlines
from .moodle import MoodleClient, MoodleError
from .server import run_http_server, run_server
from .service import create_client

DEADLINE_DAYS = 14

# Fungsi yang dipakai atau direncanakan untuk tool MCP.
READ_FUNCTIONS = (
    "core_course_get_enrolled_courses_by_timeline_classification",
    "core_course_get_contents",
    "core_course_get_courses_by_field",
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
    result = get_deadlines(client, DEADLINE_DAYS, int(time.time()))
    for title, key in (
        (f"Deadline {DEADLINE_DAYS} hari ke depan", "upcoming"),
        ("Lewat tenggat dan belum dikumpulkan", "overdue"),
    ):
        print(f"\n{title}: {len(result[key])}")
        for item in result[key]:
            print(
                f"  - {item['date_text']}  [{item['course'] or '-'}] {item['name']}"
                f"  ({item['status']}, {item['time_left']})"
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


def cmd_token() -> int:
    print("Buka halaman ini di browser dan login kalau diminta:")
    print(f"  {token_page_url(load_config().base_url)}")
    print(
        'Lalu klik kanan "Click here if the app does not open automatically", pilih '
        '"Copy link address", dan tempel setelah LMS_TOKEN= di file .env.'
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lms-mcp", description="MCP untuk LMS berbasis Moodle")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="uji akses ke API LMS")
    commands.add_parser("token", help="tampilkan alamat halaman untuk mengambil token")
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
        if args.command == "token":
            return cmd_token()
        return cmd_check()
    except ConfigError as error:
        print(f"Konfigurasi belum lengkap: {error}", file=sys.stderr)
    except (TokenError, MoodleError) as error:
        print(f"Gagal: {error}", file=sys.stderr)
    except httpx.HTTPError as error:
        print(f"Gagal menghubungi LMS: {error}", file=sys.stderr)
    return 1
