"""Runtime acceptance against the explicitly named, synthetic local kind lab."""

import argparse
import base64
import concurrent.futures
import contextlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/e2e"
CONTEXT = "kind-financial-showcase"
NS = "showcase"
KUBE = ["kubectl", "--kubeconfig", str(ROOT / ".local/kubeconfig"), "--context", CONTEXT]
NORMAL = {
    "system": "synthetic-finance",
    "component": "payments",
    "type": "normal",
    "message": "synthetic check passed",
}
FAILURE = {**NORMAL, "type": "failure", "message": "synthetic check failed"}
PROBE_IMAGE = (
    "docker.io/library/busybox:1.37.0@sha256:"
    "a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec"
)


def run(*args, data=None, check=True):
    result = subprocess.run(args, input=data, capture_output=True, check=False)
    if check and result.returncode:
        # Commands never receive secret arguments; cluster diagnostics stay local.
        raise RuntimeError(
            f"{args[0]} exited {result.returncode}: {result.stderr.decode()[-1500:]}"
        )
    return result


def kube(*args, data=None, check=True):
    return run(*KUBE, "-n", NS, *args, data=data, check=check)


def wait_for(check, timeout=60, description="condition"):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError:
            pass
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for {description}")


@contextlib.contextmanager
def forward(service, remote):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (OUT / f"forward-{service}.log").open("a") as log:
        process = subprocess.Popen(
            [
                *KUBE,
                "-n",
                NS,
                "port-forward",
                "--address=127.0.0.1",
                f"service/{service}",
                f"{port}:{remote}",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:

            def connected():
                if process.poll() is not None:
                    raise AssertionError(f"Port forward for {service} exited")
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return True

            wait_for(connected, timeout=30, description=f"{service} port forward")
            yield f"http://127.0.0.1:{port}"
        finally:
            process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
            if process.poll() is None:
                process.kill()
                process.wait()


def request(base, path, token=None, body=None, headers=None):
    merged = dict(headers or {})
    if token:
        merged["Authorization"] = "Bearer " + token
    if body is not None:
        merged["Content-Type"] = "application/json"
    req = urllib.request.Request(
        base + path, data=None if body is None else json.dumps(body).encode(), headers=merged
    )
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw.decode()
        return response.status, parsed


def env_values():
    return dict(
        line.split("=", 1)
        for line in (ROOT / ".local/k8s-secret.env").read_text().splitlines()
        if "=" in line
    )


def database_sql(sql, db="showcase"):
    return (
        kube("exec", "postgres-0", "--", "psql", "-U", "postgres", "-d", db, "-At", "-c", sql)
        .stdout.decode()
        .strip()
    )


def probe(name, allowed):
    labels = {"app": "network-probe"}
    if allowed:
        labels["access"] = "database"
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "namespace": NS, "labels": labels},
        "spec": {
            "automountServiceAccountToken": False,
            "restartPolicy": "Never",
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 10001,
                "runAsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "probe",
                    "image": PROBE_IMAGE,
                    "command": ["sh", "-c", "sleep 600"],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {"cpu": "10m", "memory": "8Mi"},
                        "limits": {"cpu": "100m", "memory": "32Mi"},
                    },
                }
            ],
        },
    }
    kube("apply", "-f", "-", data=json.dumps(pod).encode())
    kube("wait", "pod/" + name, "--for=condition=Ready", "--timeout=90s")
    return kube(
        "exec", name, "--", "sh", "-c", "nc -w 3 postgres 5432 </dev/null", check=False
    ).returncode


