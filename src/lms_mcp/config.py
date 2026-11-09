"""Memuat konfigurasi dari .env di root proyek."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_BASE_URL = "https://lms.telkomuniversity.ac.id"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "lms-mcp"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
MIN_SERVER_SECRET_LENGTH = 32
DEFAULT_UPLOAD_DIRS = tuple(Path.home() / name for name in ("Documents", "Downloads", "Desktop"))


def _is_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "ya"}


def _generation(value: str | None) -> int:
    text = (value or "0").strip() or "0"
    if not text.isdigit():
        raise ConfigError("LMS_TOKEN_GENERATION harus bilangan bulat 0 atau lebih.")
    return int(text)


def _token_value(values: dict[str, str | None]) -> str | None:
    """LMS_TOKEN menang kalau diisi. Kalau kosong, token dibaca dari LMS_TOKEN_FILE."""
    direct = (values.get("LMS_TOKEN") or "").strip()
    if direct:
        return direct
    file_name = (values.get("LMS_TOKEN_FILE") or "").strip()
    if not file_name:
        return None
    path = Path(file_name).expanduser()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ConfigError(f"LMS_TOKEN_FILE tidak bisa dibaca: {path}.") from error
    return text or None


@dataclass(frozen=True)
class Config:
    base_url: str
    token: str | None
    download_dir: Path = DEFAULT_DOWNLOAD_DIR
    enable_write: bool = False
    upload_dirs: tuple[Path, ...] = DEFAULT_UPLOAD_DIRS


@dataclass(frozen=True)
class HttpConfig:
    base_url: str
    public_url: str
    server_secret: str
    port: int = 8000
    extra_redirect_hosts: frozenset[str] = frozenset()
    enable_write: bool = False
    token_generation: int = 0


class ConfigError(ValueError):
    pass


def load_http_config(env_path: Path = ENV_PATH) -> HttpConfig:
    """Konfigurasi mode online. LMS_TOKEN sengaja tidak dibaca di sini."""
    values = {**dotenv_values(env_path), **os.environ}

    public_url = (values.get("LMS_PUBLIC_URL") or "").rstrip("/")
    if not public_url:
        raise ConfigError("LMS_PUBLIC_URL belum diisi, contoh https://nama-server.up.railway.app")

    server_secret = values.get("LMS_SERVER_SECRET") or ""
    if len(server_secret) < MIN_SERVER_SECRET_LENGTH:
        raise ConfigError(
            f"LMS_SERVER_SECRET harus minimal {MIN_SERVER_SECRET_LENGTH} karakter acak."
        )

    extra_hosts = values.get("LMS_EXTRA_REDIRECT_HOSTS") or ""
    return HttpConfig(
        base_url=(values.get("LMS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        public_url=public_url,
        server_secret=server_secret,
        port=int(values.get("PORT") or 8000),
        enable_write=_is_enabled(values.get("LMS_ENABLE_WRITE")),
        extra_redirect_hosts=frozenset(
            host.strip().lower() for host in extra_hosts.split(",") if host.strip()
        ),
        token_generation=_generation(values.get("LMS_TOKEN_GENERATION")),
    )


def load_config(env_path: Path = ENV_PATH) -> Config:
    """Variabel environment mengalahkan nilai di .env."""
    values = {**dotenv_values(env_path), **os.environ}
    base_url = values.get("LMS_BASE_URL") or DEFAULT_BASE_URL
    download_dir = values.get("LMS_DOWNLOAD_DIR")
    upload_dirs = values.get("LMS_UPLOAD_DIRS") or ""
    return Config(
        base_url=base_url.rstrip("/"),
        token=_token_value(values),
        download_dir=Path(download_dir).expanduser() if download_dir else DEFAULT_DOWNLOAD_DIR,
        enable_write=_is_enabled(values.get("LMS_ENABLE_WRITE")),
        upload_dirs=tuple(
            Path(item.strip()).expanduser() for item in upload_dirs.split(",") if item.strip()
        )
        or DEFAULT_UPLOAD_DIRS,
    )
