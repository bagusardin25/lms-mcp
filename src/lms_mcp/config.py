"""Memuat konfigurasi dari .env di root proyek."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_BASE_URL = "https://lms.telkomuniversity.ac.id"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "lms-mcp"
# Di luar folder proyek, supaya AI yang bisa membuka folder proyek tidak ikut membacanya.
DEFAULT_TOKEN_FILE = Path.home() / ".lms-mcp" / "token.txt"
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


def read_settings(env_path: Path | None = None) -> dict[str, str | None]:
    """Variabel environment mengalahkan nilai di .env."""
    return {**dotenv_values(env_path or ENV_PATH), **os.environ}


def base_url_from(values: dict[str, str | None]) -> str:
    return (values.get("LMS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def token_file(values: dict[str, str | None]) -> Path:
    """File kunci masuk: yang disebut di LMS_TOKEN_FILE, atau file bawaan lms-mcp login."""
    configured = (values.get("LMS_TOKEN_FILE") or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_TOKEN_FILE


def save_token(path: Path, token: str) -> None:
    """Menyimpan kunci masuk. Di macOS dan Linux, hanya pemilik akun yang bisa membacanya."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_token_file(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConfigError(
            f"File kunci masuk tidak bisa dibaca: {path}. Periksa LMS_TOKEN_FILE, "
            "atau jalankan lms-mcp login."
        ) from error
    # PowerShell lama menyimpan hasil `echo ... > file` sebagai UTF-16, dan Notepad lama
    # menaruh penanda di awal file UTF-8. Keduanya tetap harus terbaca.
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        return raw.decode(encoding).strip()
    except UnicodeDecodeError as error:
        raise ConfigError(
            f"File kunci masuk harus berisi teks biasa: {path}. Jalankan lms-mcp login "
            "untuk membuatnya ulang."
        ) from error


def _token_value(values: dict[str, str | None]) -> str | None:
    """LMS_TOKEN menang kalau diisi. Kalau kosong, kunci masuk dibaca dari file."""
    direct = (values.get("LMS_TOKEN") or "").strip()
    if direct:
        return direct
    path = token_file(values)
    # File bawaan boleh belum ada. File yang disebut di LMS_TOKEN_FILE harus ada.
    if not (values.get("LMS_TOKEN_FILE") or "").strip() and not path.is_file():
        return None
    return _read_token_file(path) or None


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
    values = read_settings(env_path)
    download_dir = values.get("LMS_DOWNLOAD_DIR")
    upload_dirs = values.get("LMS_UPLOAD_DIRS") or ""
    return Config(
        base_url=base_url_from(values),
        token=_token_value(values),
        download_dir=Path(download_dir).expanduser() if download_dir else DEFAULT_DOWNLOAD_DIR,
        enable_write=_is_enabled(values.get("LMS_ENABLE_WRITE")),
        upload_dirs=tuple(
            Path(item.strip()).expanduser() for item in upload_dirs.split(",") if item.strip()
        )
        or DEFAULT_UPLOAD_DIRS,
    )
