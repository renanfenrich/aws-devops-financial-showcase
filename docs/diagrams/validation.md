# Diagram validation record

Authoring/review date: **2026-10-31**. Status: **READY FOR HUMAN REVIEW**;
this record does not supply mandatory human approval.

The candidates cite revision `0cef72a` (full SHA in each model), including the
read-only CI checkout-history adjustment; infrastructure resources themselves
remain those integrated in G1/G2-A. Input and output hashes are in
[receipts.json](receipts.json), and the full maintained source inventory is in
[provenance.json](provenance.json).

| Check actually executed | Result and boundary |
| --- | --- |
| `python3 scripts/bootstrap.py --only node` | Official Node 26.13.0 archive checksum verified; checkout-local binary only |
| `make diagram-build` | All four actual candidates passed Archify showcase validate, deliver, strict check and browser-check |
| Builder's `scripts/diagram-browser-smoke.mjs` | All four outputs passed native Chrome theme click, Finder typing/selection, source focus and directed route clicks; zero runtime errors/external requests; expected AWS image counts 0/0/10/2. Light default, white canvas in Dark, 64px marks, labels below, original aspect ratios and no card shadows verified. |
| Archify `visual-check` on each checked HTML | Four viewport captures per view: light/dark at 1440×900 and 2048×1320; automatic containment/readability/chrome checks passed |
| Agent inspection of captures | All four views inspected at 1440×900 light and 2048×1320 dark; labels/routes and official AWS symbols remain visible; long views use normal document scrolling |
| `make check unit-test` | Passed: repository/diagram/Python/workflow contracts and 41 offline unit/harness tests (9 integration cases deselected); 24 diagram cases included |
| Preview HTTP checks | 127.0.0.1:8877 only; 16 manifest-listed public files served with exact hashes; six forbidden paths returned 404; unit test also rejected symlinks/unlisted files; server stopped |
| Source checkout/export checks | Actual depth-1 `file://` clone rejected missing cited revision; `git fetch --unshallow` restored a passing check. Actual `git archive` export with `.source-sha` also passed. Both Actions checkouts now use `fetch-depth: 0`. |

Full browser receipts/captures remain in ignored `.cache/diagrams/`; portable
artifact hashes and interaction observations are committed in `receipts.json`.
Its `visual_review: not-requested` describes the automated finalizer only;
the separate agent inspection is bound to the same artifact hashes in
[visual-review.json](visual-review.json). Generated HTML whitespace is preserved
through a narrow `.gitattributes` rule so receipts keep their exact checked bytes.
The optional desktop in-app browser was unavailable (`Browser is not available:
iab`); the actual Chrome headless artifact checks and image inspection ran.
No physical mobile-device inspection is claimed.

The focused gate tests change, add and delete temporary Terraform files and show
the freshness check failing until a reasoned refresh. They also cover changed
cited bytes requiring a committed source re-pin, stale HTML input bindings,
stale delivery receipts, invalid edges, modified official assets, external runtime
dependencies and the Jenkins archive contract. Touching a file is insufficient.

GitGuardian initially classified the SHA-256 of the public
`infra/atlantis/authz.sh` source as a generic high-entropy secret. The value was
recomputed from that file and matched exactly; it is not an authentication value.
Source inventory entries now name their `sha256` field explicitly. No detector,
check or source path is suppressed.

AWS assets were extracted byte-for-byte from the official icon ZIP recorded in
[vendor.json](vendor.json). Embedded images were checked against those source SVG
hashes, remain inside their corresponding component groups, and preserve aspect
ratio. Their colors are not replaced by diagram theme colors.

The local application, kind cluster, cloud IaC mock suites, Jenkins runtime and
Atlantis smoke were not repeated for this diagram change. Existing G1/G2-A
runtime evidence is historical and is explicitly labeled in the views. There
were no AWS API calls, credentials, provisioning, backend migration, remote
webhook, financial operation, deployment or external publication.

The offline gate verifies structural and provenance contracts. Topology meaning,
ownership and completeness still require current-head review by
`octavariumdigitalpartners`; no automated result grants a merge.

The 31 October appearance revision follows the user's AWS example: primary 64px
official marks, labels below, neutral arrows, thin square group frames, sans-serif
diagram text and a white canvas in both viewer themes. A semantic comparison of
all four candidates against the previous versions found only per-node position,
size and decorative icon changes; nodes, edges, labels, sources and evidence
statements are unchanged. Input bindings now include CSS and builder bytes, so a
provenance refresh cannot accept an old presentation after those inputs change.
The previous PR approval covered `7b6947a`; this revision needs a new current-head
human review. Workstation runtime suites were not rerun for this visual change;
the normal PR CI records any additional execution separately.
