"""Native recovery remains synthetic, private and independent of workstation CLI settings."""

import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("state_recovery", ROOT / "scripts/state_recovery.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
CANARY = "SYNTHETIC_STATE_VALUE_MUST_NOT_PUBLISH"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    (tmp_path / "toolchain.lock.json").write_bytes((ROOT / "toolchain.lock.json").read_bytes())
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    return tmp_path


def test_native_guards_ignore_inherited_cli_settings_and_do_not_publish_state(
    sandbox, monkeypatch, capsys
):
    outside = sandbox / "outside"
    outside.mkdir()
    sentinel = outside / "terraform.tfstate"
    sentinel.write_text("workstation state must stay untouched")
    monkeypatch.setenv("TF_CLI_ARGS_state_push", "-force")
    monkeypatch.setenv("TF_CLI_ARGS", f"-chdir={outside}")
    monkeypatch.setenv("TF_DATA_DIR", str(outside / "data"))
    monkeypatch.setenv("TF_WORKSPACE", "wrong-workspace")
    monkeypatch.setenv("TF_LOG", "TRACE")
    monkeypatch.setenv("TF_LOG_PATH", str(outside / "log"))
    monkeypatch.setenv("TF_CLI_CONFIG_FILE", str(outside / "config"))
    previous = os.umask(0)
    try:
        assert recovery.main() == 0
        assert os.umask(0) == 0
    finally:
        os.umask(previous)
    public = json.loads((sandbox / "artifacts/state-recovery/report.json").read_text())
    assert public["passed"]
    assert len(public["checks"]) == 12 and all(public["checks"].values())
    assert set(public) == {
        "schema_version",
        "mode",
        "checks",
        "passed",
        "boundaries",
        "terraform_version",
    }
    assert all(value is False for value in public["boundaries"].values())
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err + json.dumps(public)
    assert str(sandbox) not in captured.out + captured.err + json.dumps(public)
    assert list(outside.iterdir()) == [sentinel]
    assert sentinel.read_text() == "workstation state must stay untouched"
    assert not list((sandbox / "scratch").iterdir())


def test_native_failure_is_redacted_and_cleans_up_private_state(sandbox, monkeypatch, capsys):
    native_run = subprocess.run

    def fail_export(command, **kwargs):
        if command[1:] == ["state", "pull"]:
            return subprocess.CompletedProcess(command, 1, CANARY.encode(), CANARY.encode())
        return native_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_export)
    assert recovery.main() == 1
    public = json.loads((sandbox / "artifacts/state-recovery/report.json").read_text())
    assert public["passed"] is False
    assert public["checks"] == {"pinned_terraform": True}
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err + json.dumps(public)
    assert not list((sandbox / "scratch").iterdir())
    assert not list((sandbox / "artifacts").rglob("*.tfstate*"))