def load(base, token, duration, rate):
    count = int(duration * rate)
    started = time.perf_counter()
    prefix = "load-" + secrets.token_hex(8)

    def send(index):
        before = time.perf_counter()
        try:
            status, _ = request(
                base, "/v1/events", token, NORMAL, {"Idempotency-Key": f"{prefix}-{index}"}
            )
        except OSError, TimeoutError:
            status = 0
        return status, time.perf_counter() - before

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        pending = []
        for index in range(count):
            time.sleep(max(0, started + index / rate - time.perf_counter()))
            pending.append(pool.submit(send, index))
        results = [future.result() for future in pending]
    elapsed = time.perf_counter() - started
    latency = sorted(value for _, value in results)
    p95 = latency[max(0, int(len(latency) * 0.95) - 1)]
    errors = sum(status != 201 for status, _ in results)
    result = {
        "kind": "local-synthetic-benchmark",
        "transport": "kubectl port-forward service/showcase-api to one selected replica",
        "load_balancing_verified": False,
        "duration_requested_seconds": duration,
        "rate_requested_per_second": rate,
        "requests": count,
        "elapsed_seconds": round(elapsed, 3),
        "p95_milliseconds": round(p95 * 1000, 3),
        "non_201": errors,
        "http_5xx": sum(500 <= status < 600 for status, _ in results),
        "transport_errors": sum(status == 0 for status, _ in results),
        "acceptance_profile": duration == 120 and rate == 20,
        "passed": errors == 0 and p95 <= 0.5,
    }
    (OUT / "load.json").write_text(json.dumps(result, indent=2) + "\n")
    assert result["passed"], result
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-seconds", type=int, default=120)
    parser.add_argument("--load-rate", type=int, default=20)
    parser.add_argument("--gitops", action="store_true")
    args = parser.parse_args()
    assert 0 <= args.load_seconds <= 120 and 1 <= args.load_rate <= 20
    if (OUT / "report.json").exists():
        archive = ROOT / "artifacts/e2e-history" / str(time.time_ns())
        shutil.copytree(OUT, archive)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "local-runtime",
        "source_sha": run("git", "rev-parse", "HEAD").stdout.decode().strip(),
        "working_tree_dirty": bool(run("git", "status", "--porcelain").stdout),
        "platform_mode": (ROOT / ".local/platform-mode").read_text().strip(),
        "hardware": {"cpu_count": os.cpu_count(), "platform": platform.platform()},
        "checks": {},
        "passed": False,
    }
    token = env_values()["API_TOKEN"]
    checks = report["checks"]
    created_incident = None
    try:
        pods = json.loads(kube("get", "pods", "-l", "app=showcase-api", "-o", "json").stdout)
        report["runtime_images"] = [
            {"pod": pod["metadata"]["name"], "image_id": container["imageID"]}
            for pod in pods["items"]
            for container in pod["status"].get("containerStatuses", [])
        ]
        node_image = json.loads(
            run(
                "docker",
                "exec",
                "financial-showcase-control-plane",
                "crictl",
                "inspecti",
                "financial-showcase-api:local",
            ).stdout
        )
        labels = node_image.get("info", {}).get("imageSpec", {}).get("config", {}).get("Labels", {})
        report["loaded_kind_image"] = {
            "image_id": node_image["status"]["id"],
            "source_revision": labels.get("org.opencontainers.image.revision"),
            "working_tree_dirty": labels.get("io.showcase.dirty"),
        }
        loaded_ids = {*node_image["status"].get("repoDigests", []), node_image["status"]["id"]}
        assert report["runtime_images"] and all(
            item["image_id"].removeprefix("docker-pullable://") in loaded_ids
            for item in report["runtime_images"]
        ), "Running API replicas do not match the loaded kind image"
        if args.gitops:
            expected = report["platform_mode"].removeprefix("argocd-published:")
            assert report["loaded_kind_image"]["source_revision"] == expected
            assert report["loaded_kind_image"]["working_tree_dirty"] == "false"
        key = "e2e-" + secrets.token_hex(8)
        trace_id = secrets.token_hex(16)
        with (
            forward("showcase-api", 8080) as api,
            forward("prometheus", 9090) as prom,
            forward("tempo", 3200) as tempo,
            forward("grafana", 3000) as grafana,
        ):
            assert request(api, "/readyz")[0] == 200
            assert request(api, "/v1/incidents")[0] == 401
            assert (
                request(
                    api,
                    "/v1/events",
                    token,
                    {**NORMAL, "account": "rejected"},
                    {"Idempotency-Key": key + "-invalid"},
                )[0]
                == 422
            )
            checks["authentication_and_catalog_validation"] = True
            status, event = request(
                api,
                "/v1/events",
                token,
                FAILURE,
                {"Idempotency-Key": key, "traceparent": f"00-{trace_id}-{secrets.token_hex(8)}-01"},
            )
            assert status == 201 and event["incident_id"]
            created_incident = event["incident_id"]
            status, replay = request(api, "/v1/events", token, FAILURE, {"Idempotency-Key": key})
            assert status == 200 and replay == event
            assert request(api, "/v1/events", token, NORMAL, {"Idempotency-Key": key})[0] == 409
            checks["event_lifecycle_and_idempotency"] = {"incident_id": created_incident}

            def alert_firing():
                status, body = request(prom, "/api/v1/alerts")
                return status == 200 and any(
                    a["labels"]["alertname"] == "SyntheticIncidentOpen" and a["state"] == "firing"
                    for a in body["data"]["alerts"]
                )

            wait_for(alert_firing, timeout=60, description="synthetic incident alert")
            checks["alert_fired_from_persisted_incident"] = True
            status, incident = request(
                api, f"/v1/incidents/{event['incident_id']}/resolve", token, {}
            )
            assert status == 200 and incident["status"] == "resolved"
            assert (
                request(api, f"/v1/incidents/{event['incident_id']}/resolve", token, {})[0] == 200
            )
            checks["incident_resolution_is_idempotent"] = True

            def trace_received():
                status, body = request(tempo, "/api/traces/" + trace_id)
                return status == 200 and body

            wait_for(trace_received, timeout=60, description="OTel trace in Tempo")
            checks["trace_received_by_tempo"] = {"trace_id": trace_id}

            def metrics_replicas_ready():
                status, body = request(prom, "/api/v1/targets")
                targets = [
                    target
                    for target in body.get("data", {}).get("activeTargets", [])
                    if target.get("labels", {}).get("job") == "showcase-api"
                ]
                return (
                    status == 200
                    and len(targets) == 2
                    and all(target.get("health") == "up" for target in targets)
                )

            wait_for(metrics_replicas_ready, timeout=60, description="both API metrics targets")
            checks["prometheus_scrapes_each_api_replica"] = True
            grafana_password = (ROOT / ".local/grafana-password").read_text().strip()
            basic = base64.b64encode(f"showcase:{grafana_password}".encode()).decode()
            status, dashboard = request(
                grafana,
                "/api/dashboards/uid/financial-operations",
                headers={"Authorization": "Basic " + basic},
            )
            assert status == 200 and dashboard["dashboard"]["uid"] == "financial-operations"
            assert len(dashboard["dashboard"]["panels"]) == 4
            (OUT / "grafana-dashboard.json").write_text(
                json.dumps(dashboard["dashboard"], indent=2) + "\n"
            )
            checks["grafana_provisioned_dashboard_api"] = {
                "uid": dashboard["dashboard"]["uid"],
                "panels": 4,
            }
            if args.load_seconds:
                checks["load"] = load(api, token, args.load_seconds, args.load_rate)
            else:
                checks["load"] = {"status": "skipped", "reason": "explicit --load-seconds=0"}
        api_pods = json.loads(kube("get", "pods", "-l", "app=showcase-api", "-o", "json").stdout)[
            "items"
        ]
        before_uids = {p["metadata"]["uid"] for p in api_pods}
        kube("delete", "pod", api_pods[0]["metadata"]["name"], "--wait=true")

        def replacement_ready():
            pods = json.loads(kube("get", "pods", "-l", "app=showcase-api", "-o", "json").stdout)[
                "items"
            ]
            return (
                len(pods) == 2
                and any(p["metadata"]["uid"] not in before_uids for p in pods)
                and all(
                    any(
                        c["type"] == "Ready" and c["status"] == "True"
                        for c in p.get("status", {}).get("conditions", [])
                    )
                    for p in pods
                )
            )

        wait_for(replacement_ready, timeout=90, description="replacement API replica")
        with forward("showcase-api", 8080) as api:
            status, items = request(api, "/v1/incidents", token)
            assert status == 200 and any(i["id"] == event["incident_id"] for i in items["items"])
        checks["api_restart_preserves_incident"] = True
        counts = database_sql(
            "SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM incidents)"
        )
        kube("delete", "pod", "postgres-0", "--wait=true")
        kube("wait", "pod/postgres-0", "--for=condition=Ready", "--timeout=120s")
        assert (
            database_sql("SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM incidents)")
            == counts
        )
        checks["postgres_restart_preserves_pvc_data"] = True
        restricted = database_sql(
            "SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname='app'"
        )
        assert restricted == "f"
        checks["database_app_role_is_restricted"] = True
        restore_started = time.perf_counter()
        digest_sql = (
            "SELECT md5(coalesce(string_agg(row_to_json(e)::text, '' ORDER BY e.id), '')) "
            "FROM events e; "
            "SELECT md5(coalesce(string_agg(row_to_json(i)::text, '' ORDER BY i.id), '')) "
            "FROM incidents i"
        )
        original_digest = database_sql(digest_sql)
        dump = kube(
            "exec", "postgres-0", "--", "pg_dump", "-U", "postgres", "-d", "showcase", "-Fc"
        ).stdout
        kube(
            "exec",
            "postgres-0",
            "--",
            "dropdb",
            "-U",
            "postgres",
            "--if-exists",
            "showcase_restore_e2e",
        )
        kube(
            "exec",
            "postgres-0",
            "--",
            "createdb",
            "-U",
            "postgres",
            "-O",
            "app",
            "showcase_restore_e2e",
        )
        try:
            kube(
                "exec",
                "-i",
                "postgres-0",
                "--",
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                "showcase_restore_e2e",
                data=dump,
            )
            assert (
                database_sql(
                    "SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM incidents)",
                    "showcase_restore_e2e",
                )
                == counts
            )
            assert database_sql(digest_sql, "showcase_restore_e2e") == original_digest
        finally:
            kube(
                "exec",
                "postgres-0",
                "--",
                "dropdb",
                "-U",
                "postgres",
                "--if-exists",
                "showcase_restore_e2e",
            )
        checks["backup_restore_to_separate_database"] = {
            "event_incident_counts": counts,
            "dump_bytes": len(dump),
            "ordered_rows_md5": original_digest.splitlines(),
            "restore_elapsed_seconds": round(time.perf_counter() - restore_started, 3),
            "recovery_scope": "local logical snapshot with synthetic writes paused",
            "lost_rows_relative_to_snapshot": 0,
        }
        try:
            assert probe("showcase-probe-allowed", True) == 0
            assert probe("showcase-probe-denied", False) != 0
            kube(
                "exec",
                "showcase-probe-denied",
                "--",
                "nslookup",
                "postgres.showcase.svc.cluster.local.",
            )
        finally:
            kube(
                "delete",
                "pod",
                "showcase-probe-allowed",
                "showcase-probe-denied",
                "--ignore-not-found",
                "--wait=false",
                check=False,
            )
        checks["calico_allowed_denied_and_dns"] = True
        rbac = kube(
            "auth",
            "can-i",
            "get",
            "secrets",
            "--as=system:serviceaccount:showcase:showcase-api",
            check=False,
        )
        assert rbac.stdout.decode().strip() == "no"
        checks["api_has_no_secret_read_rbac"] = True
        if args.gitops:
            assert report["platform_mode"].startswith("argocd-published:")
            expected = report["platform_mode"].split(":", 1)[1]

            def argo_synced():
                app = json.loads(
                    run(
                        *KUBE,
                        "-n",
                        "argocd",
                        "get",
                        "application",
                        "financial-showcase",
                        "-o",
                        "json",
                    ).stdout
                )
                return (
                    app["status"].get("sync", {}).get("status") == "Synced"
                    and app["status"]["sync"].get("revision") == expected
                    and app["status"].get("health", {}).get("status") == "Healthy"
                )

            wait_for(argo_synced, timeout=120, description="exact-SHA GitOps sync")
            kube("scale", "deployment/showcase-api", "--replicas=1")
            wait_for(
                lambda: (
                    json.loads(kube("get", "deployment/showcase-api", "-o", "json").stdout)["spec"][
                        "replicas"
                    ]
                    == 2
                ),
                timeout=90,
                description="Argo drift correction",
            )
            wait_for(argo_synced, timeout=90, description="GitOps healthy after drift correction")
            checks["argocd_exact_sha_and_drift_correction"] = {
                "revision": expected,
                "replicas_restored": 2,
            }
        else:
            checks["gitops"] = {
                "status": "pending",
                "reason": "local Helm bootstrap, rerun --gitops after published SHA sync",
            }
        with forward("showcase-api", 8080) as api:
            status, spec = request(api, "/openapi.json", token)
            assert status == 200
            (OUT / "openapi.json").write_text(json.dumps(spec, indent=2) + "\n")
        report["passed"] = True
    finally:
        if not report["passed"] and created_incident:
            try:
                with forward("showcase-api", 8080) as api:
                    status, _ = request(api, f"/v1/incidents/{created_incident}/resolve", token, {})
                    report["failed_run_fixture_cleanup"] = status == 200
            except OSError, RuntimeError, AssertionError:
                report["failed_run_fixture_cleanup"] = False
        (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "checks": len(checks),
                "report": "artifacts/e2e/report.json",
            }
        )
    )


if __name__ == "__main__":
    main()
