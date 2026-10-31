"""Freshness and serving boundaries of the committed infrastructure diagrams."""

import argparse
import hashlib
import http.client
import importlib.util
import json
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/diagram.py"
SPEC = importlib.util.spec_from_file_location("diagram", PATH)
diagram = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagram)


def write_json(path, value):
    path.write_text(json.dumps(value))


def commit_source(root):
    subprocess.run(["git", "add", "infra"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Diagram test",
            "-c",
            "user.email=diagram@example.invalid",
            "commit",
            "-qm",
            "test source snapshot",
        ],
        cwd=root,
        check=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def bind_html(root, view):
    folder = root / "docs/diagrams"
    bindings = "".join(
        f'<meta name="showcase-{kind}-sha256" content="{diagram.digest(path)}">'
        for kind, path in (
            ("spec", folder / f"{view}.json"),
            ("icons", folder / "icons.json"),
            ("vendor", folder / "vendor.json"),
            ("style", folder / "style.css"),
            ("builder", root / "scripts/diagram-build.py"),
        )
    )
    (folder / "public" / f"{view}.html").write_text(
        "<!doctype html>" + bindings + '<a href="index.html">Overview</a>'
    )


def write_receipts(root):
    folder = root / "docs/diagrams"
    vendor = json.loads((folder / "vendor.json").read_text())
    write_json(
        folder / "receipts.json",
        {
            "archify_commit": vendor["archify"]["commit"],
            "node": vendor["archify"]["node_version"],
            "views": {
                view: {
                    "specification_sha256": diagram.digest(folder / f"{view}.json"),
                    "artifact_sha256": diagram.digest(folder / "public" / f"{view}.html"),
                    "gates": {
                        gate: "pass" for gate in ("validate", "deliver", "check", "browser-check")
                    },
                }
                for view in diagram.VIEWS
            },
        },
    )


@pytest.fixture
def checkout(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    folder = tmp_path / "docs/diagrams"
    public = folder / "public"
    public.mkdir(parents=True)
    (folder / "style.css").write_text("/* diagram style */\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/diagram-build.py").write_text("# diagram builder\n")
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra/main.tf").write_text("# initial foundation\n")
    (tmp_path / "infra/other.tf").write_text("# additional foundation source\n")
    revision = commit_source(tmp_path)
    asset = public / "assets/aws/storage.svg"
    asset.parent.mkdir(parents=True)
    asset.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"></svg>')
    spec = {
        "version": "test",
        "url": "https://aws.amazon.com/architecture/icons/",
        "sha256": "0" * 64,
    }
    write_json(
        folder / "vendor.json",
        {
            "archify": {
                **spec,
                "commit": "0" * 40,
                "node_version": "v26.13.0",
                "url": "https://codeload.github.com/tt-a1i/archify/tar.gz/" + "0" * 40,
            },
            "aws_icons": {
                **spec,
                "url": "https://d1.awsstatic.com/architecture-icon-release/test.zip",
                "assets": {
                    "assets/aws/storage.svg": {
                        "member": "official/storage.svg",
                        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                    }
                },
            },
        },
    )
    write_json(folder / "icons.json", {"aws": {"storage": "assets/aws/storage.svg"}})
    for view in diagram.VIEWS:
        node = {"id": "storage", "sources": [{"path": "infra/main.tf", "line": 1}]}
        if view == "aws":
            node.update(tag="AWS planned", icon="none")
        write_json(
            folder / f"{view}.json",
            {
                "meta": {"repository": {"revision": revision}},
                "components": [node],
            },
        )
        bind_html(tmp_path, view)
    (public / "index.html").write_text('<!doctype html><a href="aws.html">AWS</a>')
    write_receipts(tmp_path)
    diagram.refresh(tmp_path, "Reviewed initial topology against source")
    return tmp_path


@pytest.mark.parametrize("change", ("edit", "addition", "deletion"))
def test_infrastructure_changes_require_explicit_revalidation(checkout, change):
    source = checkout / "infra/other.tf"
    if change == "edit":
        source.write_text("# changed foundation\n")
    elif change == "addition":
        (checkout / "infra/new.tf").write_text("# new infrastructure\n")
    else:
        # Delete an uncited but tracked infrastructure source as a realistic removal.
        source = checkout / "infra/old.tf"
        source.write_text("# removed infrastructure\n")
        subprocess.run(["git", "add", "infra/old.tf"], cwd=checkout, check=True)
        diagram.refresh(checkout, "Reviewed removable infrastructure")
        source.unlink()
    with pytest.raises(ValueError, match="Stale diagram sources"):
        diagram.check(checkout)
    diagram.refresh(checkout, f"Reviewed {change}; topology unchanged")
    diagram.check(checkout)


def test_refresh_cannot_hide_broken_edges_or_modified_official_asset(checkout):
    path = checkout / "docs/diagrams/aws.json"
    original = json.loads(path.read_text())
    write_json(path, {**original, "connections": [{"from": "storage", "to": "invented"}]})
    with pytest.raises(ValueError, match="invalid connection"):
        diagram.refresh(checkout, "Attempted refresh")
    write_json(path, original)
    (checkout / "docs/diagrams/public/assets/aws/storage.svg").write_text("altered icon")
    with pytest.raises(ValueError, match="asset integrity"):
        diagram.refresh(checkout, "Attempted refresh")


def test_missing_source_range_icon_and_remote_dependency_fail(checkout):
    folder = checkout / "docs/diagrams"
    path = folder / "aws.json"
    model = json.loads(path.read_text())
    model["components"][0]["sources"][0]["end_line"] = 100
    write_json(path, model)
    with pytest.raises(ValueError, match="source line range"):
        diagram.validate(checkout)
    model["components"][0]["sources"][0]["end_line"] = 1
    write_json(path, model)
    bind_html(checkout, "aws")
    write_json(folder / "icons.json", {})
    for view in diagram.VIEWS:
        bind_html(checkout, view)
    with pytest.raises(ValueError, match="icon map"):
        diagram.validate(checkout)
    write_json(folder / "icons.json", {"aws": {"storage": "assets/aws/storage.svg"}})
    for view in diagram.VIEWS:
        bind_html(checkout, view)
    (folder / "public/index.html").write_text(
        '<script src="https://cdn.invalid/viewer.js"></script>'
    )
    with pytest.raises(ValueError, match="Remote runtime dependency"):
        diagram.validate(checkout)


def test_jenkins_archive_retains_freshness_check(checkout):
    import shutil

    shutil.rmtree(checkout / ".git")
    (checkout / ".source-sha").write_text("a" * 40 + "\n")
    diagram.check(checkout)
    (checkout / "infra/added.tf").write_text("# new source\n")
    with pytest.raises(ValueError, match="Stale diagram sources"):
        diagram.check(checkout)


def test_preview_serves_only_manifest_public_files_and_rejects_symlinks(checkout):
    public = checkout / "docs/diagrams/public"
    (checkout / "secret.txt").write_text("not public")
    (public / "unlisted.txt").write_text("not listed in manifest")
    (public / "link.txt").symlink_to(checkout / "secret.txt")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), diagram.handler(public, {"index.html", "link.txt"})
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(*server.server_address)
        for path, status in (
            ("/", 200),
            ("/../secret.txt", 404),
            ("/%2e%2e/secret.txt", 404),
            ("/unlisted.txt", 404),
            ("/.git/config", 404),
            ("/link.txt", 404),
        ):
            connection.request("GET", path)
            response = connection.getresponse()
            assert response.status == status
            assert b"not public" not in response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("value", ("0", "1023", "65536"))
def test_preview_rejects_out_of_range_ports(value):
    with pytest.raises(argparse.ArgumentTypeError):
        diagram.port(value)


def test_model_changes_cannot_refresh_stale_html(checkout):
    path = checkout / "docs/diagrams/aws.json"
    model = json.loads(path.read_text())
    model["components"][0]["label"] = "Reviewed name"
    write_json(path, model)
    with pytest.raises(ValueError, match="stale HTML spec binding"):
        diagram.refresh(checkout, "Updated diagram label")
    bind_html(checkout, "aws")
    write_receipts(checkout)
    diagram.refresh(checkout, "Updated diagram label and artifact")
    diagram.check(checkout)


def test_changed_cited_sources_require_committed_repin_and_rebuild(checkout):
    (checkout / "infra/main.tf").write_text("# reviewed change to cited foundation\n")
    with pytest.raises(ValueError, match="cited source differs from source revision"):
        diagram.refresh(checkout, "Attempted blind refresh")
    revision = commit_source(checkout)
    for view in diagram.VIEWS:
        path = checkout / f"docs/diagrams/{view}.json"
        model = json.loads(path.read_text())
        model["meta"]["repository"]["revision"] = revision
        write_json(path, model)
        bind_html(checkout, view)
    write_receipts(checkout)
    diagram.refresh(
        checkout, "Committed and reviewed source; repinned models and rebuilt artifacts"
    )
    diagram.check(checkout)


@pytest.mark.parametrize(
    "tag",
    (
        '<link rel="stylesheet" href="https://cdn.invalid/style.css">',
        '<image href="https://cdn.invalid/icon.svg">',
        '<use href="https://cdn.invalid/icons.svg#cloud">',
    ),
)
def test_https_href_on_runtime_elements_is_rejected(checkout, tag):
    (checkout / "docs/diagrams/public/index.html").write_text(tag)
    with pytest.raises(ValueError, match="Remote runtime dependency"):
        diagram.validate(checkout)


@pytest.mark.parametrize(
    "filename",
    (
        "docs/diagrams/icons.json",
        "docs/diagrams/vendor.json",
        "docs/diagrams/style.css",
        "scripts/diagram-build.py",
    ),
)
def test_build_input_change_requires_artifact_rebuild(checkout, filename):
    path = checkout / filename
    if path.suffix == ".json":
        model = json.loads(path.read_text())
        # Harmless metadata still changes the exact build input fingerprint.
        model["review_note"] = "Revalidated assets"
        write_json(path, model)
    else:
        path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="stale HTML .* binding"):
        diagram.refresh(checkout, "Inputs changed without rebuild")


