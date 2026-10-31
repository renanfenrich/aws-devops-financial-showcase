#!/usr/bin/env python3
"""Offline diagram freshness, structure and loopback preview contracts."""

import argparse
import fnmatch
import hashlib
import json
import mimetypes
import re
import subprocess
from datetime import UTC, datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = "docs/diagrams"
VIEWS = ("local", "delivery", "aws", "bootstrap")
SOURCE_GLOBS = (
    "infra/**",
    "platform/**",
    "ci/**",
    "migrations/**",
    ".github/workflows/**",
    "src/showcase/**",
    "scripts/**",
    "tests/harness/**",
    "compose.yaml",
    "Dockerfile",
    "Jenkinsfile",
    "bitbucket-pipelines.yml",
    "atlantis.yaml",
    "toolchain.lock.json",
    ".gitattributes",
    "Makefile",
    "AGENTS.md",
    "README.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    "docs/architecture.md",
    "docs/evidence-g1.md",
    "docs/evidence-g2-a.md",
)
IGNORED = {
    ".git",
    ".terraform",
    ".terragrunt-cache",
    "__pycache__",
    ".venv",
    ".tools",
    ".local",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
}


def regular(root, name):
    if root.resolve() != root.absolute():
        raise ValueError(f"Symlink in file root: {root}")
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe path: {name}")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink is not a diagram/source file: {name}")
    if not current.is_file():
        raise ValueError(f"Missing regular file: {name}")
    return current


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def names(root):
    if (root / ".git").exists():
        output = subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
        )
        return sorted({name.decode() for name in output.split(b"\0") if name})
    # Jenkins deliberately executes a git-archive export, with no .git or credentials.
    marker = root / ".source-sha"
    if not marker.is_file() or not re.fullmatch(r"[a-f0-9]{40}\n?", marker.read_text()):
        raise ValueError("Use a Git checkout or the harness's .source-sha archive export")
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if not any(part in IGNORED for part in path.relative_to(root).parts)
        and (path.is_file() or path.is_symlink())
    )


def snapshot(root):
    sources, artifacts = {}, {}
    for name in names(root):
        selected = any(fnmatch.fnmatchcase(name, pattern) for pattern in SOURCE_GLOBS)
        artifact = name.startswith(DIAGRAMS + "/") and name not in {
            DIAGRAMS + "/provenance.json",
            DIAGRAMS + "/README.md",
        }
        if selected or artifact:
            if not (root / name).exists() and not (root / name).is_symlink():
                continue  # A tracked deletion must disappear from the expected snapshot.
            value = digest(regular(root, name))
            if selected:
                sources[name] = {"sha256": value}
            if artifact:
                artifacts[name] = value
    return {"source_globs": list(SOURCE_GLOBS), "sources": sources, "artifacts": artifacts}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.bindings = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("name", "").startswith("showcase-"):
            self.bindings.setdefault(values["name"], []).append(values.get("content"))
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.links.append((tag, key, value))


