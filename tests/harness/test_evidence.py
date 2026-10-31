"""Verify evidence binding, retained failures and secret-safe scanner publication."""

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence = load_script("evidence")
security_report = load_script("security_report")


@pytest.fixture
def repository(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.name", "Evidence Test")
    git("config", "user.email", "evidence@example.invalid")
    (tmp_path / ".gitignore").write_text("artifacts/\n.local/\n")
    (tmp_path / "source.txt").write_text("original\n")
    (tmp_path / "toolchain.lock.json").write_text('{"tools":{}}\n')
    git("add", ".")
    git("commit", "-qm", "test input")
    return tmp_path


def test_tree_hash_covers_dirty_and_untracked_inputs_but_ignores_private_files(repository):
    original = evidence.source_snapshot(repository)
    (repository / "source.txt").write_text("changed\n")
    dirty = evidence.source_snapshot(repository)
    assert original["sha"] == dirty["sha"]
    assert original["source_tree_sha256"] != dirty["source_tree_sha256"]
    (repository / "new.txt").write_text("untracked input")
    untracked = evidence.source_snapshot(repository)
    assert dirty["source_tree_sha256"] != untracked["source_tree_sha256"]
    (repository / ".local").mkdir()
    (repository / ".local/secret").write_text("must never become source evidence")
    assert evidence.source_snapshot(repository) == untracked


def test_symlink_targets_and_ancestors_are_never_read(repository, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "private").write_text("first secret")
    (repository / "link").symlink_to(outside / "private")
    before = evidence.source_snapshot(repository)
    (outside / "private").write_text("a different secret")
    assert evidence.source_snapshot(repository) == before
    (repository / "parent").symlink_to(outside, target_is_directory=True)
    blocked = evidence.source_entry(repository, "parent/private")
    assert blocked["type"] == "blocked-by-link"
    assert "sha256" not in blocked
    (repository / "link").unlink()
    (repository / "link").symlink_to(outside / "other")
    assert (
        evidence.source_snapshot(repository)["source_tree_sha256"] != before["source_tree_sha256"]
    )


def test_changed_source_during_successful_command_is_inconclusive(repository):
    def mutate(*args, **kwargs):
        (repository / "source.txt").write_text("changed while the gate was running")
        return SimpleNamespace(returncode=0)

    assert evidence.capture(repository, "infra", runner=mutate) == 1
    record = json.loads((repository / "artifacts/evidence-infra.json").read_text())
    assert record["result"] == "inconclusive"
    assert record["command_exit_code"] == 0
    assert (
        record["source_start"]["source_tree_sha256"] != record["source_end"]["source_tree_sha256"]
    )


def test_failed_history_survives_a_later_pass_and_excludes_history_from_reports(repository):
    attempts = iter((1, 0))

    def run(*args, **kwargs):
        code = next(attempts)
        artifacts = repository / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "report.json").write_text(json.dumps({"exit": code}))
        (artifacts / "report.xml").write_text('<testsuite tests="1"/>')
        (artifacts / "evidence-old.json").write_text('{"old":true}')
        return SimpleNamespace(returncode=code)

    assert evidence.capture(repository, "infra", runner=run) == 1
    assert evidence.capture(repository, "infra", runner=run) == 0
    records = [
        json.loads(path.read_text())
        for path in (repository / "artifacts/history").glob("*/evidence.json")
    ]
    assert sorted(record["result"] for record in records) == ["failed", "passed"]
    assert len({record["run_id"] for record in records}) == 2
    assert all(
        set(record["report_sha256"]) == {"artifacts/report.json", "artifacts/report.xml"}
        for record in records
    )
    failed = next(record for record in records if record["result"] == "failed")
    retained = repository / failed["history_path"] / "reports/report.json"
    assert json.loads(retained.read_text()) == {"exit": 1}
    assert (
        json.loads((repository / "artifacts/evidence-infra.json").read_text())["result"] == "passed"
    )


