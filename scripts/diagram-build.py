#!/usr/bin/env python3
"""Generate checked Archify HTML using pinned sources; never install globally."""

import base64
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs/diagrams"
VIEWS = ("local", "delivery", "aws", "bootstrap")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    vendor = json.loads((FOLDER / "vendor.json").read_text())
    spec = vendor["archify"]
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js is required only for diagram-build; see docs/diagrams/README.md")
    node_version = subprocess.check_output([node, "--version"], text=True).strip()
    if node_version != spec["node_version"]:
        raise ValueError(f"Use pinned Node.js {spec['node_version']}; found {node_version}")
    cache = ROOT / ".cache/diagrams"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"archify-{spec['commit']}.tar.gz"
    if not archive.exists() or digest(archive) != spec["sha256"]:
        request = urllib.request.Request(spec["url"], headers={"User-Agent": "showcase-diagram"})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != spec["sha256"]:
            raise ValueError("Archify archive integrity mismatch")
        archive.write_bytes(data)
    icons = json.loads((FOLDER / "icons.json").read_text())
    style = (FOLDER / "style.css").read_text()
    receipts = {}
    with tempfile.TemporaryDirectory(prefix="build-", dir=cache) as workspace:
        with tarfile.open(archive) as package:
            package.extractall(workspace, filter="data")
        skill = Path(workspace) / f"archify-{spec['commit']}" / "archify"
        for component, expected in spec["components"].items():
            if digest(skill / component) != expected:
                raise ValueError(f"Archify component integrity mismatch: {component}")
        template_path = skill / "assets/template.html"
        renderer_path = skill / "renderers/architecture/render-architecture.mjs"
        template = template_path.read_text()
        renderer = renderer_path.read_text()
        for view in VIEWS:
            model_path = FOLDER / f"{view}.json"
            model = json.loads(model_path.read_text())
            images = {}
            for component in model["components"]:
                identifier = component["id"]
                if identifier not in icons.get(view, {}):
                    continue
                asset = icons[view][identifier]
                asset_path = FOLDER / "public" / asset
                if digest(asset_path) != vendor["aws_icons"]["assets"][asset]["sha256"]:
                    raise ValueError(f"AWS icon integrity mismatch: {asset}")
                data = base64.b64encode(asset_path.read_bytes()).decode()
                x, y = component["pos"]
                width, _ = component["size"]
                # Original official artwork is the primary mark, with labels below.
                images[identifier] = (
                    f'<image data-aws-icon="{asset}" x="{x + width / 2 - 32}" y="{y + 10}" '
                    'width="64" height="64" preserveAspectRatio="xMidYMid meet" '
                    f'href="data:image/svg+xml;base64,{data}"/>'
                )
            # Adapt presentation inside the existing node metadata/hitbox contract.
            start = renderer.index("function renderComponent(c) {")
            end = renderer.index("function renderLegend()", start)
            component_renderer = renderer[start:end]
            edits = [
                (
                    "const labelY = hasSub ? c.y + c.height / 2 - 2 : c.y + c.height / 2 + 4;",
                    "const labelY = c.y + 94;",
                ),
                ("c.y + c.height / 2 + 14", "c.y + 110"),
                ("brandLabelFitWidth(c, c.width), 11, 8", "brandLabelFitWidth(c, c.width), 13, 10"),
                (
                    'class="${fill}"',
                    "class=\"${fill} atlas-node${officialImages[c.id] ? ' atlas-aws' : ''}\"",
                ),
                (
                    'font-weight="600" text-anchor="middle"',
                    'font-weight="400" text-anchor="middle"',
                ),
                (
                    "renderSemanticSigil(c.type, { icon: c.icon, x: c.x + 6, y: c.y + 6 })",
                    "(officialImages[c.id] || renderSemanticSigil(c.type, "
                    "{ icon: c.icon, x: cx - 24, y: c.y + 18, size: 48 }))",
                ),
            ]
            for before, after in edits:
                if component_renderer.count(before) != 1:
                    raise ValueError("Pinned Archify component presentation seam changed")
                component_renderer = component_renderer.replace(before, after)
            adapted = (
                renderer[:start]
                + "const officialImages = "
                + json.dumps(images)
                + ";\n"
                + component_renderer
                + renderer[end:]
            )
            # Keep larger annotation text and the geometry checked by Archify in sync.
            for before, after in [
                ("boundaryLabelFontPreferred: 9,", "boundaryLabelFontPreferred: 12,"),
                ("sublabelPreferred: 9,", "sublabelPreferred: 10,"),
                ("textUnits(conn.label) * 4.8 + 10", "textUnits(conn.label) * 6 + 10"),
                ("y: ly - 10, width, height: 14", "y: ly - 12, width, height: 16"),
                (
                    'class="${edgeLabelAccent(conn.variant)}" font-size="8"',
                    'class="${edgeLabelAccent(conn.variant)}" font-size="10"',
                ),
            ]:
                if adapted.count(before) != 1:
                    raise ValueError("Pinned Archify annotation geometry seam changed")
                adapted = adapted.replace(before, after)
            # Canonical SVG styles also survive SVG/raster exports. No post-finalize edits.
            replacement = (
                "svg: renderSvg().replace('<svg ', "
                + json.dumps(f'<svg data-aws-style="reference" data-atlas-view="{view}" ')
                + ").replace('</svg>', "
                + json.dumps("<style>" + style + "</style></svg>")
                + "),"
            )
            if renderer.count("svg: renderSvg(),") != 1:
                raise ValueError("Pinned Archify SVG adapter seam changed")
            renderer_path.write_text(adapted.replace("svg: renderSvg(),", replacement))
            metadata = "\n".join(
                f'<meta name="showcase-{name}-sha256" content="{digest(path)}">'
                for name, path in (
                    ("spec", model_path),
                    ("icons", FOLDER / "icons.json"),
                    ("vendor", FOLDER / "vendor.json"),
                    ("style", FOLDER / "style.css"),
                    ("builder", Path(__file__)),
                )
            )
            canvas_style = (
                "<style>html[data-preset] .diagram-container {"
                "background:var(--bg); border-radius:0; box-shadow:none;}"
                "</style>"
            )
            template_path.write_text(
                template.replace("</head>", metadata + canvas_style + "\n</head>")
            )
            output = cache / f"{view}.html"
            command = [
                node,
                str(skill / "bin/archify.mjs"),
                "finalize",
                "architecture",
                str(model_path),
                str(output),
                "--repo-root",
                str(ROOT),
                "--quality",
                "showcase",
                "--out-dir",
                str(Path(tempfile.mkdtemp(prefix=f"review-{view}-", dir=cache))),
                "--json",
            ]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            receipt = json.loads(result.stdout)
            if result.returncode:
                print(result.stdout)
                raise ValueError(
                    f"Archify {view} finalize failed; retain diagnostic/evidence paths"
                )
            smoke = subprocess.check_output(
                [
                    node,
                    str(ROOT / "scripts/diagram-browser-smoke.mjs"),
                    str(skill),
                    str(output),
                    str(model_path),
                ],
                cwd=ROOT,
                text=True,
            )
            shutil.copyfile(output, FOLDER / "public" / f"{view}.html")
            receipts[view] = {
                "specification_sha256": digest(model_path),
                "artifact_sha256": digest(output),
                "gates": receipt["gates"],
                "diagnostics": receipt["diagnostics"],
                "visual_review": "not-requested",
                "interaction_checks": json.loads(smoke),
            }
            print(f"Archify {view}: {receipt['gates']}")
    (FOLDER / "receipts.json").write_text(
        json.dumps(
            {"archify_commit": spec["commit"], "node": node_version, "views": receipts}, indent=2
        )
        + "\n"
    )


if __name__ == "__main__":
    try:
        build()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
