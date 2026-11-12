"""Supervisa la API y el frontend compilado en la máquina del equipo."""

from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError

root = Path(__file__).resolve().parents[1]
front = root / "frontend"
state = root / ".local"
node = shutil.which("node")
if not node or not (front / ".next/BUILD_ID").is_file():
    sys.exit("Ejecuta primero scripts/preparar.ps1 o compila el frontend.")
for port in (3000, 8000):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            sys.exit(
                f"El puerto {port} está ocupado. Si Alzace está en ejecución, abre http://127.0.0.1:3000."
            )
env = {
    **os.environ,
    "ALZACE_MODE": "demo",
    "DATABASE_URL": "",
    "ALZACE_STATE": str(state),
    "FRONTEND_ORIGIN": "http://127.0.0.1:3000",
    "NEXT_TELEMETRY_DISABLED": "1",
}
subprocess.run(
    [sys.executable, "-m", "backend.cli", "init"], cwd=root, env=env, check=True
)


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


with ExitStack() as stack:

    def start(args, folder, name):
        log = stack.enter_context((state / (name + ".log")).open("ab"))
        process = subprocess.Popen(
            args,
            cwd=folder,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stack.callback(stop, process)
        return process

    api = start(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        root,
        "api",
    )
    web = start(
        [
            node,
            "node_modules/next/dist/bin/next",
            "start",
            "--hostname",
            "127.0.0.1",
            "--port",
            "3000",
        ],
        front,
        "web",
    )
    try:
        for _ in range(45):
            if api.poll() is not None or web.poll() is not None:
                sys.exit("Revisa .local/api.log y .local/web.log.")
            try:
                with urlopen("http://127.0.0.1:3000/api/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, URLError):
                time.sleep(1)
        else:
            sys.exit("No se pudo conectar con la API a través del frontend.")
        print("Alzace: http://127.0.0.1:3000. Ctrl+C detiene la demo.", flush=True)
        while api.poll() is None and web.poll() is None:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
