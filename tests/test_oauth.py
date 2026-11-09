import base64
import hashlib
import html
import json
import re
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from starlette.testclient import TestClient

from lms_mcp import oauth
from lms_mcp.config import ConfigError, HttpConfig, load_http_config
from lms_mcp.moodle import MoodleClient
from lms_mcp.oauth import Sealer
from lms_mcp.server import build_http_server, http_transport_options

PUBLIC_URL = "https://mcp.contoh.test"
LMS_URL = "https://lms.contoh.test"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
SECRET = "r" * 40
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)
TOKEN_ANI = "a" * 32
TOKEN_BUDI = "b" * 32
TOKEN_REJECTED = "c" * 32
USERS = {TOKEN_ANI: "Ani", TOKEN_BUDI: "Budi"}
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-11-25",
}


def lms_link(token):
    payload = f"{'a' * 32}:::{token}".encode()
    return "moodlemobile://token=" + base64.b64encode(payload).decode()


def fake_lms(request):
    body = parse_qs(request.content.decode())
    name = USERS.get(body["wstoken"][0])
    if name is None:
        return httpx.Response(
            200,
            json={
                "exception": "moodle_exception",
                "errorcode": "invalidtoken",
                "message": "Invalid token",
            },
        )
    return httpx.Response(
        200,
        json={
            "fullname": name,
            "username": name.lower(),
            "userid": len(name),
            "sitename": "LMS",
            "siteurl": LMS_URL,
            "release": "4.5",
        },
    )


def make_app(config=None):
    config = config or HttpConfig(LMS_URL, PUBLIC_URL, SECRET)
    server = build_http_server(
        config,
        create_lms_client=lambda token: MoodleClient(LMS_URL, token, httpx.MockTransport(fake_lms)),
    )
    return server.streamable_http_app(**http_transport_options(config))


@pytest.fixture
def client():
    with TestClient(make_app(), base_url=PUBLIC_URL, follow_redirects=False) as test_client:
        yield test_client


def register(client, redirect=REDIRECT, **extra):
    return client.post(
        "/register",
        json={
            "redirect_uris": [redirect],
            "client_name": "Claude",
            "token_endpoint_auth_method": "none",
            **extra,
        },
    )


def authorize(client, client_id, redirect=REDIRECT, state="state-1", scope="lms"):
    return client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect,
            "state": state,
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
            "scope": scope,
        },
    )


def login_request(client, client_id):
    response = authorize(client, client_id)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(f"{PUBLIC_URL}/login?")
    return parse_qs(urlsplit(location).query)["request"][0]


def submit_login(client, request, link):
    return client.post("/login", data={"request": request, "lms_link": link})


def get_code(client, client_id, token=TOKEN_ANI):
    response = submit_login(client, login_request(client, client_id), lms_link(token))
    assert response.status_code == 303
    return parse_qs(urlsplit(response.headers["location"]).query)["code"][0]


def exchange(client, client_id, code, verifier=VERIFIER):
    return client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
        },
    )


def sign_in(client, token=TOKEN_ANI):
    client_id = register(client).json()["client_id"]
    tokens = exchange(client, client_id, get_code(client, client_id, token)).json()
    return client_id, tokens


