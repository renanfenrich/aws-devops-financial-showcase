# Contributing

renanfenrich owns development and Git flow. Start `feature/*` from `develop` and
target `develop` with a Conventional Commit PR title. Use `release/*` for reviewed
promotion to `main`; hotfixes start from `main`. Never push implementation directly
to protected branches. The minimal initial repository bootstrap is the sole
initialization exception, not a standing permission.

Run `make bootstrap`, then `make verify` and gates affected by the change. The
application test target starts a disposable local PostgreSQL service; it does not
silently replace real database integration with SQLite. Use `make evidence` on
the committed source and retain failed attempts when diagnosing failures.

Keep changes bounded, SQL parameterized, dependencies pinned and secrets outside
Git. Add a meaningful regression test for transaction/auth/security changes.
Document observed behavior, cost/availability assumptions and pending integrations.

octavariumdigitalpartners is the mandatory human reviewer/approver. Request review
on the final head; invalidate stale reviews when code changes. Codex ends at
READY FOR HUMAN REVIEW. No approval, merge, AWS apply or release is automatic.
