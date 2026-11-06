import base64

import pytest

from lmstelkom_mcp.auth import TokenError, token_from_env

SIGNATURE = "a" * 32
TOKEN = "f" * 32


def encode(text):
    return base64.b64encode(text.encode()).decode()


# Panjang isinya menghasilkan padding "=", jadi kasus URL-encoded ikut teruji.
VALID = encode(f"{SIGNATURE}:::{TOKEN}:::rahasia")


@pytest.mark.parametrize(
    "value",
    [
        f"moodlemobile://token={VALID}",
        f"  moodlemobile://token={VALID}  \n",
        f"Failed to launch 'moodlemobile://token={VALID}' because the scheme "
        "does not have a registered handler.",
        f"celoestudent://token={VALID}",
        f"token={VALID}",
        "moodlemobile://token=" + VALID.replace("=", "%3D"),
        "moodlemobile://token=" + VALID.rstrip("="),
        "moodlemobile://token=" + encode(f"{SIGNATURE}:::{TOKEN}"),
    ],
)
def test_token_from_env_accepts_link_forms(value):
    assert token_from_env(value) == TOKEN


@pytest.mark.parametrize(
    "value",
    [
        f"  {TOKEN}\n",
        f"'{TOKEN}'",
        f'"{TOKEN}"',
        f"LMS_TOKEN={TOKEN}",
        f"LMS_TOKEN='{TOKEN}'",
        f"  LMS_TOKEN = '{TOKEN}'  \r\n",
        f"export LMS_TOKEN={TOKEN}",
        f"LMS_TOKEN='moodlemobile://token={VALID}'",
        f"'moodlemobile://token={VALID}'",
    ],
)
def test_token_from_env_accepts_copies_from_env_file(value):
    assert token_from_env(value) == TOKEN


@pytest.mark.parametrize(
    "value",
    [
        "",
        "tokenpalsu",
        "f" * 31,
        "f" * 33,
        "g" * 32,
        f"{TOKEN} {TOKEN}",
        "LMS_TOKEN=",
        "moodlemobile://token=!!!",
        "moodlemobile://token=" + encode("tanpa-pemisah"),
        "moodlemobile://token=" + encode(f"{SIGNATURE}:::"),
        "moodlemobile://token=" + encode(f"{SIGNATURE}:::bukan-token-hex"),
        "moodlemobile://token=" + base64.b64encode(b"\xff\xfe").decode(),
    ],
)
def test_token_from_env_rejects_broken_values(value):
    with pytest.raises(TokenError) as error:
        token_from_env(value)
    assert "moodlemobile" not in str(error.value)
    assert "tokenpalsu" not in str(error.value)