def mcp(client, method, params=None, access_token=None):
    headers = dict(MCP_HEADERS)
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def call_tool(client, access_token, name, arguments=None):
    response = mcp(
        client, "tools/call", {"name": name, "arguments": arguments or {}}, access_token
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_request_without_token_points_to_login(client):
    response = mcp(client, "tools/list")

    assert response.status_code == 401
    assert "oauth-protected-resource" in response.headers["www-authenticate"]


def test_metadata_advertises_registration_and_scopes(client):
    metadata = client.get("/.well-known/oauth-authorization-server").json()

    assert metadata["registration_endpoint"] == f"{PUBLIC_URL}/register"
    assert metadata["authorization_endpoint"] == f"{PUBLIC_URL}/authorize"
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "offline_access" in metadata["scopes_supported"]

    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert resource["resource"] == f"{PUBLIC_URL}/mcp"


@pytest.mark.parametrize(
    "redirect",
    [
        "https://claude.ai/api/mcp/auth_callback",
        "https://claude.com/api/mcp/auth_callback",
        "https://chatgpt.com/connector_platform_oauth_redirect",
        "http://localhost:53123/callback",
        "http://127.0.0.1:53123/callback",
    ],
)
def test_register_accepts_known_clients(client, redirect):
    assert register(client, redirect).status_code == 201


@pytest.mark.parametrize(
    "redirect",
    [
        "https://penyerang.test/callback",
        "https://claude.ai.penyerang.test/callback",
        "http://claude.ai/api/mcp/auth_callback",
    ],
)
def test_register_rejects_unknown_redirect(client, redirect):
    response = register(client, redirect)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


def test_extra_redirect_host_can_be_allowed():
    config = HttpConfig(
        LMS_URL, PUBLIC_URL, SECRET, extra_redirect_hosts=frozenset({"www.perplexity.ai"})
    )
    with TestClient(make_app(config), base_url=PUBLIC_URL) as test_client:
        assert register(test_client, "https://www.perplexity.ai/callback").status_code == 201


def test_client_without_registered_scope_can_request_offline_access(client):
    client_id = register(client).json()["client_id"]

    response = authorize(client, client_id, scope="lms offline_access")

    assert response.status_code == 302
    assert response.headers["location"].startswith(f"{PUBLIC_URL}/login?")


def test_unknown_scope_is_rejected(client):
    client_id = register(client).json()["client_id"]

    response = authorize(client, client_id, scope="lms hapus_semua")

    assert "error=invalid_scope" in response.headers["location"]


def test_login_page_shows_client_and_target_safely(client):
    client_id = register(client, client_name="<script>alert(1)</script>").json()["client_id"]

    response = client.get("/login", params={"request": login_request(client, client_id)})

    assert response.status_code == 200
    assert "<script>" not in response.text
    assert html.escape("<script>alert(1)</script>") in response.text
    assert "claude.ai" in response.text
    assert "confirmed=1" in html.unescape(response.text)
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_login_form_posts_back_to_login(client):
    client_id = register(client).json()["client_id"]
    page = client.get("/login", params={"request": login_request(client, client_id)}).text

    sealed = html.unescape(re.search(r'name="request" value="([^"]+)"', page).group(1))
    action = re.search(r'<form method="post" action="([^"]+)"', page).group(1)

    response = client.post(action, data={"request": sealed, "lms_link": lms_link(TOKEN_ANI)})
    assert response.status_code == 303


@pytest.mark.parametrize(
    "pasted",
    [
        TOKEN_ANI,
        f"'{TOKEN_ANI}'",
        f"LMS_TOKEN='{TOKEN_ANI}'",
        lms_link(TOKEN_ANI),
    ],
)
def test_login_accepts_token_copied_from_env_file(client, pasted):
    client_id = register(client).json()["client_id"]

    response = submit_login(client, login_request(client, client_id), pasted)

    assert response.status_code == 303
    code = parse_qs(urlsplit(response.headers["location"]).query)["code"][0]
    tokens = exchange(client, client_id, code).json()
    result = call_tool(client, tokens["access_token"], "get_profile")
    assert "Ani" in result["content"][0]["text"]


def test_login_redirects_with_code_and_state(client):
    client_id = register(client).json()["client_id"]

    response = submit_login(client, login_request(client, client_id), lms_link(TOKEN_ANI))

    assert response.status_code == 303
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
    query = parse_qs(location.query)
    assert query["state"] == ["state-1"]
    assert TOKEN_ANI not in response.headers["location"]


@pytest.mark.parametrize(
    "link, message",
    [
        ("", "belum diisi"),
        ("moodlemobile://token=!!!", "tidak terbaca"),
        (lms_link(TOKEN_REJECTED), "menolak token"),
    ],
)
def test_login_rejects_bad_token_without_echoing_it(client, link, message):
    client_id = register(client).json()["client_id"]

    response = submit_login(client, login_request(client, client_id), link)

    assert response.status_code == 400
    assert message in response.text
    assert "location" not in response.headers
    if link:
        assert link not in response.text


@pytest.mark.parametrize("request_value", ["", "palsu"])
def test_login_rejects_forged_request(client, request_value):
    response = submit_login(client, request_value, lms_link(TOKEN_ANI))

    assert response.status_code == 400
    assert "tidak berlaku" in response.text


def test_login_limits_attempts(client, monkeypatch):
    client_id = register(client).json()["client_id"]
    request = login_request(client, client_id)
    limit = oauth.LOGIN_ATTEMPTS_PER_MINUTE

    for _ in range(limit):
        assert submit_login(client, request, lms_link(TOKEN_REJECTED)).status_code == 400

    assert submit_login(client, request, lms_link(TOKEN_ANI)).status_code == 429


def test_code_exchange_issues_tokens_without_exposing_lms_token(client):
    client_id, tokens = sign_in(client)

    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] == oauth.ACCESS_TOKEN_SECONDS
    assert tokens["refresh_token"]
    assert "lms" in tokens["scope"].split()
    assert TOKEN_ANI not in json.dumps(tokens)
    assert TOKEN_ANI not in client_id