def test_failed_partial_rebuild_cannot_refresh_with_stale_receipts(checkout):
    path = checkout / "docs/diagrams/aws.json"
    model = json.loads(path.read_text())
    model["components"][0]["label"] = "Rebuilt but not fully finalized"
    write_json(path, model)
    bind_html(checkout, "aws")
    with pytest.raises(ValueError, match="stale build receipt specification binding"):
        diagram.refresh(checkout, "Cannot bless failed late rebuild")
    write_receipts(checkout)
    diagram.refresh(checkout, "All views rebuilt with matching passing receipts")
    diagram.check(checkout)


@pytest.mark.parametrize("invalid", ("artifact", "gate", "archify", "node"))
def test_build_receipts_require_exact_output_gates_and_tools(checkout, invalid):
    path = checkout / "docs/diagrams/receipts.json"
    receipts = json.loads(path.read_text())
    if invalid == "artifact":
        receipts["views"]["local"]["artifact_sha256"] = "0" * 64
    elif invalid == "gate":
        receipts["views"]["local"]["gates"]["browser-check"] = "fail"
    elif invalid == "archify":
        receipts["archify_commit"] = "1" * 40
    else:
        receipts["node"] = "v0.0.0"
    write_json(path, receipts)
    with pytest.raises(ValueError, match="(receipt|receipts)"):
        diagram.refresh(checkout, "Cannot bless invalid receipt")
