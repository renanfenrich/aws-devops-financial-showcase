"""Exercise the actual trusted authorization command, without GitHub or credentials."""

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AtlantisAuthorizationTests(unittest.TestCase):
    def authorize(self, user="renanfenrich", command="plan", repo="aws-devops-financial-showcase"):
        env = {
            "PATH": os.defpath,
            "USER_NAME": user,
            "COMMAND_NAME": command,
            "BASE_REPO_OWNER": "renanfenrich",
            "BASE_REPO_NAME": repo,
        }
        result = subprocess.run(
            ["sh", str(ROOT / "infra/atlantis/authz.sh")],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.splitlines()[-1:] == ["pass"]

    def test_owner_can_plan_and_read_version(self):
        self.assertTrue(self.authorize())
        self.assertTrue(self.authorize(command="version"))

    def test_every_identity_is_denied_mutating_commands(self):
        for user in ("renanfenrich", "octavariumdigitalpartners", "attacker", ""):
            for command in ("apply", "import", "state", "unlock", "approve_policies"):
                with self.subTest(user=user, command=command):
                    self.assertFalse(self.authorize(user=user, command=command))

    def test_unknown_user_repo_and_missing_context_are_denied(self):
        self.assertFalse(self.authorize(user="attacker"))
        self.assertFalse(self.authorize(user="octavariumdigitalpartners"))
        self.assertFalse(self.authorize(repo="another-repo"))
        self.assertFalse(self.authorize(user="", command=""))
        result = subprocess.run(
            ["sh", str(ROOT / "infra/atlantis/authz.sh")],
            env={"PATH": os.defpath},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.stdout.splitlines()[-1:], ["pass"])

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
