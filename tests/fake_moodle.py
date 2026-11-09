"""LMS tiruan untuk menguji pengumpulan tugas tanpa menyentuh tugas sungguhan."""

import re
from urllib.parse import parse_qs

import httpx

LMS_URL = "https://lms.contoh.test"
COURSE_ID = 7
COURSE_NAME = "Data Mining Advance"
SECTION_NAME = "Minggu 3"
ASSIGNMENT_ID = 11
CMID = 855
OPENS = 1793000000
DUE = 1794000000
COURSE_START = OPENS - 30 * 86400


class FakeMoodle:
    def __init__(
        self,
        *,
        drafts=False,
        statement="",
        file_types="",
        max_bytes=1048576,
        existing=(),
        can_edit=True,
        accepts_files=True,
        team=False,
        users=None,
        cutoff=0,
        extension=0,
        course_start=COURSE_START,
        submissions_enabled=True,
        groups=(5,),
        prevent_no_group=False,
        members_pending=(),
        hide_intro=False,
        intro=None,
    ):
        self.drafts = drafts
        self.statement = statement
        self.file_types = file_types
        self.max_bytes = max_bytes
        self.can_edit = can_edit
        self.accepts_files = accepts_files
        self.team = team
        self.users = users
        self.cutoff = cutoff
        self.extension = extension
        self.course_start = course_start
        self.submissions_enabled = submissions_enabled
        self.groups = list(groups)
        self.prevent_no_group = prevent_no_group
        self.members_pending = list(members_pending)
        self.hide_intro = hide_intro
        self.intro = intro
        self.files = list(existing)
        self.status = "submitted" if existing else "new"
        self.pending = None
        self.calls = []
        self.uploads = []
        self.save_warnings = []
        self.submit_warnings = []
        self.status_error = False

    def client(self, token="token"):
        from lms_mcp.moodle import MoodleClient

        return MoodleClient(LMS_URL, token, httpx.MockTransport(self.handler))

    def handler(self, request):
        if request.url.path.endswith("/webservice/upload.php"):
            return self._upload(request)
        body = parse_qs(request.content.decode())
        function = body["wsfunction"][0]
        self.calls.append((function, body))
        if self.users is not None and body["wstoken"][0] not in self.users:
            return httpx.Response(
                200,
                json={
                    "exception": "moodle_exception",
                    "errorcode": "invalidtoken",
                    "message": "Invalid token",
                },
            )
        return httpx.Response(200, json=getattr(self, f"_{function}")(body))

    def _upload(self, request):
        name = re.search(rb'filename="([^"]+)"', request.content).group(1).decode()
        self.uploads.append(name)
        self.pending = name
        return httpx.Response(200, json=[{"filename": name, "itemid": 77, "filepath": "/"}])

    def _core_webservice_get_site_info(self, body):
        name = (self.users or {}).get(body["wstoken"][0], "Mahasiswa")
        return {
            "fullname": name,
            "username": name.lower(),
            "userid": 1,
            "sitename": "LMS",
            "siteurl": LMS_URL,
            "release": "4.5",
        }

    def _core_course_get_courses_by_field(self, body):
        assert body["field"] == ["id"] and body["value"] == [str(COURSE_ID)]
        return {
            "courses": [
                {"id": COURSE_ID, "fullname": COURSE_NAME, "startdate": self.course_start}
            ]
        }

    def _core_course_get_contents(self, body):
        return [
            {
                "name": SECTION_NAME,
                "modules": [
                    {
                        "id": CMID,
                        "name": "Tugas &amp; Latihan",
                        "modname": "assign",
                        "instance": ASSIGNMENT_ID,
                        "url": f"{LMS_URL}/mod/assign/view.php?id={CMID}",
                    }
                ],
            }
        ]

    def _mod_assign_get_assignments(self, body):
        assert body["courseids[0]"] == [str(COURSE_ID)]
        configs = [
            {
                "plugin": "file",
                "subtype": "assignsubmission",
                "name": "maxsubmissionsizebytes",
                "value": str(self.max_bytes),
            },
            {
                "plugin": "file",
                "subtype": "assignsubmission",
                "name": "maxfilesubmissions",
                "value": "1",
            },
            {
                "plugin": "file",
                "subtype": "assignsubmission",
                "name": "filetypeslist",
                "value": self.file_types,
            },
        ]
        if self.accepts_files:
            configs.append(
                {"plugin": "file", "subtype": "assignsubmission", "name": "enabled", "value": "1"}
            )
        assignment = {
            "id": ASSIGNMENT_ID,
            "cmid": CMID,
            "name": "Tugas &amp; Latihan",
            "intro": self.intro
            if self.intro is not None
            else "<p>Kerjakan <b>bab 1</b></p>",
            "duedate": DUE,
            "allowsubmissionsfromdate": OPENS,
            "cutoffdate": self.cutoff,
            "submissiondrafts": int(self.drafts),
            "requiresubmissionstatement": int(bool(self.statement)),
            "submissionstatement": self.statement,
            "teamsubmission": int(self.team),
            "preventsubmissionnotingroup": int(self.prevent_no_group),
            "configs": configs,
            "introattachments": [
                {
                    "filename": "soal.pdf",
                    "filesize": 10,
                    "fileurl": f"{LMS_URL}/webservice/pluginfile.php/1/soal.pdf",
                }
            ],
        }
        # Moodle tidak mengirim instruksi yang diatur baru tampil saat tugas dibuka.
        if self.hide_intro:
            del assignment["intro"]
            assignment["introattachments"] = []
        return {"courses": [{"id": COURSE_ID, "assignments": [assignment]}]}

    def _mod_assign_get_submission_status(self, body):
        if self.status_error:
            return {
                "exception": "moodle_exception",
                "errorcode": "nopermission",
                "message": "Ditolak",
            }
        submission = {
            "status": self.status,
            "timemodified": 1794000000,
            "plugins": [
                {
                    "type": "file",
                    "fileareas": [
                        {
                            "area": "submission_files",
                            "files": [
                                {
                                    "filename": name,
                                    "filesize": 5,
                                    "fileurl": f"{LMS_URL}/webservice/pluginfile.php/2/{name}",
                                }
                                for name in self.files
                            ],
                        }
                    ],
                }
            ],
        }
        attempt = {
            "submissionsenabled": self.submissions_enabled,
            "canedit": self.can_edit,
            "extensionduedate": self.extension,
            "cansubmit": self.status == "draft",
            "locked": False,
            "graded": False,
            "submission": submission,
        }
        if self.team:
            # Di tugas kelompok, file dan status yang berlaku ada di kiriman kelompok.
            # Catatan kiriman pribadi bisa tertinggal dengan status lama.
            attempt["teamsubmission"] = submission
            attempt["submission"] = {"status": "new", "plugins": []}
            attempt["usergroups"] = self.groups
            attempt["submissiongroupmemberswhoneedtosubmit"] = self.members_pending
        return {
            "lastattempt": attempt,
            "feedback": {
                "gradefordisplay": "<b>90</b>",
                "plugins": [{"type": "comments", "editorfields": [{"text": "<p>Bagus</p>"}]}],
            },
        }

    def _mod_assign_save_submission(self, body):
        assert body["plugindata[files_filemanager]"] == ["77"]
        if self.save_warnings:
            return self.save_warnings
        self.files = [self.pending]
        self.status = "draft" if self.drafts else "submitted"
        return []

    def _mod_assign_submit_for_grading(self, body):
        if self.submit_warnings:
            return self.submit_warnings
        self.status = "submitted"
        return []
