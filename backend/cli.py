"""Local operator tools; invoke from repository root (python -m backend.cli --help)."""

import argparse, getpass, os, random, secrets
from datetime import timedelta
from pathlib import Path
from uuid import UUID
import bcrypt
from sqlalchemy import select, update
from . import store as s
from .administration import incidents  # noqa: F401 -- include the incident table in CLI initialization
from .config import Settings
from .vault import read_ring, encrypt, decrypt, pseudo, b64, write_private
from .dataio import read_activity
from .domain import today, due
from .training import targets, default_targets

DEMO = {
    "cliente": "demo-lucia",
    "otro": "demo-mateo",
    "entrenador": "demo-entrenador",
    "administrador": "demo-administrador",
}


def seed(c, ring):
    if c.execute(select(s.users.c.id).limit(1)).first():
        return
    rng = random.Random(3031)
    anchor = today()

    def add(**fields):
        c.execute(s.users.insert().values(source="sintetico", **fields))

    add(
        id=DEMO["entrenador"],
        name="Diego Ríos",
        role="entrenador",
        email="entrenador@demo.invalid",
    )
    add(id="demo-entrenadora", name="Eva Lira", role="entrenador")
    add(
        id=DEMO["administrador"],
        name="Alex Vega",
        role="administrador",
        email="admin@demo.invalid",
    )
    for i in range(36):
        owner = [DEMO["cliente"], DEMO["otro"]][i] if i < 2 else "demo-" + str(i)
        add(
            id=owner,
            name=["Lucía Valle", "Mateo Rojas"][i]
            if i < 2
            else f"Deportista {i + 1:02}",
            role="cliente",
            trainer=DEMO["entrenador"] if i % 2 == 0 else "demo-entrenadora",
            email=(["cliente@demo.invalid", "otro@demo.invalid"][i] if i < 2 else None),
            analytics=i >= 2,
            consent_at=s.now() if i >= 2 else None,
            consent_version="demo-v1" if i >= 2 else None,
        )
        base = rng.randrange(12, 75)
        for offset in range(65):
            day = (anchor - timedelta(days=offset)).isoformat()
            minutes = max(0, min(180, base + rng.randrange(-15, 23)))
            val = {
                "minutes": minutes,
                "steps": max(0, minutes * 100 + rng.randrange(0, 2800)),
                "sleep": rng.randrange(350, 500),
                "pulse": rng.randrange(58, 89),
                "weight": round(65 + i * 0.4 + offset * 0.012, 1),
                "fat": round(23 + i * 0.12 + offset * 0.014, 2),
            }
            c.execute(
                s.metrics.insert().values(
                    owner=owner,
                    day=day,
                    **encrypt(ring, s.metrics.name, owner, day, val),
                )
            )
        for offset, title, done in (
            (-7, "Fuerza funcional", True),
            (-4, "Movilidad y control", False),
            (-2, "Circuito de resistencia", True),
            (0, "Sesión de movilidad", False),
            (2, "Fuerza y equilibrio", False),
        ):
            day = (anchor + timedelta(days=offset)).isoformat()
            c.execute(
                s.plans.insert().values(
                    id=s.uid(),
                    owner=owner,
                    day=day,
                    label=title,
                    done=done,
                    alert_at=due(day),
                )
            )
    default_targets(c, ring)
    s.record(c, "sistema", "demo.inicializar")


