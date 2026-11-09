import httpx

from lms_mcp.confirm import ask_user
from lms_mcp.pages import download_confirm_page


def _place():
    return {
        "course": "Data Mining Advance",
        "course_status": "sedang berjalan",
        "section": "Minggu 3",
        "activity": "Slide preprocessing",
        "activity_url": "https://lms.contoh.test/mod/resource/view.php?id=1",
        "file_name": "<b>slide</b>.pdf",
        "size_bytes": 2048,
        "modified": "Sabtu, 7 November 2026 04.20 WIB",
    }


def test_cancel_keeps_the_token_out_of_the_page_and_escapes_the_name():
    seen = {}

    def opener(url):
        seen["url"] = url
        page = httpx.get(url)
        seen["page"] = page.text
        httpx.post(url, data={"decision": "cancel"})

    answer = ask_user(download_confirm_page(_place(), r"D:\Unduhan"), open_browser=opener)

    token = seen["url"].rsplit("/", 1)[-1]
    assert answer.choice == "cancel"
    assert token not in seen["page"]
    assert "<b>slide</b>" not in seen["page"]
    assert "Data Mining Advance" in seen["page"]
    assert "Minggu 3" in seen["page"]
    assert "AI tidak bisa menekan tombol ini" in seen["page"]


def test_allow_returns_the_checkbox_the_user_ticked():
    def opener(url):
        httpx.post(url, data={"decision": "allow", "confirm_immediate": "yes"})

    answer = ask_user("<p>ya</p>", open_browser=opener)

    assert answer.choice == "allow"
    assert answer.values["confirm_immediate"] == "yes"


def test_a_second_click_cannot_change_the_decision():
    def opener(url):
        assert httpx.get(url + "salah").status_code == 404
        httpx.post(url, data={"decision": "cancel"})
        again = httpx.post(url, data={"decision": "allow"})
        assert again.status_code == 409

    answer = ask_user("<p>sekali</p>", open_browser=opener)

    assert answer.choice == "cancel"


def test_nobody_clicking_does_not_allow_the_action():
    answer = ask_user("<p>tunggu</p>", timeout=0.2, open_browser=lambda _url: True)

    assert answer.choice == "timeout"


def test_a_browser_that_does_not_open_does_not_allow_the_action():
    def opener(_url):
        raise OSError("tidak ada browser")

    answer = ask_user("<p>gagal</p>", open_browser=opener)

    assert answer.choice == "unopened"
