import pytest


@pytest.fixture(autouse=True)
def isolate_audit_log(tmp_path, monkeypatch):
    """Catatan aksi tidak boleh tertulis di folder rumah saat tes berjalan."""
    monkeypatch.setenv("LMS_AUDIT_LOG", str(tmp_path / "audit.log"))


@pytest.fixture(autouse=True)
def isolate_token_file(tmp_path, monkeypatch):
    """Tes tidak boleh membaca atau menimpa kunci masuk sungguhan di folder rumah."""
    monkeypatch.setattr("lms_mcp.config.DEFAULT_TOKEN_FILE", tmp_path / "rumah" / "token.txt")
