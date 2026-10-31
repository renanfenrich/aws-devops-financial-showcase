#!/bin/sh
# Trusted, image-baked authorization. Empty/unknown context always denies.
set -eu
if [ "${BASE_REPO_OWNER-}/${BASE_REPO_NAME-}" = "renanfenrich/aws-devops-financial-showcase" ] &&
   [ "${USER_NAME-}" = "renanfenrich" ]; then
  case "${COMMAND_NAME-}" in
    plan|version) printf '%s\n' pass; exit 0 ;;
  esac
fi
printf '%s\n' 'Denied: G1 allows only the owner to plan/version; apply/import/state are disabled for everyone.'
# Atlantis interprets exit 0 without a final 'pass' as an authorization denial.
exit 0
