import html
import json
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from fake_moodle import ASSIGNMENT_ID, COURSE_ID, LMS_URL, FakeMoodle
from starlette.testclient import TestClient
from test_oauth import PUBLIC_URL, SECRET, TOKEN_ANI, USERS, call_tool, mcp, sign_in

from lms_mcp.assignments import MAX_UPLOAD_BYTES
from lms_mcp.config import HttpConfig
from lms_mcp.oauth import Sealer
from lms_mcp.server import build_http_server, http_transport_options


def make_client(moodle, enable_write=True):
    config = HttpConfig(LMS_URL, PUBLIC_URL, SECRET, enable_write=enable_write)
    server = build_http_server(config, create_lms_client=moodle.client)
    app = server.streamable_http_app(**http_transport_options(config))
    return TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)


@pytest.fixture
def setup(request):
    options = getattr(request, "param", {})
    moodle = FakeMoodle(users=USERS, **options)
    with make_client(moodle) as client:
        _, tokens = sign_in(client)
        yield client, moodle, tokens["access_token"]


def create_link(client, access_token):
    result = call_tool(
        client,
        access_token,
        "create_upload_link",
        {"course_id": COURSE_ID, "assignment_id": ASSIGNMENT_ID},
    )
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def sealed_of(link):
    return parse_qs(urlsplit(link["upload_url"]).query)["request"][0]


def post_file(client, sealed, name="tugas.pdf", data=b"isi", **fields):
    return client.post(
        "/upload",
        data={"request": sealed, "step": "save", **fields},
        files={"file": (name, data, "application/pdf")},
    )


def post_final(client, sealed, **fields):
    return client.post(
        "/upload",
        data={"request": sealed, "step": "final", **fields},
        files={"unused": ("", b"")},
    )


def final_request_of(page):
    return html.unescape(re.search(r'name="request" value="([^"]+)"', page).group(1))


def tool_names(client, access_token):
    response = mcp(client, "tools/list", access_token=access_token)
    return {tool["name"] for tool in response.json()["result"]["tools"]}


def test_write_features_are_off_by_default():
    moodle = FakeMoodle(users=USERS)
    with make_client(moodle, enable_write=False) as client:
        _, tokens = sign_in(client)
        names = tool_names(client, tokens["access_token"])
        assert client.get("/upload", params={"request": "x"}).status_code == 404

    assert "create_upload_link" not in names
    assert {"list_assignments", "get_assignment"} <= names


def test_online_mode_has_link_tool_but_no_direct_upload(setup):
    client, _, access_token = setup

    names = tool_names(client, access_token)

    assert "create_upload_link" in names
    assert "save_assignment_file" not in names
    assert "submit_assignment" not in names


def test_creating_link_uploads_nothing_and_hides_token(setup):
    client, moodle, access_token = setup

    link = create_link(client, access_token)

    assert link["upload_url"].startswith(f"{PUBLIC_URL}/upload?request=")
    assert TOKEN_ANI not in link["upload_url"]
    assert moodle.uploads == []


@pytest.mark.parametrize("setup", [{"can_edit": False}], indirect=True)
def test_no_link_for_assignment_that_cannot_be_changed(setup):
    client, _, access_token = setup

    result = call_tool(
        client,
        access_token,
        "create_upload_link",
        {"course_id": COURSE_ID, "assignment_id": ASSIGNMENT_ID},
    )

    assert result["isError"] is True
    assert "tidak bisa diubah" in result["content"][0]["text"]


def test_page_warns_when_assignment_has_no_draft_stage(setup):
    client, moodle, access_token = setup

    response = client.get("/upload", params={"request": sealed_of(create_link(client, access_token))})

    assert response.status_code == 200
    assert "Tugas &amp; Latihan" in response.text
    assert "Data Mining Advance" in response.text
    assert "Minggu 3" in response.text
    assert "tidak punya tahap draft" in response.text
    assert 'name="confirm_immediate" value="yes" required' in response.text
    assert TOKEN_ANI not in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert moodle.uploads == []


def test_upload_without_confirmation_does_not_submit(setup):
    client, moodle, access_token = setup

    response = post_file(client, sealed_of(create_link(client, access_token)))

    assert response.status_code == 400
    assert "langsung terkumpul" in response.text
    assert moodle.uploads == []
    assert moodle.status == "new"


def test_confirmed_upload_submits_and_link_cannot_be_reused(setup):
    client, moodle, access_token = setup
    sealed = sealed_of(create_link(client, access_token))

    response = post_file(client, sealed, confirm_immediate="yes")

    assert response.status_code == 200
    assert "Tugas terkumpul" in response.text
    assert "tugas.pdf" in response.text
    assert moodle.status == "submitted"

    again = post_file(client, sealed, confirm_immediate="yes", replace="yes")
    assert again.status_code == 400
    assert "tidak berlaku" in again.text
    assert moodle.uploads == ["tugas.pdf"]


@pytest.mark.parametrize("setup", [{"drafts": True}], indirect=True)
def test_draft_flow_needs_second_click_to_send(setup):
    client, moodle, access_token = setup

    saved = post_file(client, sealed_of(create_link(client, access_token)))

    assert saved.status_code == 200
    assert "Draft tersimpan" in saved.text
    assert "belum terkirim ke dosen" in saved.text
    assert moodle.status == "draft"

    final_request = final_request_of(saved.text)
    sent = post_final(client, final_request)

    assert sent.status_code == 200
    assert "Tugas terkumpul" in sent.text
    assert moodle.status == "submitted"

    assert post_final(client, final_request).status_code == 400