def test_code_needs_correct_pkce_verifier(client):
    client_id = register(client).json()["client_id"]

    response = exchange(client, client_id, get_code(client, client_id), verifier="x" * 64)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


def test_code_works_only_once(client):
    client_id = register(client).json()["client_id"]
    code = get_code(client, client_id)

    assert exchange(client, client_id, code).status_code == 200
    assert exchange(client, client_id, code).status_code == 400


def test_code_cannot_be_used_by_other_client(client):
    owner = register(client).json()["client_id"]
    other = register(client).json()["client_id"]

    response = exchange(client, other, get_code(client, owner))

    assert response.status_code == 400


def test_tools_use_token_of_signed_in_user(client):
    _, ani = sign_in(client, TOKEN_ANI)
    _, budi = sign_in(client, TOKEN_BUDI)

    ani_result = call_tool(client, ani["access_token"], "get_profile")
    budi_result = call_tool(client, budi["access_token"], "get_profile")

    assert "Ani" in ani_result["content"][0]["text"]
    assert "Budi" in budi_result["content"][0]["text"]


def test_server_ignores_owner_token_in_environment(monkeypatch):
    monkeypatch.setenv("LMS_TOKEN", TOKEN_BUDI)
    with TestClient(make_app(), base_url=PUBLIC_URL, follow_redirects=False) as test_client:
        _, ani = sign_in(test_client, TOKEN_ANI)
        result = call_tool(test_client, ani["access_token"], "get_profile")

    assert "Ani" in result["content"][0]["text"]
    assert "Budi" not in result["content"][0]["text"]


def test_remote_tools_replace_download_with_link(client):
    _, tokens = sign_in(client)

    response = mcp(client, "tools/list", access_token=tokens["access_token"])
    names = {tool["name"] for tool in response.json()["result"]["tools"]}

    assert names == {
        "get_profile",
        "list_courses",
        "get_upcoming_deadlines",
        "get_course_materials",
        "read_file_text",
        "list_assignments",
        "get_assignment",
        "get_file_link",
    }


def test_file_link_uses_browser_path_without_token(client):
    _, tokens = sign_in(client)

    result = call_tool(
        client,
        tokens["access_token"],
        "get_file_link",
        {"file_url": f"{LMS_URL}/webservice/pluginfile.php/1/mod_resource/content/1/a%20b.pdf"},
    )

    link = json.loads(result["content"][0]["text"])
    assert link["url"] == f"{LMS_URL}/pluginfile.php/1/mod_resource/content/1/a%20b.pdf"
    assert link["file_name"] == "a b.pdf"
    assert "token" not in link["url"]


def test_file_link_rejects_other_host(client):
    _, tokens = sign_in(client)

    result = call_tool(
        client,
        tokens["access_token"],
        "get_file_link",
        {"file_url": "https://penyerang.test/webservice/pluginfile.php/1/a.pdf"},
    )

    assert result["isError"] is True