def test_security_projection_removes_secret_payloads_and_image_environment():
    secret = "LIVE_SECRET_MUST_NOT_PUBLISH"
    report = {
        "SchemaVersion": 2,
        "Metadata": {"ImageID": "sha256:example", "ImageConfig": {"Env": ["TOKEN=" + secret]}},
        "UnknownRawDump": secret,
        "Results": [
            {
                "Target": "src/config.py",
                "Class": "secret",
                "Secrets": [
                    {
                        "RuleID": "token",
                        "Title": "Token",
                        "Severity": "HIGH",
                        "StartLine": 3,
                        "EndLine": 4,
                        "Match": secret,
                        "Code": {"Lines": [{"Content": secret}]},
                        "FutureRawField": secret,
                    }
                ],
                "Misconfigurations": [{"ID": "example", "CauseMetadata": {"Code": secret}}],
            }
        ],
    }
    safe = security_report.sanitized_report(report)
    assert secret not in json.dumps(safe)
    assert safe["Metadata"]["ImageID"] == "sha256:example"
    finding = safe["Results"][0]["Secrets"][0]
    assert set(finding) == {"RuleID", "Title", "Severity", "StartLine", "EndLine", "File"}


def test_security_missing_report_remains_failed_and_records_scanned_image(tmp_path):
    raw, public = tmp_path / "raw", tmp_path / "public"
    raw.mkdir()
    (raw / "status.json").write_text('{"filesystem":0,"image":2,"sbom":0}')
    (raw / "image-inspect.json").write_text(
        json.dumps(
            [
                {
                    "Id": "sha256:immutable",
                    "Config": {
                        "Labels": {
                            "org.opencontainers.image.revision": "a" * 40,
                            "io.showcase.dirty": "false",
                        }
                    },
                }
            ]
        )
    )
    (raw / "filesystem.json").write_text('{"Results":[]}')
    (raw / "sbom.spdx.json").write_text('{"spdxVersion":"SPDX-2.3","packages":[]}')
    assert security_report.publish(raw, public, "run") == 1
    summary = json.loads((public / "scan.json").read_text())
    assert not summary["passed"] and not summary["reports_complete"]
    assert summary["scanned_image_id"] == "sha256:immutable"
    assert summary["image_source_dirty"] == "false"
    assert summary["other_images_scanned"] is False
    assert not (public / "image.json").exists()


def test_security_shell_scans_immutable_id_and_never_publishes_raw_secret(tmp_path):
    import shutil

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("security.sh", "security_report.py"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    binary = tmp_path / ".tools/bin"
    binary.mkdir(parents=True)
    image_id = "sha256:" + "a" * 64
    (binary / "docker").write_text(
        "#!/usr/bin/env python3\nimport json\n"
        f"print(json.dumps([{{'Id':'{image_id}','Config':{{'Labels':{{}}}}}}]))\n"
    )
    (binary / "trivy").write_text(
        """#!/usr/bin/env python3
import json,sys
from pathlib import Path
args=sys.argv[1:]
with Path('.local/scanner-calls.jsonl').open('a') as calls:
    calls.write(json.dumps(args)+'\\n')
path=Path(args[args.index('--output')+1])
if args[0]=='fs':
    report={'Results':[{'Target':'config.py','Secrets':[{'RuleID':'test','Title':'Token','Severity':'HIGH','Match':'PRIVATE_DETECTED_VALUE','Code':{'Content':'PRIVATE_DETECTED_VALUE'}}]}]}
elif '--format' in args and args[args.index('--format')+1]=='spdx-json':
    report={'spdxVersion':'SPDX-2.3','packages':[]}
else:
    report={'Results':[]}
path.write_text(json.dumps(report))
raise SystemExit(1 if args[0]=='fs' else 0)
"""
    )
    for path in binary.iterdir():
        path.chmod(0o755)
    result = subprocess.run(
        ["bash", str(scripts / "security.sh")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "PRIVATE_DETECTED_VALUE" not in result.stdout + result.stderr
    public = list((tmp_path / "artifacts/security").rglob("*.json"))
    assert public and all("PRIVATE_DETECTED_VALUE" not in path.read_text() for path in public)
    assert any(
        "PRIVATE_DETECTED_VALUE" in path.read_text()
        for path in (tmp_path / ".local/security").rglob("filesystem.json")
    )
    calls = [
        json.loads(line)
        for line in (tmp_path / ".local/scanner-calls.jsonl").read_text().splitlines()
    ]
    assert all(call[-1] == image_id for call in calls if call[0] == "image")
