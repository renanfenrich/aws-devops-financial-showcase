#!/usr/bin/env python3
"""Prove the disabled graph with the real provider inside a network-isolated runner."""

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "infra/terraform/state-bootstrap"
CACHE = ROOT / ".cache/terraform/providers"
TERRAFORM = ROOT / ".tools/bin/terraform"

PLAN_SCRIPT = r"""
import json, os, subprocess

def invoke(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout

version = json.loads(invoke(["/usr/local/bin/terraform", "version", "-json"]))
assert version["terraform_version"] == os.environ["EXPECTED_TERRAFORM_VERSION"]
invoke(["/usr/local/bin/terraform", "-chdir=/workspace", "plan", "-refresh=false",
        "-lock=false", "-input=false", "-no-color", "-out=/tmp/disabled.tfplan"])
plan = json.loads(invoke(["/usr/local/bin/terraform", "-chdir=/workspace",
                          "show", "-json", "/tmp/disabled.tfplan"]))
def instances(module):
    return len(module.get("resources", [])) + sum(
        instances(child) for child in module.get("child_modules", []))
changes = [change for change in plan.get("resource_changes", [])
           if change["change"]["actions"] != ["no-op"]]
count = instances(plan.get("planned_values", {}).get("root_module", {}))
assert plan.get("errored") is not True
assert plan["variables"]["bootstrap_enabled"]["value"] is False
assert plan["variables"]["target"]["value"] is None
assert count == 0 and not changes
outputs = plan.get("planned_values", {}).get("outputs", {})
assert set(outputs) == {"backend_config", "backend_access_policy_json"}
assert all("value" in output and output["value"] is None for output in outputs.values())
assert all(change.get("after_unknown") is False and change.get("after") is None
           for change in plan.get("output_changes", {}).values())
print(json.dumps({"terraform_version": version["terraform_version"],
                  "bootstrap_enabled": False, "target_configured": False,
                  "resource_changes": len(changes), "planned_resource_instances": count,
                  "network": "none", "sdk_fields": "synthetic process-local fixtures",
                  "actual_credentials_mounted": False, "passed": True}))
"""


def main():
    if os.getuid() == 0:
        raise SystemExit("Run this isolated check as a non-root workstation/CI user")
    private = ROOT / ".local/state-plan"
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / "toolchain.lock.json").read_text())
    inspection = subprocess.run(
        ["docker", "image", "inspect", "financial-showcase-api:local"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if inspection.returncode:
        raise SystemExit("Build the local runner image with make image first")
    image_id = json.loads(inspection.stdout)[0]["Id"]
    run_id = uuid.uuid4().hex
    container_name = "financial-showcase-state-plan-" + run_id
    record = {"schema_version": 1, "run_id": run_id, "runner_image_id": image_id, "passed": False}
    environment = {
        "PATH": str(ROOT / ".tools/bin") + os.pathsep + os.defpath,
        "HOME": os.environ["HOME"],
        "TF_IN_AUTOMATION": "true",
        "TF_INPUT": "false",
        "TF_CLI_CONFIG_FILE": "/dev/null",
        "TF_PLUGIN_CACHE_DIR": str(CACHE),
        "CHECKPOINT_DISABLE": "1",
        "AWS_CONFIG_FILE": "/dev/null",
        "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    try:
        # Copy code + the signed dependency lock only; no tfvars, local state,
        # backend cache, private configuration or workstation credentials enter.
        with tempfile.TemporaryDirectory(prefix="workspace-", dir=private) as temporary:
            workspace = Path(temporary)
            for source in [*MODULE.glob("*.tf"), MODULE / ".terraform.lock.hcl"]:
                if source.is_symlink() or not source.is_file():
                    raise ValueError("State-plan inputs must be regular files, not symbolic links")
                shutil.copyfile(source, workspace / source.name)
            initialized = subprocess.run(
                [
                    str(TERRAFORM),
                    f"-chdir={workspace}",
                    "init",
                    "-backend=false",
                    "-input=false",
                    "-lockfile=readonly",
                    "-no-color",
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            if initialized.returncode:
                raise RuntimeError(initialized.stdout + initialized.stderr)
            command = [
                "docker",
                "run",
                "--rm",
                "--interactive",
                "--name",
                container_name,
                "--pull=never",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                "--tmpfs",
                "/tmp:rw,nosuid,size=64m",
                "--mount",
                f"type=bind,src={TERRAFORM},dst=/usr/local/bin/terraform,readonly",
                "--mount",
                f"type=bind,src={workspace},dst=/workspace,readonly",
                "--mount",
                f"type=bind,src={CACHE},dst={CACHE},readonly",
            ]
            # Fake SDK parser inputs exist only in this no-network process. The
            # Terraform target is still null; these are not an AWS account/identity.
            fixtures = {
                "TF_IN_AUTOMATION": "true",
                "TF_INPUT": "false",
                "CHECKPOINT_DISABLE": "1",
                "TF_CLI_CONFIG_FILE": "/dev/null",
                "AWS_CONFIG_FILE": "/dev/null",
                "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
                "AWS_EC2_METADATA_DISABLED": "true",
                "AWS_ACCESS_KEY_ID": "offline-unused-key",
                "AWS_SECRET_ACCESS_KEY": "offline-unused-secret",
                "AWS_REGION": "us-east-1",
                "EXPECTED_TERRAFORM_VERSION": lock["tools"]["terraform"]["version"],
            }
            for key, value in fixtures.items():
                command.extend(["--env", f"{key}={value}"])
            command.extend(["--entrypoint", "python", image_id, "-I", "-"])
            result = subprocess.run(
                command,
                input=PLAN_SCRIPT,
                capture_output=True,
                text=True,
                check=False,
                timeout=150,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            record.update(json.loads(result.stdout))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        (private / f"{run_id}.log").write_text(str(error))
        record["error"] = f"Check failed; private diagnostic: .local/state-plan/{run_id}.log"
    except KeyboardInterrupt:
        record["error"] = "Interrupted; the owned runner was removed"
    finally:
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                check=False,
                timeout=15,
            )
    output = ROOT / "artifacts/state-plan"
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