def test_forged_access_token_is_rejected(client):
    assert mcp(client, "tools/list", access_token="palsu").status_code == 401


def test_token_sealed_with_other_secret_is_rejected(client):
    other = Sealer("s" * 40).seal(
        "access",
        {
            "client_id": "x",
            "scopes": ["lms"],
            "resource": None,
            "subject": "1",
            "lms_token": TOKEN_ANI,
            "exp": 9999999999,
        },
    )
    assert mcp(client, "tools/list", access_token=other).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client):
    _, tokens = sign_in(client)

    assert mcp(client, "tools/list", access_token=tokens["refresh_token"]).status_code == 401


def test_expired_access_token_is_rejected(client):
    expired = Sealer(SECRET).seal(
        "access",
        {
            "client_id": "x",
            "scopes": ["lms"],
            "resource": None,
            "subject": "1",
            "lms_token": TOKEN_ANI,
            "exp": 1,
        },
    )
    assert mcp(client, "tools/list", access_token=expired).status_code == 401


def test_refresh_issues_working_access_token(client):
    client_id, tokens = sign_in(client)

    response = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": tokens["refresh_token"],
        },
    )

    assert response.status_code == 200, response.text
    result = call_tool(client, response.json()["access_token"], "get_profile")
    assert "Ani" in result["content"][0]["text"]

    again = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": tokens["refresh_token"],
        },
    )
    assert again.status_code != 200


def test_revoked_token_stops_working(client):
    client_id, tokens = sign_in(client)

    # SDK mewajibkan field client_secret ada, walaupun klien publik tidak punya secret.
    response = client.post(
        "/revoke",
        data={"client_id": client_id, "client_secret": "", "token": tokens["access_token"]},
    )

    assert response.status_code == 200
    assert mcp(client, "tools/list", access_token=tokens["access_token"]).status_code == 401


def test_invalid_host_is_rejected():
    with TestClient(make_app(), base_url="https://lain.test", follow_redirects=False) as test_client:
        _, tokens = sign_in(test_client)
        response = mcp(test_client, "tools/list", access_token=tokens["access_token"])
    assert response.status_code == 421


def test_health_check_is_public(client):
    assert client.get("/healthz").text == "ok"


def test_sealer_rejects_wrong_kind():
    sealer = Sealer(SECRET)
    assert sealer.unseal("access", sealer.seal("refresh", {"a": 1})) is None
    assert sealer.unseal("refresh", sealer.seal("refresh", {"a": 1})) == {"a": 1}


def test_http_config_requires_url_and_strong_secret(tmp_path, monkeypatch):
    for name in (
        "LMS_PUBLIC_URL",
        "LMS_SERVER_SECRET",
        "PORT",
        "LMS_EXTRA_REDIRECT_HOSTS",
        "LMS_TOKEN_GENERATION",
    ):
        monkeypatch.delenv(name, raising=False)
    env_path = tmp_path / ".env"

    with pytest.raises(ConfigError):
        load_http_config(env_path)

    env_path.write_text("LMS_PUBLIC_URL=https://mcp.contoh.test/\nLMS_SERVER_SECRET=pendek\n")
    with pytest.raises(ConfigError):
        load_http_config(env_path)

    env_path.write_text(
        f"LMS_PUBLIC_URL=https://mcp.contoh.test/\nLMS_SERVER_SECRET={SECRET}\n"
        "PORT=9000\nLMS_EXTRA_REDIRECT_HOSTS=a.test, B.test\n"
    )
    config = load_http_config(env_path)
    assert config.public_url == "https://mcp.contoh.test"
    assert config.port == 9000
    assert config.extra_redirect_hosts == {"a.test", "b.test"}
    assert config.token_generation == 0

    env_path.write_text(
        f"LMS_PUBLIC_URL=https://mcp.contoh.test/\nLMS_SERVER_SECRET={SECRET}\n"
        "LMS_TOKEN_GENERATION=2\n"
    )
    assert load_http_config(env_path).token_generation == 2

    env_path.write_text(
        f"LMS_PUBLIC_URL=https://mcp.contoh.test/\nLMS_SERVER_SECRET={SECRET}\n"
        "LMS_TOKEN_GENERATION=baru\n"
    )
    with pytest.raises(ConfigError):
        load_http_config(env_path)


