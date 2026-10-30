"""Security boundary checks for the repository-local tool installer."""

import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/bootstrap.py"
SPEC = importlib.util.spec_from_file_location("tool_bootstrap", PATH)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def test_corrupt_download_never_installs(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(
        bootstrap.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"corrupt download")
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        bootstrap.install(
            (
                "unsafe",
                {
                    "version": "1",
                    "url": "https://example.invalid/tool",
                    "sha256": "0" * 64,
                    "member": None,
                },
            )
        )
    assert not (tmp_path / ".tools/bin/unsafe").exists()


def test_symlink_archive_member_never_installs(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        entry = tarfile.TarInfo("tool")
        entry.type = tarfile.SYMTYPE
        entry.linkname = "/etc/passwd"
        archive.addfile(entry)
    data = stream.getvalue()
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(data))
    with pytest.raises(ValueError, match="regular archive member"):
        bootstrap.install(
            (
                "unsafe",
                {
                    "version": "1",
                    "url": "https://example.invalid/tool.tar.gz",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "member": "tool",
                },
            )
        )
    assert not (tmp_path / ".tools/bin/unsafe").exists()
