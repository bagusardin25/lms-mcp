from pathlib import Path

import pytest

from lms_mcp.config import (
    DEFAULT_BASE_URL,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_UPLOAD_DIRS,
    load_config,
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