@pytest.mark.parametrize(
    "path, media_type, signature",
    [
        ("/favicon.ico", "image/x-icon", b"\x00\x00\x01\x00"),
        ("/icon-64.png", "image/png", b"\x89PNG"),
        ("/icon-256.png", "image/png", b"\x89PNG"),
    ],
)
def test_icons_are_public_without_login(client, path, media_type, signature):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
    assert response.content.startswith(signature)
    assert "max-age" in response.headers["cache-control"]


def test_server_info_advertises_hosted_icons(client):
    _, tokens = sign_in(client)

    response = mcp(
        client,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "uji", "version": "1"},
        },
        tokens["access_token"],
    )

    icons = response.json()["result"]["serverInfo"]["icons"]
    assert {icon["src"] for icon in icons} == {
        f"{PUBLIC_URL}/icon-256.png",
        f"{PUBLIC_URL}/icon-64.png",
    }


def test_login_page_can_show_its_own_icon_only(client):
    client_id = register(client).json()["client_id"]

    response = client.get("/login", params={"request": login_request(client, client_id)})

    assert 'src="/icon-64.png"' in response.text
    assert 'href="/favicon.ico"' in response.text
    assert "img-src 'self'" in response.headers["content-security-policy"]


def test_login_page_title_shows_client_name_once_escaped(client):
    client_id = register(client, client_name="A & B").json()["client_id"]

    page = client.get("/login", params={"request": login_request(client, client_id)}).text

    assert "<title>Hubungkan LMS ke A &amp; B</title>" in page
    assert "&amp;amp;" not in page


def test_login_page_is_clear_about_who_gets_access_and_status(client):
    client_id = register(client).json()["client_id"]

    page = client.get("/login", params={"request": login_request(client, client_id)}).text

    assert "Hubungkan LMS ke Claude" in page
    assert "<code>claude.ai</code>" in page
    assert REDIRECT in page
    assert "hanya membaca" in page
    assert "Tidak resmi" in page
    assert "tidak berafiliasi" in page
    assert '<label for="lms_link">' in page
    assert "<script" not in page


def test_login_page_warns_about_loopback_and_write_mode():
    redirect = "http://127.0.0.1:9/callback"
    config = HttpConfig(LMS_URL, PUBLIC_URL, SECRET, enable_write=True)
    with TestClient(make_app(config), base_url=PUBLIC_URL, follow_redirects=False) as client:
        client_id = register(client, redirect=redirect).json()["client_id"]
        started = authorize(client, client_id, redirect=redirect)
        request = parse_qs(urlsplit(started.headers["location"]).query)["request"][0]
        page = client.get("/login", params={"request": request}).text

    assert redirect in page
    assert "komputermu sendiri" in page
    assert "mengizinkan pengumpulan tugas" in page
    assert "hanya membaca" not in page


def test_old_token_dies_when_generation_changes():
    config = HttpConfig(LMS_URL, PUBLIC_URL, SECRET, token_generation=1)
    with TestClient(make_app(config), base_url=PUBLIC_URL, follow_redirects=False) as client:
        _, tokens = sign_in(client)
        assert mcp(client, "tools/list", access_token=tokens["access_token"]).status_code == 200
        stale = Sealer(SECRET).seal(
            "access",
            {
                "client_id": "x",
                "scopes": ["lms"],
                "resource": None,
                "subject": "1",
                "lms_token": TOKEN_ANI,
                "gen": 0,
                "exp": 9999999999,
            },
        )
        assert mcp(client, "tools/list", access_token=stale).status_code == 401


def test_expired_login_page_explains_next_step(client):
    response = client.get("/login", params={"request": "palsu"})

    assert response.status_code == 400
    assert "Ulangi dari aplikasi AI" in response.text
    assert "Tidak resmi" in response.text
