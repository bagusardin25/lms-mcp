"""Memuat konfigurasi dari .env di root proyek."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_BASE_URL = "https://lms.telkomuniversity.ac.id"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "lms-telkom"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
MIN_SERVER_SECRET_LENGTH = 32


@dataclass(frozen=True)
class Config:
    base_url: str
    token: str | None
    download_dir: Path = DEFAULT_DOWNLOAD_DIR


@dataclass(frozen=True)
class HttpConfig:
    base_url: str
    public_url: str
    server_secret: str
    port: int = 8000
    extra_redirect_hosts: frozenset[str] = frozenset()


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
        extra_redirect_hosts=frozenset(
            host.strip().lower() for host in extra_hosts.split(",") if host.strip()
        ),
    )


def load_config(env_path: Path = ENV_PATH) -> Config:
    """Variabel environment mengalahkan nilai di .env."""
    values = {**dotenv_values(env_path), **os.environ}
    base_url = values.get("LMS_BASE_URL") or DEFAULT_BASE_URL
    download_dir = values.get("LMS_DOWNLOAD_DIR")
    return Config(
        base_url=base_url.rstrip("/"),
        token=values.get("LMS_TOKEN") or None,
        download_dir=Path(download_dir).expanduser() if download_dir else DEFAULT_DOWNLOAD_DIR,
    )