@pytest.mark.parametrize(
    "setup", [{"drafts": True, "statement": "Ini karya saya sendiri"}], indirect=True
)
def test_final_step_needs_statement_from_user(setup):
    client, moodle, access_token = setup
    saved = post_file(client, sealed_of(create_link(client, access_token)))

    assert "Ini karya saya sendiri" in saved.text
    assert 'name="accept_statement" value="yes" required' in saved.text

    final_request = final_request_of(saved.text)
    refused = post_final(client, final_request)
    assert refused.status_code == 400
    assert moodle.status == "draft"

    assert post_final(client, final_request, accept_statement="yes").status_code == 200
    assert moodle.status == "submitted"


@pytest.mark.parametrize("setup", [{"drafts": True, "existing": ["lama.pdf"]}], indirect=True)
def test_existing_file_needs_replace_confirmation(setup):
    client, moodle, access_token = setup
    sealed = sealed_of(create_link(client, access_token))

    page = client.get("/upload", params={"request": sealed}).text
    assert "lama.pdf" in page
    assert 'name="replace" value="yes" required' in page

    refused = post_file(client, sealed)
    assert refused.status_code == 400
    assert moodle.uploads == []

    assert post_file(client, sealed, replace="yes").status_code == 200
    assert moodle.files == ["tugas.pdf"]


@pytest.mark.parametrize("setup", [{"drafts": True, "file_types": ".pdf"}], indirect=True)
def test_failed_upload_keeps_link_usable(setup):
    client, moodle, access_token = setup
    sealed = sealed_of(create_link(client, access_token))

    refused = post_file(client, sealed, name="virus.exe")
    assert refused.status_code == 400
    assert "hanya menerima" in refused.text
    assert moodle.uploads == []

    assert post_file(client, sealed).status_code == 200


@pytest.mark.parametrize("setup", [{"drafts": True}], indirect=True)
def test_missing_file_is_explained(setup):
    client, moodle, access_token = setup

    response = client.post(
        "/upload",
        data={"request": sealed_of(create_link(client, access_token)), "step": "save"},
        files={"unused": ("", b"")},
    )

    assert response.status_code == 400
    assert "Pilih file" in response.text
    assert moodle.uploads == []


@pytest.mark.parametrize("setup", [{"drafts": True}], indirect=True)
def test_file_name_is_escaped_in_result_page(setup):
    client, _, access_token = setup

    response = post_file(
        client, sealed_of(create_link(client, access_token)), name="<img src=x>.pdf"
    )

    assert response.status_code == 200
    assert "<img src=x" not in response.text


def test_oversized_upload_is_rejected_before_reading(setup):
    client, moodle, access_token = setup
    sealed = sealed_of(create_link(client, access_token))

    response = post_file(client, sealed, data=b"x" * (MAX_UPLOAD_BYTES + 100_000))

    assert response.status_code == 413
    assert moodle.uploads == []


@pytest.mark.parametrize("value", ["", "palsu"])
def test_forged_link_is_rejected(setup, value):
    client, moodle, _ = setup

    assert client.get("/upload", params={"request": value}).status_code == 400
    assert post_file(client, value, confirm_immediate="yes").status_code == 400
    assert moodle.uploads == []


def test_upload_link_is_not_marked_read_only(setup):
    client, _, access_token = setup

    response = mcp(client, "tools/list", access_token=access_token)
    tools = {tool["name"]: tool for tool in response.json()["result"]["tools"]}

    assert tools["create_upload_link"]["annotations"]["readOnlyHint"] is False


def test_upload_link_from_an_older_generation_is_rejected():
    from lms_mcp.upload_flow import UploadFlow

    sealer = Sealer(SECRET)
    old = UploadFlow(sealer=sealer, public_url=PUBLIC_URL, operations_for=lambda _token: None)
    sealed = old._seal("upload", TOKEN_ANI, COURSE_ID, ASSIGNMENT_ID)
    current = UploadFlow(
        sealer=sealer,
        public_url=PUBLIC_URL,
        operations_for=lambda _token: None,
        generation=1,
    )

    assert current._open("upload", sealed) is None
    assert current._open("upload", current._seal("upload", TOKEN_ANI, COURSE_ID, ASSIGNMENT_ID))


def test_other_sealed_values_cannot_be_used_as_upload_link(setup):
    client, moodle, access_token = setup
    sealer = Sealer(SECRET)
    data = {
        "id": "x",
        "lms_token": TOKEN_ANI,
        "course_id": COURSE_ID,
        "assignment_id": ASSIGNMENT_ID,
        "exp": 9999999999,
    }

    response = post_file(client, sealer.seal("access", data), confirm_immediate="yes")

    assert response.status_code == 400
    assert moodle.uploads == []
    # Tautan upload juga tidak boleh dipakai sebagai access token.
    link = sealed_of(create_link(client, access_token))
    assert mcp(client, "tools/list", access_token=link).status_code == 401


def test_expired_link_is_rejected(setup):
    client, moodle, _ = setup
    expired = Sealer(SECRET).seal(
        "upload",
        {
            "id": "y",
            "lms_token": TOKEN_ANI,
            "course_id": COURSE_ID,
            "assignment_id": ASSIGNMENT_ID,
            "exp": 1,
        },
    )

    assert post_file(client, expired, confirm_immediate="yes").status_code == 400
    assert moodle.uploads == []


def test_upload_uses_the_token_of_signed_in_user(setup):
    client, moodle, access_token = setup
    moodle.calls.clear()

    post_file(client, sealed_of(create_link(client, access_token)), confirm_immediate="yes")

    assert {body["wstoken"][0] for _, body in moodle.calls} == {TOKEN_ANI}
