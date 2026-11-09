from pathlib import Path

import pytest

from lms_mcp.config import DEFAULT_BASE_URL, DEFAULT_DOWNLOAD_DIR, load_config


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("LMS_TOKEN", "LMS_BASE_URL", "LMS_DOWNLOAD_DIR"):
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


def test_environment_overrides_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("LMS_TOKEN=dari-file\n")
    monkeypatch.setenv("LMS_TOKEN", "dari-env")

    assert load_config(env_path).token == "dari-env"
