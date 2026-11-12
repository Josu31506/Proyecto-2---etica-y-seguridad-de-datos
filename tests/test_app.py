from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from cryptography.exceptions import InvalidTag
from backend.main import create_app
from backend.config import Settings
from backend import store as s
from backend.cli import seed, DEMO, reencrypt, import_study
from backend.domain import today, periods
from backend.vault import read_ring, decrypt, b64, write_private
from backend.privacy import contributions, private_mean
from backend.backup import snapshot, verify
from backend.dataio import read_activity

H = {"X-Alzace-Request": "web", "Origin": "http://127.0.0.1:3000"}


@pytest.fixture
def site(tmp_path):
    d = tmp_path / "state"
    cfg = Settings(
        d, "sqlite:///" + (d / "test.sqlite3").as_posix(), "demo", H["Origin"]
    )
    app = create_app(cfg)
    eng = app.state.engine
    s.initialize(eng)
    ring = read_ring(cfg, create=True)
    with eng.begin() as c:
        seed(c, ring)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=H) as cl:
        yield cl, eng, cfg


def login(cl, role):
    resp = cl.post("/api/auth/demo", json={"alias": role})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_acl_csrf_sessions(site):
    cl, eng, _ = site
    assert cl.get("/api/clients").status_code == 401
    assert (
        cl.post(
            "/api/auth/demo",
            json={"alias": "administrador"},
            headers={"origin": "https://otra.invalid"},
        ).status_code
        == 403
    )
    login(cl, "cliente")
    assert cl.get("/api/clients/" + DEMO["otro"]).status_code == 403
    assert cl.get("/api/admin/audit").status_code == 403
    login(cl, "entrenador")
    assert cl.get("/api/clients/" + DEMO["otro"]).status_code == 403
    assert cl.get("/api/clients/" + DEMO["cliente"]).status_code == 200
    login(cl, "administrador")
    assert cl.get("/api/clients/" + DEMO["cliente"]).status_code == 403
    assert any(
        e["outcome"] == "denegado" for e in cl.get("/api/admin/audit").json()["events"]
    )
    token = cl.cookies.get("alzace_session")
    cl.post("/api/auth/logout")
    cl.cookies.set("alzace_session", token, path="/api")
    assert cl.get("/api/me").status_code == 401


def test_measurements_aad_rotation_backup(site, tmp_path):
    cl, eng, cfg = site
    owner = login(cl, "cliente")["id"]
    day = today().isoformat()
    previous_fat = cl.get("/api/clients/" + owner).json()["history"][0]["fat"]
    r = cl.post(
        "/api/clients/" + owner + "/metrics",
        json={"day": day, "minutes": 59, "steps": 12345},
    )
    assert r.status_code == 201
    assert cl.get("/api/clients/" + owner).json()["history"][0]["fat"] == previous_fat
    with eng.begin() as c:
        original = dict(
            c.execute(
                select(s.metrics).where(
                    s.metrics.c.owner == owner, s.metrics.c.day == day
                )
            )
            .mappings()
            .one()
        )
        ring = read_ring(cfg)
        assert b"12345" not in original["blob"]
        for field, change in (
            ("owner", "otro"),
            ("blob", original["blob"][:-1] + bytes([original["blob"][-1] ^ 1])),
        ):
            with pytest.raises(InvalidTag):
                decrypt(ring, s.metrics.name, {**original, field: change})
    copy = snapshot(cfg, tmp_path / "backup")
    with eng.begin() as c:
        ring["active"] = "v2"
        ring["keys"]["v2"] = b64(os.urandom(32))
        write_private(cfg.directory / "keys.json", ring, replace=True)
        reencrypt(c, ring)
        assert {x for x in c.execute(select(s.metrics.c.version)).scalars()} == {"v2"}
    assert cl.get("/api/clients/" + owner).json()["history"][0]["steps"] == 12345
    assert verify(cfg, copy) > 0
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(update(s.audit).values(outcome="alterado"))


def test_privacy_math():
    a = contributions(
        [("a", "d1", 25), ("a", "d2", 75), ("b", "d1", 300), ("a", "d1", 25)]
    )
    assert a == [50.0, 120.0]
    with pytest.raises(ValueError):
        contributions([("a", "d", 5), ("a", "d", 6)])
    assert private_mean([60] * 30, 1, rng=np.random.RandomState(32)) == private_mean(
        [60] * 30, 1, rng=np.random.RandomState(32)
    )


