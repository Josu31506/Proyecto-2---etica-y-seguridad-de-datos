from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from . import store as s

incidents = s.Table(
    "incident_cases",
    s.meta,
    s.C("id", s.S(40), primary_key=True),
    s.C("category", s.S(20), nullable=False),
    s.C("created", s.S(32), nullable=False),
    s.C("resolved", s.S(32)),
)


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trainer: str = Field(min_length=1, max_length=80)


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["acceso", "divulgacion", "perdida"]


def admin_router(engine, actor):
    def admin(user=Depends(actor)):
        if user["role"] != "administrador":
            raise HTTPException(403, "Acción reservada a administración.")
        return user

    routes = APIRouter(prefix="/api/admin", dependencies=[Depends(admin)])

    @routes.get("/operations")
    def overview():
        with engine.connect() as c:
            fields = (s.users.c.id, s.users.c.name, s.users.c.role, s.users.c.trainer)
            accounts = [
                dict(r)
                for r in c.execute(select(*fields).order_by(s.users.c.name)).mappings()
            ]
            cases = [
                dict(r)
                for r in c.execute(
                    select(incidents).order_by(incidents.c.created.desc()).limit(60)
                ).mappings()
            ]
            backups = [
                dict(r)
                for r in c.execute(
                    select(s.audit.c.at, s.audit.c.action)
                    .where(
                        s.audit.c.action.in_(["respaldo.crear", "respaldo.verificar"])
                    )
                    .order_by(s.audit.c.id.desc())
                    .limit(10)
                ).mappings()
            ]
        return {"accounts": accounts, "incidents": cases, "backups": backups}

    @routes.put("/assignments/{owner}")
    def assign(owner: str, data: Assignment, admin_user=Depends(admin)):
        with engine.begin() as c:
            trainer = c.execute(
                select(s.users.c.id).where(
                    s.users.c.id == data.trainer, s.users.c.role == "entrenador"
                )
            ).first()
            if not trainer:
                raise HTTPException(422, "Elige un entrenador habilitado.")
            result = c.execute(
                update(s.users)
                .where(s.users.c.id == owner, s.users.c.role == "cliente")
                .values(trainer=data.trainer)
            )
            if not result.rowcount:
                raise HTTPException(404, "Cliente no disponible.")
            s.record(c, admin_user["id"], "equipo.asignar")
        return {"ok": True}

    @routes.post("/incidents", status_code=201)
    def report(data: Incident, admin_user=Depends(admin)):
        case = s.uid()
        with engine.begin() as c:
            c.execute(
                incidents.insert().values(
                    id=case, category=data.category, created=s.now()
                )
            )
            s.record(c, admin_user["id"], "incidente.abrir")
        return {"id": case}

    @routes.put("/incidents/{case}/resolve")
    def resolve(case: str, admin_user=Depends(admin)):
        with engine.begin() as c:
            result = c.execute(
                update(incidents)
                .where(incidents.c.id == case, incidents.c.resolved.is_(None))
                .values(resolved=s.now())
            )
            if not result.rowcount:
                raise HTTPException(409, "El incidente no está abierto.")
            s.record(c, admin_user["id"], "incidente.cerrar")
        return {"ok": True}

    return routes
