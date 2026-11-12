import hashlib, secrets, time
from collections import deque
from threading import Lock
import bcrypt, httpx
from fastapi import HTTPException
from sqlalchemy import select, delete
from . import store as s

COOKIE = "alzace_session"


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Limiter:
    """Bounded per-process login limiter; upstream limit required for multi-instance hosting."""

    def __init__(self):
        self.items = {}
        self.lock = Lock()

    def check(self, k):
        with self.lock:
            now = time.monotonic()
            if len(self.items) > 2048:
                self.items = {
                    i: q for i, q in self.items.items() if q and q[-1] > now - 60
                }
                if len(self.items) > 2048:
                    raise HTTPException(429, "Demasiados intentos.")
            q = self.items.setdefault(k, deque())
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= 15:
                raise HTTPException(429, "Espere un minuto antes de volver a intentar.")
            q.append(now)


def remote(cfg, verb, path, token=None, body=None):
    headers = {"apikey": cfg.anon_key}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        r = httpx.request(
            verb,
            cfg.auth_url + "/auth/v1/" + path,
            headers=headers,
            json=body,
            timeout=8,
        )
    except httpx.HTTPError:
        raise HTTPException(
            503, "No se pudo contactar con el proveedor de identidad."
        ) from None
    if r.status_code == 429:
        raise HTTPException(429, "Límite de autenticación alcanzado.")
    if r.status_code >= 500:
        raise HTTPException(503, "Proveedor de identidad no disponible.")
    if not r.is_success:
        raise HTTPException(401, "Sesión o credenciales no válidas.")
    return r.json() if r.content else {}


def open_session(c, cfg, user):
    token = secrets.token_urlsafe(40)
    c.execute(delete(s.sessions).where(s.sessions.c.expires <= int(time.time())))
    c.execute(
        s.sessions.insert().values(
            digest=digest(token), user_id=user["id"], expires=int(time.time()) + 3600
        )
    )
    return token


def lookup(c, cfg, token):
    if not token or len(token) > 12000:
        raise HTTPException(401, "Inicie sesión.")
    if cfg.mode == "supabase":
        ident = remote(cfg, "GET", "user", token)["id"]
        query = select(s.users).where(s.users.c.id == ident)
    else:
        query = (
            select(s.users)
            .join(s.sessions, s.sessions.c.user_id == s.users.c.id)
            .where(
                s.sessions.c.digest == digest(token),
                s.sessions.c.expires > int(time.time()),
            )
        )
    u = c.execute(query).mappings().first()
    if not u:
        raise HTTPException(401, "Sesión no válida o perfil sin habilitar.")
    return dict(u)


def login(c, cfg, email, password):
    if cfg.mode == "supabase":
        res = remote(
            cfg,
            "POST",
            "token?grant_type=password",
            body={"email": email, "password": password},
        )
        token = res["access_token"]
        user = lookup(c, cfg, token)
        return token, user, min(3600, int(res["expires_in"]))
    row = (
        c.execute(select(s.users).where(s.users.c.email == email.lower()))
        .mappings()
        .first()
    )
    # Same bcrypt cost for unknown/disabled accounts; no local plaintext passwords.
    candidate = row["password_hash"] if row and row["password_hash"] else DUMMY
    pw = password.encode()
    if (
        len(pw) > 72
        or not bcrypt.checkpw(pw, candidate)
        or not row
        or not row["password_hash"]
    ):
        raise HTTPException(401, "Sesión o credenciales no válidas.")
    return open_session(c, cfg, row), row, 3600


DUMMY = bcrypt.hashpw(secrets.token_bytes(24), bcrypt.gensalt(rounds=12))
