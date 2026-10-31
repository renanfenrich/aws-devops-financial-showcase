# Infrastructure diagrams

Open the [local atlas](public/index.html) with:

```bash
make diagram
# http://127.0.0.1:8765/ — Ctrl-C stops the server
make diagram DIAGRAM_PORT=8877
```

Viewing and `make diagram-check` use Python's standard library, no cloud access,
Node, CDN or global installation. The server is fixed to loopback and serves only
manifest-listed files under `public/`; repository source links navigate to a pinned
GitHub revision. No source directory, `.git`, credentials, state or plan is served.
HTML can also be opened directly, including its embedded runtime/fonts/icons.

## Source model and evidence

The four native Archify candidates are `local.json`, `delivery.json`, `aws.json`
and `bootstrap.json`. All component citations refer to inspected committed bytes
at the model's `meta.repository.revision`. Local execution is historical G1
evidence; generating the map does not repeat the lab. AWS foundations and enabled
bootstrap tests use mocks; bootstrap is disabled by default. No AWS call or apply
is part of diagram generation, checks or preview.

Each view includes a legend, source inspection, guided focus, routes/reach and
ownership limits. Local kind is not EKS; PostgreSQL is not RDS. S3, KMS and IAM
are outside the VPC. AWS arrows are declarations or policy contracts, not traffic.
See [validation evidence](validation.md) for the checks actually run.

## Updating a PR

Every infrastructure PR must review these views. The explicit `SOURCE_GLOBS` in
[the check](../../scripts/diagram.py) cover Terraform/Terragrunt/Atlantis,
platform/chart, delivery/CI, application I/O, migrations, Make, harness and
supporting contracts. `provenance.json` inventories their content hashes, including
added/deleted files, and all model/artifact/provenance inputs. CI, Jenkins and the
Bitbucket adapter reach `diagram-check` through the existing `make check` contract.

1. Review the changed source and affected relationships, ownership and boundaries.
2. If a cited file changes, commit that reviewed source, update the model's pinned
   repository revision and citation ranges, then regenerate. Diagram checks compare
   cited working bytes with that commit. Jenkins archive exports can check the
   existing record, but refreshing provenance requires a Git checkout.
3. For model, icon or vendor changes, run `make diagram-build`; old HTML fails
   input-hash checks even if someone refreshes the manifest. Inspect the views.
4. Revalidate a change without visual impact with a concrete reason, for example:

```bash
make diagram-refresh NOTE='Reviewed Terraform test assertion change; resource topology and ownership are unchanged'
make diagram-check
make check unit-test
```

A file touch is insufficient. Hashes, model IDs/edges/boundaries, citation ranges,
committed citation bytes, official asset hashes, input-to-HTML binding and local
links are checked. These checks cannot prove semantic fidelity or replace the
mandatory current-head human review by `octavariumdigitalpartners`.

## Rebuilding with the pinned Archify release

```bash
python3 scripts/bootstrap.py --only node
make diagram-build
make diagram-refresh NOTE='Reviewed and regenerated affected source-backed views'
make diagram-check
```

Node.js 26.13.0 is checksum-pinned in `toolchain.lock.json` and installs only into
`.tools/`. Archify 3.2.0 is pinned to commit
`f325d86230553e1dd15d3464324f1fcd01f02352` and its archive SHA-256 in `vendor.json`.
The builder downloads that archive into ignored `.cache/`, verifies it, extracts a
temporary copy and runs the real Archify `finalize` CLI. No `npm install` or global
skill installation is needed. Node >=18 is upstream's compatibility floor; the
repository build requires the tested pinned version. Source:
[Archify upstream](https://github.com/tt-a1i/archify),
[Node release checksums](https://nodejs.org/dist/v26.13.0/SHASUMS256.txt).

The small, recorded renderer adapter inserts official SVGs as base64 images in
the canonical SVG before Archify `deliver`, strict `check` and `browser-check`.
It adds model/icon/vendor hash metadata before generation. Published HTML is an
identical copy of the checked output, with no post-finalize modification.
The builder also exercises theme switching, Finder input, source-backed focus
and directed Route Probe with native clicks/text in a real headless Chrome,
using Archify's pinned browser test helper. It checks runtime errors, offline
loading and the expected AWS image count on each actual output.
`receipts.json` retains portable input/output hashes and outcomes; complete receipts
and browser captures remain under ignored `.cache/diagrams/`.
Missing browser support is a failed/incomplete build, never a fabricated success.

## AWS icon provenance and use

[AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) is the sole
AWS asset source. `vendor.json` records the official July 31, 2026 download URL,
retrieval date, complete ZIP hash, exact ZIP member paths and each extracted SVG
hash. `icons.json` explicitly maps every AWS component to a local official asset.
Only the seven required original SVGs are retained; full ZIPs stay outside Git.
There are no third-party AWS icon libraries, recoloring or stretched aspect ratios.
Network security groups use the official Amazon VPC mark with explicit resource
labels, rather than an icon for another security product.

AWS permits these assets for architecture diagrams; its page's guidance and AWS
trademark rights apply separately from Archify's software license. The atlas
attributes AWS and links the official guidance. Archify and bundled runtime/font
notices are preserved in `public/licenses/` and within generated HTML. Official
sources, hashes and adapter inputs remain reviewable in `vendor.json`.
