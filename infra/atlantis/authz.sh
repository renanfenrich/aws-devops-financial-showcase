#!/bin/sh
# Trusted image-baked policy for Atlantis 0.49.0's repository + project checks.
set -eu
deny() {
  printf '%s\n' 'Denied: offline access is restricted to the owner and the approved foundation project; mutations are disabled.'
  # Exit 0 without final 'pass' means an evaluated denial, per Atlantis' contract.
  exit 0
}
[ "${BASE_REPO_OWNER-}/${BASE_REPO_NAME-}" = "renanfenrich/aws-devops-financial-showcase" ] || deny
[ "${USER_NAME-}" = renanfenrich ] || deny
case "${COMMAND_NAME-}" in plan|version) ;; *) deny ;; esac

# The pinned upstream runner ALWAYS sets these keys, even before project discovery.
# Unset keys are not a valid repository-stage invocation and fail closed.
[ "${PROJECT_NAME+x}" = x ] && [ "${REPO_REL_PATH+x}" = x ] && [ "${REPO_ROOT+x}" = x ] || deny
if [ -z "$PROJECT_NAME" ] && [ -z "$REPO_REL_PATH" ] && [ -z "$REPO_ROOT" ]; then
  # Repository identity check only. A plan still needs the later project check.
  printf '%s\n' pass
  exit 0
fi

# Compare the upstream lexical path exactly: never normalize traversal into access.
[ "$PROJECT_NAME" = aws-foundation ] || deny
[ "$REPO_REL_PATH" = infra/terraform/aws-foundation ] || deny
case "$REPO_ROOT" in /*) ;; *) deny ;; esac
printf '%s\n' pass