def import_study(c, ring, paths):
    rows, rep = read_activity(paths)
    # Serialize imports and publications of the fixed study cohort.
    c.execute(update(s.ledger).where(s.ledger.c.id == 1).values(spent=s.ledger.c.spent))
    released = c.execute(
        select(s.releases.c.query_key)
        .where(s.releases.c.query_key.like("mean-v1:estudio:%"))
        .limit(1)
    ).first()
    for (subject, day), data in rows.items():
        owner = pseudo(ring, subject)
        previous = (
            c.execute(
                select(s.research).where(
                    s.research.c.owner == owner, s.research.c.day == day
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if decrypt(ring, s.research.name, previous) != data:
                raise ValueError(
                    "El archivo contradice una medición previamente importada."
                )
            continue
        if released:
            raise ValueError(
                "El estudio ya tiene publicaciones: el conjunto de origen está cerrado."
            )
        payload = encrypt(ring, s.research.name, owner, day, data)
        s.upsert(c, s.research, dict(owner=owner, day=day, **payload), ["owner", "day"])
    s.upsert(c, s.study_sources, {"name": "fitbit"}, ["name"])
    s.record(c, "operador", "estudio.importar")
    return len(rows), rep


def reencrypt(c, ring):
    for table in (s.metrics, s.research, targets):
        for row in (
            c.execute(select(table).where(table.c.version != ring["active"]))
            .mappings()
            .all()
        ):
            data = decrypt(ring, table.name, row)
            c.execute(
                update(table)
                .where(table.c.owner == row["owner"], table.c.day == row["day"])
                .values(**encrypt(ring, table.name, row["owner"], row["day"], data))
            )
    s.record(c, "operador", "claves.rotar")


def main():
    ap = argparse.ArgumentParser(description="Administración local de Alzace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("rotate")
    imp = sub.add_parser("import-fitbit")
    imp.add_argument("files", type=Path, nargs="+")
    pw = sub.add_parser("password")
    pw.add_argument("alias", choices=DEMO)
    pr = sub.add_parser("provision")
    pr.add_argument("uuid", type=UUID)
    pr.add_argument("role", choices=["cliente", "entrenador", "administrador"])
    pr.add_argument("name")
    pr.add_argument("--trainer", type=UUID)
    args = ap.parse_args()
    cfg = Settings.load()
    engine = s.connect(cfg)
    if args.cmd == "init":
        s.initialize(engine)
        ring = read_ring(cfg, create=True)
        if cfg.mode == "demo":
            with engine.begin() as c:
                seed(c, ring)
        print("Esquema preparado. Modo:", cfg.mode)
        return
    ring = read_ring(cfg)
    if args.cmd == "import-fitbit":
        with engine.begin() as c:
            n, rep = import_study(c, ring, args.files)
        print(
            f"{n} pares persona-día procesados, {rep} duplicados idénticos. Solo analítica del estudio."
        )
    elif args.cmd == "rotate":
        # Rotate during a maintenance window. Retain previous versions for historical backups.
        if cfg.mode == "demo":
            ver = "k-" + secrets.token_hex(6)
            ring["keys"][ver] = b64(os.urandom(32))
            ring["active"] = ver
            write_private(cfg.directory / "keys.json", ring, replace=True)
        with engine.begin() as c:
            reencrypt(c, ring)
        print(
            "Registros migrados a la versión activa. Conserve las claves de los respaldos."
        )
    elif args.cmd == "password":
        if cfg.mode != "demo":
            ap.error("Use Supabase Auth en el despliegue.")
        pw = getpass.getpass("Nueva contraseña local (12 a 72 bytes): ").encode()
        if not 12 <= len(pw) <= 72:
            ap.error("Longitud de contraseña no válida")
        with engine.begin() as c:
            c.execute(
                update(s.users)
                .where(s.users.c.id == DEMO[args.alias])
                .values(password_hash=bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)))
            )
        print("Contraseña local configurada.")
    elif args.cmd == "provision":
        if cfg.mode != "supabase":
            ap.error("Solo para usuarios ya creados en Supabase Auth")
        with engine.begin() as c:
            if (
                args.trainer
                and not c.execute(
                    select(s.users.c.id).where(
                        s.users.c.id == str(args.trainer),
                        s.users.c.role == "entrenador",
                    )
                ).first()
            ):
                ap.error("Entrenador inexistente")
            c.execute(
                s.users.insert().values(
                    id=str(args.uuid),
                    role=args.role,
                    name=args.name,
                    trainer=str(args.trainer) if args.trainer else None,
                    source="operativo",
                )
            )
        print("Perfil vinculado a su UUID de Auth.")


if __name__ == "__main__":
    main()
