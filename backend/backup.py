"""Encrypted offline copies for the SQLite demonstration. Restore tests never roll back the live DP ledger."""

import argparse, json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .config import Settings
from . import store as s
from .vault import b64, raw, read_ring, write_private, decrypt
from .training import targets

MAGIC = b"ALZACE-SNAPSHOT-1\n"


def backup_key(cfg, create=False):
    p = cfg.directory / "backup-key.json"
    if create and not p.exists():
        write_private(p, {"key": b64(os.urandom(32))})
    return raw(json.loads(p.read_text(encoding="utf8"))["key"])


def snapshot(cfg, dest):
    if cfg.mode != "demo":
        raise ValueError(
            "En PostgreSQL, use la política de respaldos del despliegue (ver docs/operacion.md)."
        )
    dest = Path(dest).resolve()
    if dest.is_relative_to(cfg.directory.resolve()):
        raise ValueError("El respaldo debe estar fuera del directorio de la base")
    dest.mkdir(parents=True, exist_ok=True)
    key = backup_key(cfg, create=True)
    engine = s.connect(cfg)
    path = Path(engine.url.database).resolve()
    with (
        closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source,
        closing(sqlite3.connect(":memory:")) as copy,
    ):
        source.backup(copy)
        # An old backup must not resurrect sessions.
        copy.execute("DELETE FROM sessions")
        copy.commit()
        snapshot_bytes = copy.serialize()
    nonce = os.urandom(12)
    name = "alzace-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".azb"
    output = dest / name
    with output.open("xb") as f:
        f.write(MAGIC + nonce + AESGCM(key).encrypt(nonce, snapshot_bytes, MAGIC))
    with engine.begin() as c:
        s.record(c, "operador", "respaldo.crear")
    engine.dispose()
    return output


def verify(cfg, path):
    if cfg.mode != "demo":
        raise ValueError("Esta prueba de restauración es para el prototipo SQLite.")
    sealed = Path(path).read_bytes()
    if not sealed.startswith(MAGIC):
        raise ValueError("Formato desconocido")
    n = len(MAGIC)
    plain = AESGCM(backup_key(cfg)).decrypt(sealed[n : n + 12], sealed[n + 12 :], MAGIC)
    with closing(sqlite3.connect(":memory:")) as check:
        check.deserialize(plain)
        check.row_factory = sqlite3.Row
        if (
            check.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or check.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise ValueError("Restauración inconsistente")
        ring = read_ring(cfg)
        count = 0
        for name in [s.metrics.name, s.research.name, targets.name]:
            for r in check.execute("SELECT * FROM " + name):
                decrypt(ring, name, r)
                count += 1
        spent = check.execute("SELECT spent FROM dp_budget WHERE id=1").fetchone()[0]
        if (
            spent
            != check.execute(
                "SELECT COALESCE(SUM(epsilon_milli),0) FROM dp_releases"
            ).fetchone()[0]
        ):
            raise ValueError("Historial del presupuesto inconsistente")
        if check.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]:
            raise ValueError("Incluye sesiones activas")
    eng = s.connect(cfg)
    with eng.begin() as c:
        s.record(c, "operador", "respaldo.verificar")
    eng.dispose()
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "verify"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    cfg = Settings.load()
    if args.action == "create":
        print(snapshot(cfg, args.path))
    else:
        print(
            "Restauración aislada verificada. Registros cifrados comprobados:",
            verify(cfg, args.path),
        )
