from pathlib import Path

import pytest

from lms_mcp import config as config_module
from lms_mcp.config import (
    DEFAULT_BASE_URL,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_UPLOAD_DIRS,
    ConfigError,
    load_config,
    save_token,
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (
        "LMS_TOKEN",
        "LMS_TOKEN_FILE",
        "LMS_BASE_URL",
        "LMS_DOWNLOAD_DIR",
        "LMS_ENABLE_WRITE",
        "LMS_UPLOAD_DIRS",
        "LMS_TOKEN_GENERATION",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_file_is_missing(tmp_path):
    config = load_config(tmp_path / ".env")

    assert config.token is None
    assert config.base_url == DEFAULT_BASE_URL
    assert config.download_dir == DEFAULT_DOWNLOAD_DIR


def test_load_values_from_file(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LMS_TOKEN=abc123\n"
        "LMS_BASE_URL=https://contoh.test/\n"
        f"LMS_DOWNLOAD_DIR={tmp_path}/unduhan\n"
    )

    config = load_config(env_path)

    assert config.token == "abc123"
    assert config.base_url == "https://contoh.test"
    assert config.download_dir == Path(f"{tmp_path}/unduhan")


def test_empty_token_counts_as_missing(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LMS_TOKEN=\n")

    assert load_config(env_path).token is None


def test_load_keeps_link_with_equals_signs_intact(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LMS_TOKEN=moodlemobile://token=QUJD+/ZA==\n")

    assert load_config(env_path).token == "moodlemobile://token=QUJD+/ZA=="


def test_write_features_are_off_unless_enabled(tmp_path):
    env_path = tmp_path / ".env"

    config = load_config(env_path)
    assert config.enable_write is False
    assert config.upload_dirs == DEFAULT_UPLOAD_DIRS

    env_path.write_text("LMS_ENABLE_WRITE=1\nLMS_UPLOAD_DIRS=/a, /b\n")
    config = load_config(env_path)
    assert config.enable_write is True
    assert config.upload_dirs == (Path("/a"), Path("/b"))

    env_path.write_text("LMS_ENABLE_WRITE=0\n")
    assert load_config(env_path).enable_write is False


def test_token_file_is_used_when_the_env_value_is_empty(tmp_path):
    token_file = tmp_path / "rahasia" / "token"
    token_file.parent.mkdir()
    token_file.write_text("moodlemobile://token=QUJD\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text(
        f'LMS_TOKEN=\nLMS_TOKEN_FILE="{token_file.as_posix()}"\n', encoding="utf-8"
    )

    assert load_config(env_path).token == "moodlemobile://token=QUJD"


def test_missing_token_file_is_explained(tmp_path):
    env_path = tmp_path / ".env"
    missing = tmp_path / "tidak-ada"
    env_path.write_text(f'LMS_TOKEN_FILE="{missing.as_posix()}"\n', encoding="utf-8")

    with pytest.raises(Exception) as error:
        load_config(env_path)

    assert "LMS_TOKEN_FILE" in str(error.value)


def test_environment_overrides_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("LMS_TOKEN=dari-file\n")
    monkeypatch.setenv("LMS_TOKEN", "dari-env")

    assert load_config(env_path).token == "dari-env"


LINK = "moodlemobile://token=QUJD"


def test_key_saved_by_login_is_found_without_any_setting(tmp_path):
    # conftest mengarahkan file bawaan ke folder sementara.
    save_token(config_module.DEFAULT_TOKEN_FILE, "f" * 32)

    assert load_config(tmp_path / ".env").token == "f" * 32


def test_env_value_wins_over_saved_key(tmp_path):
    save_token(config_module.DEFAULT_TOKEN_FILE, "f" * 32)
    env_path = tmp_path / ".env"
    env_path.write_text("LMS_TOKEN=dari-env-file\n", encoding="utf-8")

    assert load_config(env_path).token == "dari-env-file"


@pytest.mark.parametrize(
    "raw",
    [
        LINK.encode("utf-8") + b"\r\n",
        # Notepad lama menaruh penanda di awal file.
        b"\xef\xbb\xbf" + LINK.encode("utf-8"),
        # PowerShell lama: echo "tautan" > token.txt
        (LINK + "\r\n").encode("utf-16"),
    ],
)
def test_key_file_is_read_in_common_windows_encodings(tmp_path, raw):
    token_path = tmp_path / "token.txt"
    token_path.write_bytes(raw)
    env_path = tmp_path / ".env"
    env_path.write_text(f'LMS_TOKEN_FILE="{token_path.as_posix()}"\n', encoding="utf-8")

    assert load_config(env_path).token == LINK


def test_key_file_that_is_not_text_is_explained(tmp_path):
    token_path = tmp_path / "token.txt"
    token_path.write_bytes(b"\x80\x81\x82 bukan teks")
    env_path = tmp_path / ".env"
    env_path.write_text(f'LMS_TOKEN_FILE="{token_path.as_posix()}"\n', encoding="utf-8")

    with pytest.raises(ConfigError) as error:
        load_config(env_path)

    assert "teks biasa" in str(error.value)
    assert "lms-mcp login" in str(error.value)


def test_save_token_creates_the_folder_and_replaces_the_old_key(tmp_path):
    token_path = tmp_path / "belum-ada" / "token.txt"

    save_token(token_path, "a" * 32)
    save_token(token_path, "b" * 32)

    assert token_path.read_text(encoding="utf-8") == "b" * 32 + "\n"