def validate(root):
    folder = root / DIAGRAMS
    icons = json.loads((folder / "icons.json").read_text())
    vendor = json.loads((folder / "vendor.json").read_text())
    for name in ("archify", "aws_icons"):
        item = vendor[name]
        if not item.get("version") or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
            raise ValueError(f"Invalid {name} version/archive integrity")
        if urlsplit(item["url"]).scheme != "https":
            raise ValueError(f"Invalid {name} official source")
    if not re.fullmatch(r"[a-f0-9]{40}", vendor["archify"]["commit"]):
        raise ValueError("Archify commit must be pinned")
    official_archify = (
        "https://codeload.github.com/tt-a1i/archify/tar.gz/" + vendor["archify"]["commit"]
    )
    if vendor["archify"]["url"] != official_archify:
        raise ValueError("Archify must use its official commit-pinned archive")
    aws_url = urlsplit(vendor["aws_icons"]["url"])
    if aws_url.hostname != "d1.awsstatic.com" or "architecture-icon-release/" not in aws_url.path:
        raise ValueError("AWS icons must come from the official AWS architecture release")
    assets = vendor["aws_icons"]["assets"]
    for path, spec in assets.items():
        if not spec.get("member") or digest(regular(folder / "public", path)) != spec["sha256"]:
            raise ValueError(f"AWS asset integrity mismatch: {path}")
    verified_sources = set()
    for view in VIEWS:
        model_path = folder / f"{view}.json"
        model = json.loads(model_path.read_text())
        revision = model["meta"]["repository"]["revision"]
        if not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError(f"{view}: repository source revision must be pinned")
        nodes = model["components"]
        ids = [node["id"] for node in nodes]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError(f"{view}: duplicate or empty component IDs")
        for edge in model.get("connections", []):
            if edge["from"] not in ids or edge["to"] not in ids:
                raise ValueError(f"{view}: invalid connection endpoint")
        for boundary in model.get("boundaries", []):
            if not boundary["wraps"] or not set(boundary["wraps"]) <= set(ids):
                raise ValueError(f"{view}: invalid boundary membership")
        expected_icons = {node["id"] for node in nodes if node.get("tag", "").startswith("AWS")}
        if set(icons.get(view, {})) != expected_icons:
            raise ValueError(f"{view}: AWS icon map must cover exactly the AWS components")
        for node in nodes:
            if node["id"] in expected_icons:
                if node.get("icon") != "none" or icons[view][node["id"]] not in assets:
                    raise ValueError(f"{view}: AWS component requires an official mapped icon")
            if not node.get("sources"):
                raise ValueError(f"{view}: missing source references")
            for source in node["sources"]:
                source_path = regular(root, source["path"])
                count = len(source_path.read_text().splitlines())
                start, end = source.get("line", 1), source.get("end_line", source.get("line", 1))
                if not 1 <= start <= end <= count:
                    raise ValueError(f"{view}: source line range outside {source['path']}")
                identity = (revision, source["path"])
                if (root / ".git").exists() and identity not in verified_sources:
                    committed = subprocess.run(
                        ["git", "show", f"{revision}:{source['path']}"],
                        cwd=root,
                        capture_output=True,
                        check=False,
                    )
                    if committed.returncode or committed.stdout != source_path.read_bytes():
                        raise ValueError(
                            f"{view}: cited source differs from source revision: {source['path']}; "
                            "commit reviewed source, re-pin the model and rebuild"
                        )
                    verified_sources.add(identity)
        parser = Links()
        parser.feed(regular(folder / "public", f"{view}.html").read_text())
        for kind, path in (
            ("spec", model_path),
            ("icons", folder / "icons.json"),
            ("vendor", folder / "vendor.json"),
            ("style", folder / "style.css"),
            ("builder", root / "scripts/diagram-build.py"),
        ):
            if parser.bindings.get(f"showcase-{kind}-sha256") != [digest(path)]:
                raise ValueError(
                    f"{view}: stale HTML {kind} binding; rebuild before diagram-refresh"
                )
    public = folder / "public"
    regular(public, "index.html")
    for path in public.rglob("*"):
        if path.is_symlink():
            raise ValueError("Public diagram files cannot be symlinks")
        if path.suffix != ".html":
            continue
        parser = Links()
        parser.feed(path.read_text())
        for tag, key, link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme:
                if parsed.scheme == "data" or (
                    tag == "a" and key == "href" and parsed.scheme == "https"
                ):
                    continue
                raise ValueError(f"Remote runtime dependency in {path.name}: {link}")
            if parsed.netloc or parsed.path.startswith("/"):
                raise ValueError(f"Nonlocal artifact link in {path.name}: {link}")
            if parsed.path:
                target = path.parent / unquote(parsed.path)
                regular(public, str(target.relative_to(public)))

    receipts = json.loads((folder / "receipts.json").read_text())
    if receipts.get("archify_commit") != vendor["archify"]["commit"]:
        raise ValueError("Build receipts use a different Archify commit")
    if receipts.get("node") != vendor["archify"]["node_version"]:
        raise ValueError("Build receipts use a different pinned Node.js version")
    if set(receipts.get("views", {})) != set(VIEWS):
        raise ValueError("Build receipts must cover every diagram view")
    for view in VIEWS:
        receipt = receipts["views"][view]
        if receipt.get("specification_sha256") != digest(folder / f"{view}.json"):
            raise ValueError(f"{view}: stale build receipt specification binding")
        if receipt.get("artifact_sha256") != digest(folder / "public" / f"{view}.html"):
            raise ValueError(f"{view}: stale build receipt artifact binding")
        if receipt.get("gates") != {
            gate: "pass" for gate in ("validate", "deliver", "check", "browser-check")
        }:
            raise ValueError(f"{view}: build receipt requires all four Archify gates to pass")


def check(root=ROOT):
    validate(root)
    record = json.loads((root / DIAGRAMS / "provenance.json").read_text())
    if record.get("schema_version") != 1 or not record.get("review_note", "").strip():
        raise ValueError("Missing diagram review provenance")
    datetime.fromisoformat(record["reviewed_at"])
    for key, value in snapshot(root).items():
        if record.get(key) != value:
            if key == "source_globs":
                raise ValueError("Stale diagram source_globs; review the changed source mapping")
            old, new = record.get(key, {}), value
            changed = sorted(
                set(old) ^ set(new) | {p for p in set(old) & set(new) if old[p] != new[p]}
            )
            raise ValueError(
                f"Stale diagram {key}: {', '.join(changed[:12])}; review/build then diagram-refresh"
            )


def refresh(root, note):
    if not (root / ".git").exists():
        raise ValueError(
            "Refresh requires the Git checkout; archive exports only check saved provenance"
        )
    if not note.strip():
        raise ValueError("A concrete revalidation note is required")
    validate(root)
    record = {
        "schema_version": 1,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "review_note": note.strip(),
        **snapshot(root),
    }
    (root / DIAGRAMS / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")


def handler(public, allowed):
    class Preview(BaseHTTPRequestHandler):
        def do_GET(self):
            name = unquote(urlsplit(self.path).path).removeprefix("/") or "index.html"
            if name not in allowed:
                self.send_error(404)
                return
            try:
                data = regular(public, name).read_bytes()
            except ValueError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header(
                "Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream"
            )
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

    return Preview


def port(value):
    result = int(value)
    if not 1024 <= result <= 65535:
        raise argparse.ArgumentTypeError("Port must be in 1024..65535")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "refresh", "serve"))
    parser.add_argument("--note", default="")
    parser.add_argument("--port", type=port, default=8765)
    args = parser.parse_args()
    if args.command == "refresh":
        refresh(ROOT, args.note)
        print("Diagram provenance refreshed; semantic fidelity still requires human review")
    else:
        check()
        if args.command == "serve":
            public = ROOT / DIAGRAMS / "public"
            record = json.loads((ROOT / DIAGRAMS / "provenance.json").read_text())
            prefix = DIAGRAMS + "/public/"
            allowed = {
                name.removeprefix(prefix) for name in record["artifacts"] if name.startswith(prefix)
            }
            server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(public, allowed))
            print(f"Diagram: http://127.0.0.1:{args.port}/ — stop with Ctrl-C", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        else:
            print("Diagram freshness, sources, assets and structure passed (not semantic approval)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError) as error:
        raise SystemExit(str(error)) from error
