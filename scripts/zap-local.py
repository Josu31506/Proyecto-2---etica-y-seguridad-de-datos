"""Escaneo pasivo por rol, en loopback y con una base sintética temporal."""

import argparse
from collections import Counter
from contextlib import ExitStack
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        url = dict(attrs).get("src" if tag == "script" else "href", "")
        if url.startswith("/_next/static/") and (".js" in url or ".css" in url):
            self.urls.add(url)


def wait_for(check, process, seconds=90):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError("El proceso terminó antes de estar disponible.")
        try:
            if check():
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.5)
    raise RuntimeError(
        "Tiempo de espera agotado. Revise la instalación de ZAP/Java y los puertos."
    )


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def scan(zap_jar, out):
    api = "http://127.0.0.1:18098"
    front = "http://127.0.0.1:13098"
    proxy = "http://127.0.0.1:18099"
    for port in (18098, 13098, 18099):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    with (
        tempfile.TemporaryDirectory(
            prefix="alzace-zap-", ignore_cleanup_errors=True
        ) as temporary,
        ExitStack() as stack,
    ):
        temp = Path(temporary)
        key = secrets.token_hex(32)
        env = {
            **os.environ,
            "ALZACE_MODE": "demo",
            "DATABASE_URL": "",
            "ALZACE_STATE": str(temp / "state"),
            "ALZACE_FRONTEND_DIST": ".next-zap",
            "FRONTEND_ORIGIN": front,
            "DEMO_SHORTCUTS": "1",
            "API_INTERNAL_URL": api,
            "NEXT_TELEMETRY_DISABLED": "1",
        }
        subprocess.run(
            [sys.executable, "-m", "backend.cli", "init"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
        )

        def launch(args, cwd=ROOT):
            process = subprocess.Popen(
                args,
                cwd=cwd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            stack.callback(stop, process)
            return process

        clean = stack.enter_context(httpx.Client(trust_env=False, timeout=4))
        back = launch(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18098",
                "--no-access-log",
            ]
        )
        wait_for(lambda: clean.get(api + "/api/health").is_success, back)
        subprocess.run(
            [shutil.which("node"), "node_modules/next/dist/bin/next", "build"],
            cwd=ROOT / "frontend",
            env=env,
            check=True,
            capture_output=True,
        )
        web = launch(
            [
                shutil.which("node"),
                "node_modules/next/dist/bin/next",
                "start",
                "--hostname",
                "127.0.0.1",
                "--port",
                "13098",
            ],
            ROOT / "frontend",
        )
        wait_for(lambda: clean.get(front).is_success, web)
        zap = launch(
            [
                shutil.which("java"),
                "-Xmx512m",
                "-jar",
                str(zap_jar.resolve()),
                "-daemon",
                "-silent",
                "-host",
                "127.0.0.1",
                "-port",
                "18099",
                "-dir",
                str(temp / "zap"),
                "-config",
                "api.key=" + key,
            ],
            zap_jar.resolve().parent,
        )

        def control(path, **params):
            return (
                clean.get(
                    proxy + "/JSON/" + path + "/",
                    params=params,
                    headers={"X-ZAP-API-Key": key},
                )
                .raise_for_status()
                .json()
            )

        wait_for(lambda: control("core/view/version").get("version"), zap)
        site = stack.enter_context(
            httpx.Client(
                base_url=front,
                proxy=proxy,
                trust_env=False,
                timeout=30,
                headers={"X-Alzace-Request": "web", "Origin": front},
            )
        )
        paths = []

        def visit(method, path, expected=200, **kwargs):
            response = site.request(method, path, **kwargs)
            if response.status_code != expected:
                raise RuntimeError(
                    f"Respuesta inesperada {method} {path}: {response.status_code}"
                )
            paths.append((method, path))
            return response

        doc = visit("GET", "/")
        assets = Assets()
        assets.feed(doc.text)
        for asset in sorted(assets.urls)[:5]:
            visit("GET", asset)
        visit("GET", "/api/health")
        visit("GET", "/api/clients", 401)
        for alias in ("cliente", "entrenador", "administrador"):
            visit("POST", "/api/auth/demo", json={"alias": alias})
            visit("GET", "/api/me")
            if alias != "administrador":
                visit("GET", "/api/clients")
                visit("GET", "/api/clients/demo-lucia")
                visit("GET", "/api/clients/demo-mateo", 403)
            if alias == "cliente":
                visit("PUT", "/api/me/consent", json={"allow": False})
            if alias == "entrenador":
                visit("GET", "/api/trainer/alerts")
            if alias == "administrador":
                visit("GET", "/api/admin/audit")
                visit("GET", "/api/analytics")
            visit("POST", "/api/auth/logout")
        # Wait for the passive scanner to finish its queue.
        for _ in range(2):
            time.sleep(1.5)
            wait_for(
                lambda: int(control("pscan/view/recordsToScan")["recordsToScan"]) == 0,
                zap,
            )
        recorded = int(
            control("core/view/numberOfMessages", baseurl=front)["numberOfMessages"]
        )
        if recorded < len(paths):
            raise RuntimeError("ZAP no registró todo el recorrido.")
        alerts = control("core/view/alerts", baseurl=front, start=0, count=1000)[
            "alerts"
        ]
        summary = Counter((a["pluginId"], a["risk"], a["alert"]) for a in alerts)
        evidence = {
            "tool": "ZAP " + control("core/view/version")["version"],
            "type": "pasivo sobre HTTP local con frontend compilado en producción",
            "roles": ["sin sesión", "cliente", "entrenador", "administrador"],
            "messages": recorded,
            "alerts": [
                {"id": i, "risk": risk, "finding": msg, "instances": n}
                for (i, risk, msg), n in sorted(summary.items())
            ],
            "limits": "Cobertura de rutas visitadas con datos sintéticos. Repetir con TLS, proveedor de identidad y configuración final en staging.",
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf8"
        )
        print(
            f"Escaneo completado: {recorded} solicitudes y {len(summary)} tipos de alerta."
        )
        try:
            control("core/action/shutdown")
            zap.wait(timeout=10)
        except (httpx.HTTPError, subprocess.TimeoutExpired):
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "jar", type=Path, help="JAR de la distribución oficial completa de ZAP"
    )
    args = parser.parse_args()
    scan(args.jar, ROOT / "evidence/zap-pasivo.json")
