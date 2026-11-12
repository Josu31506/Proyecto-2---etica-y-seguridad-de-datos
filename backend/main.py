import csv
import io
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from sqlalchemy import select, update, delete
from . import store as s, auth
from .administration import admin_router
from .config import Settings
from .cli import DEMO
from .domain import person_view, periods, today, due
from .privacy import PERIODS
from .service import check_access, public_user, budget, describe, release
from .training import save_target, progress, operations
from .vault import decrypt, encrypt, read_ring


class Form(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Login(Form):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Demo(Form):
    alias: Literal["cliente", "otro", "entrenador", "administrador"]


class Consent(Form):
    allow: bool


class Metric(Form):
    day: date
    minutes: int = Field(ge=0, le=1440)
    steps: int = Field(ge=0, le=200000)
    sleep: int | None = Field(None, ge=0, le=1440)
    pulse: int | None = Field(None, ge=1, le=300)
    weight: float | None = Field(None, gt=0, le=600)
    fat: float | None = Field(None, ge=0, le=100)


class CsvImport(Form):
    csv: str = Field(min_length=1, max_length=65536)


class Publication(Form):
    source: Literal["programa", "estudio"]
    period: str = Field(pattern=r"^\d{4}-\d{2}$")


class Plan(Form):
    day: date
    label: str = Field(min_length=3, max_length=100)


class Goal(Form):
    months: Literal[1, 3] = 1
    minutes: int = Field(gt=0, le=130000)
    fat_drop: float = Field(gt=0, le=50)
    activity_weight: float = Field(ge=0, le=1)


class Attendance(Form):
    done: bool


def create_app(cfg=None):
    cfg = cfg or Settings.load()
    eng = s.connect(cfg)
    limiter = auth.Limiter()

    def quick():
        return cfg.mode == "demo" and os.environ.get("DEMO_SHORTCUTS", "1") == "1"

    @asynccontextmanager
    async def life(app):
        read_ring(cfg)
        with eng.connect() as c:
            budget(c)  # fail early if schema not initialized
        yield
        eng.dispose()

    app = FastAPI(
        title="Alzace · Seguimiento",
        version="1.0",
        lifespan=life,
        docs_url="/docs" if cfg.mode == "demo" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.mode == "demo" else None,
    )
    app.state.engine = eng

    @app.middleware("http")
    async def guard(req, call_next):
        if cfg.mode == "demo" and req.url.hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            return JSONResponse({"detail": "La demo es local."}, status_code=403)
        if req.method not in ("GET", "HEAD", "OPTIONS"):
            origin = req.headers.get("origin")
            if req.headers.get("x-alzace-request") != "web" or (
                origin and origin != cfg.origin
            ):
                return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
        res = await call_next(req)
        res.headers["cache-control"] = "private, no-store"
        res.headers["x-content-type-options"] = "nosniff"
        return res

    def actor(req: Request):
        with eng.connect() as c:
            return auth.lookup(c, cfg, req.cookies.get(auth.COOKIE))

    def require(u, *roles):
        if u["role"] not in roles:
            raise HTTPException(403, "Acción no permitida para este rol.")

    def member(c, u, owner):
        try:
            return check_access(c, u, owner)
        except HTTPException:
            s.record(c, u["id"], "perfil.acceso", "denegado")
            c.commit()
            raise

    def session_response(res, token, age):
        res.set_cookie(
            auth.COOKIE,
            token,
            max_age=age,
            httponly=True,
            secure=cfg.mode == "supabase",
            samesite="strict",
            path="/api",
        )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "demo": quick(), "mode": cfg.mode}

    @app.post("/api/auth/demo")
    def demo(form: Demo, res: Response, req: Request):
        if not quick():
            raise HTTPException(404)
        limiter.check(req.client.host if req.client else "-")
        with eng.begin() as c:
            u = (
                c.execute(
                    select(s.users).where(
                        s.users.c.id == DEMO[form.alias],
                        s.users.c.source == "sintetico",
                    )
                )
                .mappings()
                .one()
            )
            token = auth.open_session(c, cfg, u)
            s.record(c, u["id"], "sesion.demo")
        session_response(res, token, 3600)
        return public_user(u)

    @app.post("/api/auth/login")
    def signin(form: Login, req: Request, res: Response):
        limiter.check(req.client.host if req.client else "-")
        with eng.begin() as c:
            token, u, age = auth.login(c, cfg, form.email.strip(), form.password)
            s.record(c, u["id"], "sesion.iniciar")
        session_response(res, token, age)
        return public_user(u)

    @app.post("/api/auth/logout")
    def signout(req: Request, res: Response):
        token = req.cookies.get(auth.COOKIE)
        if token and cfg.mode == "supabase":
            auth.remote(cfg, "POST", "logout?scope=local", token)
        elif token:
            with eng.begin() as c:
                c.execute(
                    delete(s.sessions).where(s.sessions.c.digest == auth.digest(token))
                )
        res.delete_cookie(
            auth.COOKIE,
            path="/api",
            httponly=True,
            samesite="strict",
            secure=cfg.mode == "supabase",
        )
        return {"ok": True}

    @app.get("/api/me")
    def me(u=Depends(actor)):
        return public_user(u)

    @app.put("/api/me/consent")
    def consent(form: Consent, u=Depends(actor)):
        require(u, "cliente")
        with eng.begin() as c:
            at = s.now()
            c.execute(
                update(s.users)
                .where(s.users.c.id == u["id"])
                .values(
                    analytics=form.allow, consent_at=at, consent_version="analitica-v1"
                )
            )
            s.record(
                c, u["id"], "analitica.aceptar" if form.allow else "analitica.retirar"
            )
        return public_user({**u, "analytics": form.allow, "consent_at": at})

    @app.get("/api/clients")
    def clients(u=Depends(actor)):
        require(u, "entrenador", "cliente")
        with eng.connect() as c:
            stmt = select(s.users.c.id, s.users.c.name).where(
                s.users.c.role == "cliente"
            )
            stmt = (
                stmt.where(s.users.c.id == u["id"])
                if u["role"] == "cliente"
                else stmt.where(s.users.c.trainer == u["id"])
            )
            return [
                dict(r) for r in c.execute(stmt.order_by(s.users.c.name)).mappings()
            ]

    @app.get("/api/clients/{owner}")
    def client(owner: str, u=Depends(actor)):
        with eng.begin() as c:
            p = member(c, u, owner)
            ring = read_ring(cfg)
            view = person_view(c, ring, owner)
            view["goal"] = progress(c, ring, owner, view["history"])
            s.record(c, u["id"], "metricas.consultar")
            return {"id": owner, "name": p["name"], "source": p["source"], **view}

    def save_measurements(owner, forms, user, event):
        if any(form.day > today() for form in forms):
            raise HTTPException(422, "La medición no puede ser futura.")
        with eng.begin() as c:
            member(c, user, owner)
            # Serialize same-client edits (including the first entry on a given day).
            c.execute(
                update(s.users).where(s.users.c.id == owner).values(name=s.users.c.name)
            )
            ring = read_ring(cfg)
            for form in forms:
                day = form.day.isoformat()
                row = (
                    c.execute(
                        select(s.metrics).where(
                            s.metrics.c.owner == owner, s.metrics.c.day == day
                        )
                    )
                    .mappings()
                    .first()
                )
                values = (
                    decrypt(ring, s.metrics.name, row)
                    if row
                    else form.model_dump(exclude={"day"})
                )
                values.update(form.model_dump(exclude={"day"}, exclude_unset=True))
                payload = encrypt(ring, s.metrics.name, owner, day, values)
                s.upsert(
                    c,
                    s.metrics,
                    dict(owner=owner, day=day, **payload),
                    ["owner", "day"],
                    ["version", "blob"],
                )
            s.record(c, user["id"], event)

    @app.post("/api/clients/{owner}/metrics", status_code=201)
    def measure(owner: str, form: Metric, u=Depends(actor)):
        save_measurements(owner, [form], u, "metricas.registrar")
        return {"ok": True}

    @app.post("/api/clients/{owner}/metrics/import", status_code=201)
    def import_metrics(owner: str, form: CsvImport, u=Depends(actor)):
        reader = csv.DictReader(io.StringIO(form.csv.lstrip("\ufeff")), strict=True)
        forms = []
        days = set()
        try:
            names = reader.fieldnames or []
            if (
                len(names) != len(set(names))
                or not {"day", "minutes", "steps"}.issubset(names)
                or set(names) - set(Metric.model_fields)
            ):
                raise HTTPException(
                    422,
                    "Revisa los encabezados del CSV. Usa day,minutes,steps y campos opcionales conocidos.",
                )
            for i, row in enumerate(reader, 2):
                if None in row or i > 367:
                    raise HTTPException(
                        422,
                        "Se admiten hasta 366 días, con una columna por encabezado.",
                    )
                value = Metric.model_validate(
                    {k: v for k, v in row.items() if v not in ("", None)}
                )
                if value.day in days:
                    raise HTTPException(422, "Hay días repetidos dentro del archivo.")
                days.add(value.day)
                forms.append(value)
        except (ValidationError, csv.Error):
            raise HTTPException(422, f"Revisa los datos de la línea {reader.line_num}.")
        if not forms:
            raise HTTPException(422, "El archivo debe contener al menos un día.")
        save_measurements(owner, forms, u, "metricas.importar")
        return {"days": len(forms)}

    @app.put("/api/clients/{owner}/goal")
    def goal(owner: str, form: Goal, u=Depends(actor)):
        require(u, "entrenador")
        with eng.begin() as c:
            member(c, u, owner)
            save_target(
                c,
                read_ring(cfg),
                owner,
                today().replace(day=1).isoformat(),
                form.model_dump(),
            )
            s.record(c, u["id"], "meta.asignar")
        return {"ok": True}

    @app.post("/api/clients/{owner}/plans", status_code=201)
    def plan(owner: str, form: Plan, u=Depends(actor)):
        require(u, "entrenador")
        with eng.begin() as c:
            member(c, u, owner)
            day = form.day.isoformat()
            key = s.uid()
            c.execute(
                s.plans.insert().values(
                    id=key,
                    owner=owner,
                    label=form.label.strip(),
                    day=day,
                    alert_at=due(day),
                )
            )
            s.record(c, u["id"], "plan.crear")
        return {"id": key}

    @app.put("/api/plans/{pid}/attendance")
    def attend(pid: str, form: Attendance, u=Depends(actor)):
        require(u, "cliente")
        with eng.begin() as c:
            updated = c.execute(
                update(s.plans)
                .where(
                    s.plans.c.id == pid,
                    s.plans.c.owner == u["id"],
                    s.plans.c.day <= today().isoformat(),
                )
                .values(done=form.done)
            )
            if not updated.rowcount:
                raise HTTPException(403, "Sesión no disponible.")
            s.record(c, u["id"], "sesion.cumplimiento")
        return {"ok": True}

    @app.post("/api/plans/{pid}/respond")
    def respond(pid: str, u=Depends(actor)):
        require(u, "entrenador")
        with eng.begin() as c:
            p = c.execute(select(s.plans).where(s.plans.c.id == pid)).mappings().first()
            if not p:
                raise HTTPException(403)
            member(c, u, p["owner"])
            if p["done"] or p["alert_at"] > s.now():
                raise HTTPException(409, "No hay alerta activa.")
            c.execute(
                update(s.plans)
                .where(s.plans.c.id == pid, s.plans.c.attended_at.is_(None))
                .values(attended_at=s.now())
            )
            s.record(c, u["id"], "alerta.seguimiento")
        return {"ok": True}

    @app.get("/api/analytics")
    def analytics(u=Depends(actor)):
        require(u, "entrenador", "administrador")
        with eng.connect() as c:
            return {
                "budget": budget(c),
                "periods": {"programa": periods(), "estudio": PERIODS},
                "releases": [
                    describe(r)
                    for r in c.execute(
                        select(s.releases).order_by(s.releases.c.created.desc())
                    ).mappings()
                ],
            }

    @app.post("/api/analytics/publish")
    def publish(form: Publication, u=Depends(actor)):
        require(u, "administrador")
        with eng.begin() as c:
            return release(c, read_ring(cfg), u, form.source, form.period)

    @app.get("/api/admin/audit")
    def audit(u=Depends(actor)):
        require(u, "administrador")
        with eng.connect() as c:
            return {
                "events": [
                    dict(r)
                    for r in c.execute(
                        select(s.audit).order_by(s.audit.c.id.desc()).limit(40)
                    ).mappings()
                ],
                "retention": operations(c),
            }

    @app.get("/api/trainer/alerts")
    def alerts(u=Depends(actor)):
        require(u, "entrenador")
        with eng.connect() as c:
            q = (
                select(s.plans, s.users.c.name)
                .join(s.users, s.users.c.id == s.plans.c.owner)
                .where(s.users.c.trainer == u["id"], s.plans.c.alert_at <= s.now())
            )
            allrows = c.execute(q).mappings().all()
            month = today().strftime("%Y-%m")
            eligible = [
                r
                for r in allrows
                if r["alert_at"].startswith(month) and r["attended_at"]
            ]
            hours = [
                (
                    datetime.fromisoformat(r["attended_at"])
                    - datetime.fromisoformat(r["alert_at"])
                ).total_seconds()
                / 3600
                for r in eligible
            ]
            return {
                "hours": round(sum(hours) / len(hours), 1) if hours else None,
                "period": month,
                "pending": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "at": r["alert_at"],
                        "label": r["label"],
                    }
                    for r in allrows
                    if not r["done"] and not r["attended_at"]
                ],
            }

    app.include_router(admin_router(eng, actor))
    return app


app = create_app()
