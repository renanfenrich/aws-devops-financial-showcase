"""Publish bounded scanner evidence without source excerpts or image environments."""

import argparse
import copy
import json
import re
from pathlib import Path

SECRET_FIELDS = ("RuleID", "Title", "Severity", "StartLine", "EndLine")


def without_excerpts(value):
    if isinstance(value, dict):
        return {
            key: without_excerpts(item)
            for key, item in value.items()
            if key not in {"Match", "Code", "ImageConfig"}
        }
    if isinstance(value, list):
        return [without_excerpts(item) for item in value]
    return value


def sanitized_report(report):
    """Fail closed on unknown top-level fields; secret findings use an allowlist."""
    safe = {
        key: copy.deepcopy(report[key])
        for key in (
            "SchemaVersion",
            "Trivy",
            "ReportID",
            "CreatedAt",
            "ArtifactID",
            "ArtifactName",
            "ArtifactType",
        )
        if key in report
    }
    metadata = report.get("Metadata", {})
    safe["Metadata"] = {
        key: copy.deepcopy(metadata[key])
        for key in ("Size", "OS", "ImageID", "RepoTags", "RepoDigests", "Reference")
        if key in metadata
    }
    safe["Results"] = []
    for result in report.get("Results", []):
        safe_result = {
            key: without_excerpts(result[key])
            for key in (
                "Target",
                "Class",
                "Type",
                "Packages",
                "MisconfSummary",
                "Vulnerabilities",
                "Misconfigurations",
            )
            if key in result
        }
        if "Secrets" in result:
            safe_result["Secrets"] = [
                {
                    **{key: finding[key] for key in SECRET_FIELDS if key in finding},
                    "File": result.get("Target"),
                }
                for finding in result["Secrets"]
            ]
        safe["Results"].append(safe_result)
    return safe


def publish(raw_directory, output_directory, run_id):
    """Only reports produced in this run can become public evidence."""
    output_directory.mkdir(parents=True, exist_ok=True)
    statuses = json.loads((raw_directory / "status.json").read_text())
    inspection = json.loads((raw_directory / "image-inspect.json").read_text())[0]
    labels = inspection.get("Config", {}).get("Labels") or {}
    revision = labels.get("org.opencontainers.image.revision", "")
    dirty = labels.get("io.showcase.dirty")
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "scanned_image_id": inspection["Id"],
        "image_source_revision": revision if re.fullmatch(r"[a-f0-9]{40}", revision) else None,
        "image_source_dirty": dirty if dirty in ("true", "false") else None,
        "scope": ["checkout filesystem including development dependencies", "API image only"],
        "other_images_scanned": False,
        "scanner_exit_codes": statuses,
        "high_critical": [],
    }
    complete = set(statuses) == {"filesystem", "image", "sbom"} and all(
        value in (0, 1) for value in statuses.values()
    )
    for name in ("filesystem.json", "image.json"):
        source = raw_directory / name
        if not source.is_file():
            complete = False
            continue
        data = sanitized_report(json.loads(source.read_text()))
        (output_directory / name).write_text(json.dumps(data, indent=2) + "\n")
        for result in data["Results"]:
            for kind in ("Vulnerabilities", "Misconfigurations", "Secrets"):
                for finding in result.get(kind, []):
                    if finding.get("Severity") in ("HIGH", "CRITICAL"):
                        summary["high_critical"].append(
                            {
                                "target": result.get("Target"),
                                "id": finding.get(
                                    "VulnerabilityID", finding.get("ID", finding.get("RuleID"))
                                ),
                                "severity": finding["Severity"],
                            }
                        )
    source = raw_directory / "sbom.spdx.json"
    if source.is_file():
        sbom = json.loads(source.read_text())
        # SPDX package relationships are safe inventory; omit free-text annotations/comments.
        sbom.pop("annotations", None)
        for package in sbom.get("packages", []):
            package.pop("annotations", None)
            package.pop("comment", None)
        (output_directory / "sbom.spdx.json").write_text(json.dumps(sbom, indent=2) + "\n")
    else:
        complete = False
    summary["reports_complete"] = complete
    summary["passed"] = (
        complete and all(value == 0 for value in statuses.values()) and not summary["high_critical"]
    )
    (output_directory / "scan.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("run_id")
    args = parser.parse_args()
    return publish(args.raw_directory, args.output_directory, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
