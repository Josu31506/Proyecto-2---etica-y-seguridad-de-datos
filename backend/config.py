"""Secrets stay server-side. No automatic fallback from production to demo."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    directory: Path
    database: str
    mode: str
    origin: str
    auth_url: str = ""
    anon_key: str = ""

    @classmethod
    def load(cls):
        mode = os.environ.get("ALZACE_MODE", "demo")
        if os.environ.get("RENDER", "").lower() == "true" and mode != "supabase":
            raise RuntimeError(
                "Configure el modo supabase para el despliegue en Render"
            )
        if mode not in ("demo", "supabase"):
            raise RuntimeError("ALZACE_MODE debe ser demo o supabase")
        directory = Path(os.environ.get("ALZACE_STATE", ROOT / ".local")).resolve()
        db = os.environ.get("DATABASE_URL", "")
        origin = os.environ.get("FRONTEND_ORIGIN", "http://127.0.0.1:3000").rstrip("/")
        auth = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        if mode == "supabase":
            if not (
                urlsplit(origin).scheme == "https"
                and urlsplit(auth).scheme == "https"
                and key
                and db
            ):
                raise RuntimeError("Falta configurar HTTPS, Supabase Auth o PostgreSQL")
            url = make_url(db)
            if (
                url.drivername != "postgresql+psycopg"
                or url.query.get("sslmode") != "verify-full"
            ):
                raise RuntimeError(
                    "Use postgresql+psycopg con sslmode=verify-full y CA de confianza"
                )
            if not os.environ.get("ALZACE_KEYRING"):
                raise RuntimeError(
                    "Proporcione ALZACE_KEYRING mediante el almacén de secretos"
                )
        elif urlsplit(origin).hostname not in ("localhost", "127.0.0.1", "::1") or (
            db and not db.startswith("sqlite:")
        ):
            raise RuntimeError("La demo admite exclusivamente origen local y SQLite")
        return cls(
            directory,
            db or "sqlite:///" + (directory / "demo.sqlite3").as_posix(),
            mode,
            origin,
            auth,
            key,
        )