def test_concurrent_release_cache_and_budget(site):
    cl, eng, cfg = site
    login(cl, "administrador")

    def pub(m):
        return cl.post(
            "/api/analytics/publish", json={"source": "programa", "period": m}
        )

    months = periods()
    with ThreadPoolExecutor(4) as ex:
        answers = list(ex.map(pub, [months[0]] * 4))
    assert all(x.status_code == 200 for x in answers)
    vals = [x.json() for x in answers]
    assert sum(not x["cached"] for x in vals) == 1 and all(
        x["release"] == vals[0]["release"] for x in vals
    )
    assert pub(months[1]).status_code == 200 and pub(months[2]).status_code == 409
    assert pub(months[0]).json()["cached"]
    with TestClient(
        create_app(cfg), base_url="http://127.0.0.1:8000", headers=H
    ) as again:
        login(again, "administrador")
        r = again.get("/api/analytics").json()
        assert r["budget"] == {"spent": 2.0, "total": 2.0} and len(r["releases"]) == 2
    login(cl, "entrenador")
    assert pub(months[0]).status_code == 403


def test_consent_selects_contributors(site, monkeypatch):
    cl, _, _ = site
    counts = []

    def spy(v, e):
        counts.append(len(v))
        return None

    monkeypatch.setattr("backend.service.private_mean", spy)
    login(cl, "cliente")
    cl.put("/api/me/consent", json={"allow": True})

    def pub(m):
        login(cl, "administrador")
        return cl.post(
            "/api/analytics/publish", json={"source": "programa", "period": m}
        ).json()

    months = periods()
    assert pub(months[0])["release"]["minutes"] is None
    login(cl, "cliente")
    assert cl.put("/api/me/consent", json={"allow": False}).json()["analytics"] is False
    assert pub(months[0])["cached"] and not pub(months[1])["cached"]
    assert counts == [35, 34]  # synthetic seed grants 34, REAL accounts start opted out


def test_plan_goal_and_deviation(site):
    cl, _, _ = site
    login(cl, "entrenador")
    owner = DEMO["cliente"]
    plan = cl.post(
        "/api/clients/" + owner + "/plans",
        json={
            "label": "Circuito personal",
            "day": (today() - timedelta(days=4)).isoformat(),
        },
    ).json()["id"]
    assert (
        cl.put(
            "/api/clients/" + owner + "/goal",
            json={"months": 3, "minutes": 2200, "activity_weight": 1, "fat_drop": 1},
        ).status_code
        == 200
    )
    assert any(x["id"] == plan for x in cl.get("/api/trainer/alerts").json()["pending"])
    assert cl.post("/api/plans/" + plan + "/respond").status_code == 200
    assert all(x["id"] != plan for x in cl.get("/api/trainer/alerts").json()["pending"])
    login(cl, "otro")
    assert (
        cl.put("/api/plans/" + plan + "/attendance", json={"done": True}).status_code
        == 403
    )
    login(cl, "cliente")
    assert (
        cl.put("/api/plans/" + plan + "/attendance", json={"done": True}).status_code
        == 200
    )


def test_import_conflicts_and_minimisation(site, tmp_path):
    cl, eng, cfg = site
    login(cl, "administrador")
    assert (
        cl.post(
            "/api/analytics/publish", json={"source": "estudio", "period": "2016-04"}
        ).status_code
        == 409
    )
    assert cl.get("/api/analytics").json()["budget"]["spent"] == 0
    file = tmp_path / "daily.csv"
    head = "Id,ActivityDate,VeryActiveMinutes,FairlyActiveMinutes,TotalSteps\n"
    file.write_text(head + "99999999,4/12/2016,15,20,5000\n")
    with eng.begin() as c:
        import_study(c, read_ring(cfg), [file])
        import_study(c, read_ring(cfg), [file])
        r = c.execute(select(s.research)).mappings().one()
        assert r["owner"] != "99999999" and b"5000" not in r["blob"]
    file.write_text(
        head + "99999999,4/12/2016,15,20,5000\n99999999,4/12/2016,16,20,5000\n"
    )
    with pytest.raises(ValueError):
        read_activity([file])


def test_csv_upload_atomic_and_scoped(site):
    cl, _, _ = site
    owner = login(cl, "cliente")["id"]
    path = f"/api/clients/{owner}/metrics/import"
    day = today().isoformat()
    before = cl.get(f"/api/clients/{owner}").json()["history"][0]
    assert (
        cl.post(
            path, json={"csv": f"day,minutes,steps\n{day},42,7654\n1999-01-01,-1,2"}
        ).status_code
        == 422
    )
    assert cl.get(f"/api/clients/{owner}").json()["history"][0] == before
    assert cl.post(path, json={"csv": f"day,minutes,steps\n{day},42,7654"}).json() == {
        "days": 1
    }
    after = cl.get(f"/api/clients/{owner}").json()["history"][0]
    assert (after["steps"], after["fat"]) == (7654, before["fat"])
    assert (
        cl.post(
            "/api/clients/" + DEMO["otro"] + "/metrics/import",
            json={"csv": f"day,minutes,steps\n{day},41,3"},
        ).status_code
        == 403
    )
