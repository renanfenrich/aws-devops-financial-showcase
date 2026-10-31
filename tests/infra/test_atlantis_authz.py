"""Exercise trusted repo/project authorization without GitHub or credentials."""

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOUNDATION = "infra/terraform/aws-foundation"


class AtlantisAuthorizationTests(unittest.TestCase):
    def authorize(
        self,
        user="renanfenrich",
        command="plan",
        repo="aws-devops-financial-showcase",
        project="aws-foundation",
        directory=FOUNDATION,
        root="/offline/checkout",
        unset=(),
    ):
        env = {
            "PATH": os.defpath,
            "USER_NAME": user,
            "COMMAND_NAME": command,
            "BASE_REPO_OWNER": "renanfenrich",
            "BASE_REPO_NAME": repo,
            "PROJECT_NAME": project,
            "REPO_REL_PATH": directory,
            "REPO_ROOT": root,
        }
        for key in unset:
            env.pop(key, None)
        result = subprocess.run(
            ["sh", str(ROOT / "infra/atlantis/authz.sh")],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.splitlines()[-1:] == ["pass"]

    def test_owner_can_plan_and_read_version_for_foundation_only(self):
        self.assertTrue(self.authorize())
        self.assertTrue(self.authorize(command="version"))

    def test_upstream_repository_stage_is_identity_check_not_project_authorization(self):
        # In 0.49.0 all three keys exist with empty values before project discovery.
        for command in ("plan", "version"):
            self.assertTrue(self.authorize(command=command, project="", directory="", root=""))
        self.assertFalse(self.authorize(project="", directory=FOUNDATION, root=""))
        self.assertFalse(self.authorize(project="aws-foundation", directory="", root=""))

    def test_every_identity_is_denied_mutating_commands(self):
        for user in ("renanfenrich", "octavariumdigitalpartners", "attacker", ""):
            for command in ("apply", "import", "state", "unlock", "approve_policies"):
                with self.subTest(user=user, command=command):
                    self.assertFalse(self.authorize(user=user, command=command))

    def test_bootstrap_and_unknown_projects_are_denied_even_with_approved_name_or_path(self):
        for command in ("plan", "version"):
            for project, directory in (
                ("state-bootstrap", "infra/terraform/state-bootstrap"),
                ("aws-foundation", "infra/terraform/state-bootstrap"),
                ("state-bootstrap", FOUNDATION),
                ("unknown", FOUNDATION),
                ("aws-foundation", "infra/terraform/unknown"),
            ):
                with self.subTest(command=command, project=project, directory=directory):
                    self.assertFalse(
                        self.authorize(command=command, project=project, directory=directory)
                    )

    def test_alternate_traversal_absolute_and_encoded_paths_are_denied(self):
        for directory in (
            "../aws-foundation",
            "./" + FOUNDATION,
            "/" + FOUNDATION,
            FOUNDATION + "/",
            FOUNDATION + "/../state-bootstrap",
            "infra/terraform//aws-foundation",
            "infra/terraform/%2e%2e/aws-foundation",
            "infra/terraform/AWS-FOUNDATION",
        ):
            with self.subTest(directory=directory):
                self.assertFalse(self.authorize(directory=directory))

    def test_unknown_user_repo_and_missing_context_are_denied(self):
        self.assertFalse(self.authorize(user="attacker"))
        self.assertFalse(self.authorize(user="octavariumdigitalpartners"))
        self.assertFalse(self.authorize(repo="another-repo"))
        self.assertFalse(self.authorize(root="relative/checkout"))
        for key in ("PROJECT_NAME", "REPO_REL_PATH", "REPO_ROOT"):
            with self.subTest(missing=key):
                self.assertFalse(self.authorize(unset=(key,)))
        self.assertFalse(self.authorize(unset=("PROJECT_NAME", "REPO_REL_PATH", "REPO_ROOT")))
        self.assertFalse(self.authorize(project="", directory="", root="/offline/checkout"))

    def test_bootstrap_is_not_a_registered_project(self):
        text = (ROOT / "atlantis.yaml").read_text()
        self.assertEqual(re.findall(r"^\s+- name:\s*(\S+)", text, re.M), ["aws-foundation"])
        self.assertEqual(re.findall(r"^\s+dir:\s*(\S+)", text, re.M), [FOUNDATION])

    def test_apply_workflow_always_fails(self):
        result = subprocess.run(
            ["sh", str(ROOT / "infra/atlantis/deny-apply.sh")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
