import pytest


@pytest.fixture(autouse=True)
def isolate_audit_log(tmp_path, monkeypatch):
    """Catatan aksi tidak boleh tertulis di folder rumah saat tes berjalan."""
    monkeypatch.setenv("LMS_AUDIT_LOG", str(tmp_path / "audit.log"))
