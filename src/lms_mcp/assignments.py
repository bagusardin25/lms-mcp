"""Membaca tugas dan mengumpulkan file tugas.

Di banyak tugas, Moodle tidak punya tahap draft (submissiondrafts bernilai 0): file yang
disimpan langsung terhitung terkumpul. Karena itu penyimpanan di tugas seperti ini harus
disetujui secara eksplisit lewat allow_immediate.
"""

from __future__ import annotations

import posixpath
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .formatting import (
    CONTENT_NOTE,
    clean_file_name,
    clean_text,
    describe_remaining,
    format_time,
    format_time_text,
    mark_untrusted,
)
from .moodle import MoodleClient, MoodleError, run_parallel

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
DESCRIPTION_LIMIT = 3000
COMMENT_LIMIT = 1000
# Kelonggaran kalau tanggal mulai mata kuliah diatur sedikit terlambat.
LEFT_OVER_MARGIN = 30 * 86400

# Berkas seperti ini hampir pasti rahasia, bukan tugas kuliah. File tujuan upload datang
# dari AI, yang bisa saja terpancing instruksi tersembunyi di konten LMS.
_BLOCKED_EXTENSIONS = {".env", ".pem", ".key", ".p12", ".pfx", ".kdbx", ".ppk", ".keystore"}
_BLOCKED_NAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
    "credentials",
    "secrets.json",
    "cookies",
    "cookies.txt",
    "login data",
}

_STATUS_LABELS = {
    None: "belum_dikumpulkan",
    "new": "belum_dikumpulkan",
    "draft": "draft",
    "submitted": "terkumpul",
    "reopened": "dibuka_lagi",
}


class AssignmentError(ValueError):
    pass


def is_left_over(timestamp: int | None, course_start: int | None) -> bool:
    """Mata kuliah sering disalin dari semester lalu bersama tugasnya. Tenggat yang jauh
    sebelum mata kuliah dimulai berarti tugas sisa salinan itu, bukan tugas semester ini."""
    return bool(timestamp and course_start and timestamp < course_start - LEFT_OVER_MARGIN)


@dataclass(frozen=True)
class SubmissionRules:
    accepts_files: bool
    accepts_online_text: bool
    max_files: int
    max_bytes: int
    file_types: tuple[str, ...]
    needs_final_submit: bool
    requires_statement: bool
    statement: str
    team_submission: bool


def submission_rules(assignment: dict[str, Any]) -> SubmissionRules:
    configs = {
        (item["plugin"], item["name"]): item["value"]
        for item in assignment.get("configs", [])
        if item.get("subtype") == "assignsubmission"
    }
    types = configs.get(("file", "filetypeslist")) or ""
    return SubmissionRules(
        accepts_files=configs.get(("file", "enabled")) == "1",
        accepts_online_text=configs.get(("onlinetext", "enabled")) == "1",
        max_files=int(configs.get(("file", "maxfilesubmissions")) or 0),
        max_bytes=int(configs.get(("file", "maxsubmissionsizebytes")) or 0),
        file_types=tuple(item.strip().lower() for item in types.split(",") if item.strip()),
        needs_final_submit=bool(assignment.get("submissiondrafts")),
        requires_statement=bool(assignment.get("requiresubmissionstatement")),
        statement=clean_text(assignment.get("submissionstatement")),
        team_submission=bool(assignment.get("teamsubmission")),
    )


def is_file_type_allowed(file_name: str, file_types: Sequence[str]) -> bool:
    """Grup seperti document atau image tidak bisa dicek di sini, jadi diserahkan ke LMS."""
    if not file_types or "*" in file_types:
        return True
    if any(not item.startswith(".") for item in file_types):
        return True
    return posixpath.splitext(file_name)[1].lower() in file_types


def local_upload_path(
    path_text: str,
    allowed_dirs: Sequence[Path],
    blocked_roots: Sequence[Path] = (),
) -> Path:
    """Memeriksa path dari AI tanpa membaca isinya. Isi baru dibaca setelah pengguna setuju."""
    try:
        path = Path(path_text).expanduser().resolve(strict=True)
    except OSError:
        raise AssignmentError("File tidak ditemukan. Periksa lagi lokasinya.") from None

    roots = [folder.expanduser().resolve() for folder in allowed_dirs]
    if not any(path.is_relative_to(root) for root in roots):
        folders = ", ".join(str(root) for root in roots) or "(belum ada)"
        raise AssignmentError(
            f"Demi keamanan, file hanya boleh diambil dari folder ini: {folders}. "
            "Pindahkan filenya, atau atur LMS_UPLOAD_DIRS."
        )
    if any(path.is_relative_to(root.expanduser().resolve()) for root in blocked_roots):
        raise AssignmentError(
            "File dari folder unduhan LMS tidak boleh langsung dikumpulkan. "
            "Salin ke folder lain dulu kalau memang itu tugasmu."
        )
    if (
        any(part.startswith(".") for part in path.parts)
        or path.suffix.lower() in _BLOCKED_EXTENSIONS
        or path.name.lower() in _BLOCKED_NAMES
    ):
        raise AssignmentError("File ini tidak boleh diunggah karena kemungkinan berisi rahasia.")
    if not path.is_file():
        raise AssignmentError("Yang dipilih bukan file.")
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise AssignmentError(f"File melebihi batas {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return path


def read_local_upload(
    path_text: str,
    allowed_dirs: Sequence[Path],
    blocked_roots: Sequence[Path] = (),
) -> tuple[str, bytes]:
    """Membaca file untuk mode lokal. Path datang dari AI, jadi lokasinya dibatasi."""
    path = local_upload_path(path_text, allowed_dirs, blocked_roots)
    return clean_file_name(path.name), path.read_bytes()


class AssignmentOperations:
    def __init__(
        self,
        client: MoodleClient,
        upload_dirs: Sequence[Path] = (),
        clock: Callable[[], float] = time.time,
        download_dir: Path | None = None,
    ) -> None:
        self._client = client
        self._upload_dirs = upload_dirs
        self._clock = clock
        self._download_dir = download_dir

    # Membaca

    def _course_assignments(self, course_id: int) -> list[dict[str, Any]]:
        courses = self._client.call("mod_assign_get_assignments", courseids=[course_id])["courses"]
        return [item for course in courses for item in course["assignments"]]

    def _find(self, course_id: int, assignment_id: int) -> dict[str, Any]:
        for assignment in self._course_assignments(course_id):
            if assignment["id"] == assignment_id:
                return assignment
        raise AssignmentError("Tugas tidak ditemukan di mata kuliah ini.")

    def _status(self, assignment_id: int) -> dict[str, Any]:
        return self._client.call("mod_assign_get_submission_status", assignid=assignment_id)

    def _url(self, assignment: dict[str, Any]) -> str:
        return f"{self._client.base_url}/mod/assign/view.php?id={assignment['cmid']}"

    def _course_start(self, course_id: int) -> int:
        try:
            courses = self._client.call(
                "core_course_get_courses_by_field", field="id", value=course_id
            )["courses"]
        except MoodleError:
            return 0
        return (courses[0].get("startdate") or 0) if courses else 0

    def status_or_error(self, assignment_id: int) -> dict[str, Any] | MoodleError:
        try:
            return self._status(assignment_id)
        except MoodleError as error:
            return error

    def list_assignments(self, course_id: int) -> dict[str, Any]:
        now = int(self._clock())
        course_start = self._course_start(course_id)
        assignments = self._course_assignments(course_id)
        # Status tugas sisa semester lalu tidak diambil, supaya tidak perlu puluhan
        # panggilan ke LMS untuk tugas yang tidak relevan.
        old: list[dict[str, Any]] = []
        current_assignments: list[dict[str, Any]] = []
        for assignment in assignments:
            left_over = is_left_over(assignment.get("duedate"), course_start)
            (old if left_over else current_assignments).append(assignment)
        statuses = run_parallel(
            self.status_or_error, [item["id"] for item in current_assignments]
        )

        current = []
        for assignment, status in zip(current_assignments, statuses):
            item: dict[str, Any] = {
                "id": assignment["id"],
                "name": clean_text(assignment.get("name")),
            }
            if isinstance(status, MoodleError):
                item["status_error"] = status.errorcode
                status = {}
            opens = assignment.get("allowsubmissionsfromdate") or 0
            if opens > now:
                item["opens"] = format_time(opens)
            item.update(_deadline_fields(assignment, status, now))
            if status:
                item.update(_status_summary(status))
            if assignment.get("teamsubmission"):
                item["team_submission"] = True
                item.update(_team_fields(assignment, status))
            item["url"] = self._url(assignment)
            current.append(item)

        # Tenggat terdekat lebih dulu, tugas tanpa tenggat di akhir.
        current.sort(key=lambda item: (item["due"] is None, item["due"] or ""))
        result: dict[str, Any] = {
            "course_id": course_id,
            "now": format_time(now),
            "now_text": format_time_text(now),
            "count": len(current),
            "assignments": current,
        }
        if old:
            result["old_count"] = len(old)
            result["old_assignments"] = [
                {
                    "id": item["id"],
                    "name": clean_text(item.get("name")),
                    "due": format_time(item.get("duedate")),
                }
                for item in old
            ]
            result["old_note"] = (
                "Tenggatnya jauh sebelum mata kuliah dimulai, jadi kemungkinan sisa salinan "
                "semester lalu. Statusnya tidak diambil; pakai get_assignment kalau perlu."
            )
        return result

    def get_assignment(self, course_id: int, assignment_id: int) -> dict[str, Any]:
        now = int(self._clock())
        assignment = self._find(course_id, assignment_id)
        status = self._status(assignment_id)
        rules = submission_rules(assignment)
        result: dict[str, Any] = {
            "id": assignment_id,
            "name": clean_text(assignment.get("name")),
            "description": clean_text(assignment.get("intro"), DESCRIPTION_LIMIT),
        }
        # Moodle tidak mengirim instruksi tugas yang diatur baru tampil saat dibuka.
        if "intro" not in assignment:
            result["description_note"] = (
                "Instruksi belum ditampilkan LMS. Biasanya muncul setelah tugas dibuka."
            )
        detailed = {
            **result,
            "content_note": CONTENT_NOTE,
            "now": format_time(now),
            "now_text": format_time_text(now),
            "opens": format_time(assignment.get("allowsubmissionsfromdate")),
            "closes": None,
            **_deadline_fields(assignment, status, now),
            **_team_fields(assignment, status),
            "url": self._url(assignment),
            "instruction_files": [
                {
                    "name": item["filename"],
                    "size_bytes": item.get("filesize"),
                    "file_url": item["fileurl"],
                }
                for item in assignment.get("introattachments", [])
            ],
            "rules": {
                "accepts_files": rules.accepts_files,
                "accepts_online_text": rules.accepts_online_text,
                "max_files": rules.max_files,
                "max_bytes": rules.max_bytes,
                "file_types": list(rules.file_types),
                "saving_file_submits_immediately": not rules.needs_final_submit,
                "team_submission": rules.team_submission,
            },
            **_status_summary(status),
            "submitted_files": _submitted_files(status),
            "feedback": _feedback_comments(status),
        }
        mark_untrusted(detailed, "description")
        mark_untrusted(detailed, "feedback")
        mark_untrusted(detailed, "name")
        return detailed

    # Mengumpulkan

    def upload_context(self, course_id: int, assignment_id: int) -> dict[str, Any]:
        """Data yang perlu dilihat pengguna sebelum mengunggah."""
        assignment = self._find(course_id, assignment_id)
        status = self._status(assignment_id)
        rules = submission_rules(assignment)
        _check_can_edit(rules, status)
        return self._page_context(course_id, assignment, status, rules)

    def submit_preview(self, course_id: int, assignment_id: int) -> dict[str, Any]:
        """Data halaman konfirmasi kirim final. Belum mengirim apa pun."""
        assignment = self._find(course_id, assignment_id)
        status = self._status(assignment_id)
        rules = submission_rules(assignment)
        if not rules.needs_final_submit:
            raise AssignmentError(
                "Tugas ini tidak perlu dikirim lagi, karena terkumpul saat disimpan."
            )
        if status_label(status) == "terkumpul":
            raise AssignmentError("Tugas ini sudah terkumpul.")
        if not (status.get("lastattempt") or {}).get("cansubmit"):
            raise AssignmentError(
                "Tugas ini belum bisa dikirim. Pastikan sudah ada file tersimpan."
            )
        return self._page_context(course_id, assignment, status, rules)

    def _course_section(self, course_id: int, assignment_id: int) -> tuple[str, str]:
        try:
            courses = self._client.call(
                "core_course_get_courses_by_field", field="id", value=course_id
            )["courses"]
        except MoodleError:
            courses = []
        course = clean_text(courses[0].get("fullname")) if courses else ""
        try:
            sections = self._client.call("core_course_get_contents", courseid=course_id)
        except MoodleError:
            return course, ""
        for section in sections or []:
            for module in section.get("modules") or []:
                instance = module.get("instance")
                if module.get("modname") != "assign" or instance is None:
                    continue
                try:
                    same = int(instance) == assignment_id
                except (TypeError, ValueError):
                    continue
                if same:
                    return course, clean_text(section.get("name"))
        return course, ""

    def _page_context(
        self,
        course_id: int,
        assignment: dict[str, Any],
        status: dict[str, Any],
        rules: SubmissionRules,
    ) -> dict[str, Any]:
        course, section = self._course_section(course_id, assignment["id"])
        deadlines = _deadline_fields(assignment, status, int(self._clock()))
        return {
            "name": clean_text(assignment.get("name")),
            "course": course or "Tidak diketahui",
            "section": section or "Tidak muncul di daftar bagian",
            "due": deadlines.get("due"),
            "due_text": deadlines.get("due_text"),
            "time_left": deadlines.get("time_left"),
            "url": self._url(assignment),
            "rules": rules,
            "submitted_files": _submitted_files(status),
            "submission_status": status_label(status),
            "statement": rules.statement if rules.requires_statement else "",
        }

    def save_file(
        self,
        course_id: int,
        assignment_id: int,
        file_name: str,
        data: bytes,
        *,
        replace_existing: bool = False,
        allow_immediate: bool = False,
    ) -> dict[str, Any]:
        file_name = clean_file_name(file_name)
        assignment = self._find(course_id, assignment_id)
        status = self._status(assignment_id)
        rules = submission_rules(assignment)

        _check_can_edit(rules, status)
        if not is_file_type_allowed(file_name, rules.file_types):
            allowed = ", ".join(rules.file_types)
            raise AssignmentError(f"Tugas ini hanya menerima format {allowed}.")
        limit = rules.max_bytes or MAX_UPLOAD_BYTES
        if len(data) > limit:
            raise AssignmentError(f"File melebihi batas tugas ini, yaitu {_format_size(limit)}.")
        if not data:
            raise AssignmentError("File kosong.")
        if self._client.appears_in(data):
            raise AssignmentError(
                "File ini berisi token LMS, jadi tidak diunggah. Token tidak boleh masuk ke tugas."
            )

        existing = _submitted_files(status)
        if existing and not replace_existing:
            names = ", ".join(item["name"] for item in existing)
            raise AssignmentError(
                f"Tugas ini sudah berisi file: {names}. File baru akan menggantikannya, "
                "jadi perlu persetujuan untuk mengganti."
            )
        if not rules.needs_final_submit and not allow_immediate:
            raise AssignmentError(
                "Tugas ini tidak punya tahap draft: file yang disimpan langsung terkumpul. "
                "Perlu persetujuan pengguna untuk mengumpulkan."
            )

        item_id = self._client.upload_draft_file(file_name, data)
        warnings = self._client.call(
            "mod_assign_save_submission",
            assignmentid=assignment_id,
            plugindata={"files_filemanager": item_id},
        )
        _raise_for_warnings(warnings, "File gagal disimpan")
        return self._result(assignment, rules)

    def submit_final(
        self, course_id: int, assignment_id: int, *, statement_accepted: bool = False
    ) -> dict[str, Any]:
        assignment = self._find(course_id, assignment_id)
        status = self._status(assignment_id)
        rules = submission_rules(assignment)

        if not rules.needs_final_submit:
            raise AssignmentError("Tugas ini tidak perlu dikirim lagi, karena terkumpul saat disimpan.")
        if status_label(status) == "terkumpul":
            raise AssignmentError("Tugas ini sudah terkumpul.")
        if not (status.get("lastattempt") or {}).get("cansubmit"):
            raise AssignmentError("Tugas ini belum bisa dikirim. Pastikan sudah ada file tersimpan.")
        if rules.requires_statement and not statement_accepted:
            raise AssignmentError(
                f"Pengguna harus menyetujui pernyataan ini dulu: {rules.statement}"
            )

        warnings = self._client.call(
            "mod_assign_submit_for_grading",
            assignmentid=assignment_id,
            acceptsubmissionstatement=int(statement_accepted),
        )
        _raise_for_warnings(warnings, "Tugas gagal dikirim")
        return self._result(assignment, rules)

    def save_local_file(
        self,
        course_id: int,
        assignment_id: int,
        file_path: str,
        *,
        replace_existing: bool = False,
        allow_immediate: bool = False,
    ) -> dict[str, Any]:
        blocked = (self._download_dir,) if self._download_dir is not None else ()
        file_name, data = read_local_upload(file_path, self._upload_dirs, blocked)
        return self.save_file(
            course_id,
            assignment_id,
            file_name,
            data,
            replace_existing=replace_existing,
            allow_immediate=allow_immediate,
        )

    def _result(self, assignment: dict[str, Any], rules: SubmissionRules) -> dict[str, Any]:
        # Dibaca ulang dari LMS, supaya yang dilaporkan adalah kondisi sebenarnya.
        status = self._status(assignment["id"])
        label = status_label(status)
        result = {
            "assignment": clean_text(assignment.get("name")),
            "submission_status": label,
            "submitted_files": _submitted_files(status),
            "url": self._url(assignment),
        }
        if label == "draft":
            result["next_step"] = "File tersimpan sebagai draft dan belum terkirim ke dosen."
        if rules.team_submission:
            result["note"] = "Kiriman ini berlaku untuk seluruh kelompok."
        return result


def _submission(status: dict[str, Any]) -> dict[str, Any]:
    # Di tugas kelompok, yang dinilai dan berisi file adalah kiriman kelompok.
    attempt = status.get("lastattempt") or {}
    return attempt.get("teamsubmission") or attempt.get("submission") or {}


def status_label(status: dict[str, Any]) -> str:
    raw = _submission(status).get("status")
    # Tugas tanpa plugin pengumpulan hanya dipakai dosen untuk mencatat nilai.
    no_online_submission = (status.get("lastattempt") or {}).get("submissionsenabled") is False
    if no_online_submission and raw in {None, "new"}:
        return "tanpa_pengumpulan_online"
    return _STATUS_LABELS.get(raw, raw)


def _team_fields(assignment: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    if not assignment.get("teamsubmission"):
        return {}
    attempt = status.get("lastattempt") or {}
    fields: dict[str, Any] = {}
    if attempt and not attempt.get("usergroups") and assignment.get("preventsubmissionnotingroup"):
        fields["team_note"] = (
            "Pengguna belum masuk kelompok mana pun di LMS, jadi belum bisa mengumpulkan. "
            "Dosen perlu memasukkannya ke kelompok."
        )
    pending = attempt.get("submissiongroupmemberswhoneedtosubmit") or []
    if pending:
        fields["team_members_still_to_submit"] = len(pending)
    return fields


def _deadline_fields(
    assignment: dict[str, Any], status: dict[str, Any], now: int
) -> dict[str, Any]:
    """Tenggat yang berlaku untuk pengguna ini, termasuk perpanjangan dari dosen."""
    opens = assignment.get("allowsubmissionsfromdate") or 0
    original_due = assignment.get("duedate") or 0
    closes = assignment.get("cutoffdate") or 0
    extension = (status.get("lastattempt") or {}).get("extensionduedate") or 0
    due = extension or original_due
    # Seperti di Moodle, perpanjangan bisa melewati batas akhir, tetapi tidak membuat
    # batas akhir muncul kalau tugasnya memang tidak punya.
    if extension and closes:
        closes = max(closes, extension)

    # Seperti di Moodle, tepat pada detik tenggat atau batas akhir kiriman masih diterima.
    if opens > now:
        state = "belum_dibuka"
    elif closes and closes < now:
        state = "ditutup"
    elif not due:
        state = "tanpa_tenggat"
    elif due >= now:
        state = "berjalan"
    else:
        state = "lewat_tenggat"

    fields: dict[str, Any] = {"due": format_time(due)}
    if due:
        fields["due_text"] = format_time_text(due)
        fields["time_left"] = describe_remaining(due, now)
    if extension:
        fields["original_due"] = format_time(original_due)
    if closes:
        fields["closes"] = format_time(closes)
    fields["deadline_state"] = state
    return fields


def _status_summary(status: dict[str, Any]) -> dict[str, Any]:
    attempt = status.get("lastattempt") or {}
    summary = {
        "submission_status": status_label(status),
        "can_edit": bool(attempt.get("submissionsenabled") and attempt.get("canedit")),
        "graded": bool(attempt.get("graded")),
    }
    grade = clean_text((status.get("feedback") or {}).get("gradefordisplay"))
    if grade:
        summary["grade"] = grade
    modified = format_time(_submission(status).get("timemodified"))
    if modified:
        summary["last_modified"] = modified
    return summary


def _submitted_files(status: dict[str, Any]) -> list[dict[str, Any]]:
    files = []
    for plugin in _submission(status).get("plugins") or []:
        if plugin.get("type") != "file":
            continue
        for area in plugin.get("fileareas") or []:
            for item in area.get("files") or []:
                files.append(
                    {
                        "name": item["filename"],
                        "size_bytes": item.get("filesize"),
                        "file_url": item.get("fileurl"),
                    }
                )
    return files


def _feedback_comments(status: dict[str, Any]) -> str:
    for plugin in (status.get("feedback") or {}).get("plugins") or []:
        if plugin.get("type") == "comments":
            for field in plugin.get("editorfields") or []:
                text = clean_text(field.get("text"), COMMENT_LIMIT)
                if text:
                    return text
    return ""


def _check_can_edit(rules: SubmissionRules, status: dict[str, Any]) -> None:
    attempt = status.get("lastattempt") or {}
    if not rules.accepts_files:
        raise AssignmentError("Tugas ini tidak menerima unggahan file.")
    if not attempt.get("submissionsenabled") or not attempt.get("canedit") or attempt.get("locked"):
        raise AssignmentError("Tugas ini sedang tidak bisa diubah, mungkin belum dibuka atau sudah ditutup.")


def _raise_for_warnings(warnings: Any, message: str) -> None:
    if not warnings:
        return
    detail = clean_text(warnings[0].get("message")) if isinstance(warnings, list) else ""
    raise AssignmentError(f"{message}. {detail}".strip())


def _format_size(size: int) -> str:
    return f"{size / (1024 * 1024):g} MB"
