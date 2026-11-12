"use client";
import { FormEvent, useEffect, useState } from "react";
import {
  api,
  User,
  Profile,
  Metric,
  dateLabel,
  errorText,
  localDay,
} from "./lib";
import { Icon, Notice, Panel, Track } from "./ui";
import { Upload } from "./upload";
function Trend({ data }: { data: Metric[] }) {
  const series = data.slice(0, 14).reverse(),
    max = Math.max(10, ...series.map((x) => x.minutes));
  if (!series.length)
    return <p className="empty">Todavía no hay mediciones.</p>;
  return (
    <>
      <div
        className="chart"
        role="img"
        aria-label={
          "Minutos activos en las últimas " +
          series.length +
          " mediciones. Consulta los valores en el historial."
        }
      >
        {series.map((r, i) => (
          <div
            key={r.day}
            className="barcol"
            title={dateLabel(r.day) + ": " + r.minutes + " min"}
          >
            <svg
              height={Math.max(2, (100 * r.minutes) / max) + "%"}
              width="84%"
              viewBox="0 0 12 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <rect
                x="0"
                width="12"
                height="100"
                rx="1"
                fill={i === series.length - 1 ? "#184d40" : "#86a898"}
              />
            </svg>
          </div>
        ))}
      </div>
      <div className="chart-scale">
        <span>{dateLabel(series[0].day)}</span>
        <span>Minutos activos por día</span>
        <span>{dateLabel(series.at(-1)!.day)}</span>
      </div>
    </>
  );
}
export function Training({ user }: { user: User }) {
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]),
    [owner, setOwner] = useState(""),
    [data, setData] = useState<Profile | null>(null),
    [msg, setMsg] = useState(""),
    [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0),
    [tab, setTab] = useState("resumen"),
    [form, setForm] = useState("");
  useEffect(() => {
    let ok = true;
    api<{ id: string; name: string }[]>("clients")
      .then((xs) => {
        if (ok) {
          setClients(xs);
          setOwner(xs[0]?.id || "");
          if (!xs.length) setMsg("Todavía no hay clientes asignados.");
        }
      })
      .catch((e) => ok && setMsg(errorText(e)));
    return () => {
      ok = false;
    };
  }, [user.id]);
  useEffect(() => {
    if (!owner) return;
    let ok = true;
    api<Profile>("clients/" + owner)
      .then((x) => {
        if (ok) setData(x);
      })
      .catch((e) => ok && setMsg(errorText(e)));
    return () => {
      ok = false;
    };
  }, [owner, reload]);
  async function run(
    path: string,
    method: string,
    body: unknown,
    message: string,
  ) {
    setBusy(true);
    setMsg("");
    try {
      await api(path, method, body);
      setReload((n) => n + 1);
      setForm("");
      setMsg(message);
    } catch (e) {
      setMsg(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (form === "medicion") {
      const body: Record<string, unknown> = {
        day: f.get("day"),
        minutes: Number(f.get("minutes")),
        steps: Number(f.get("steps")),
      };
      for (const k of ["fat", "weight", "pulse", "sleep"])
        if (f.get(k)) body[k] = Number(f.get(k));
      void run(
        "clients/" + owner + "/metrics",
        "POST",
        body,
        "Medición guardada.",
      );
    }
    if (form === "plan")
      void run(
        "clients/" + owner + "/plans",
        "POST",
        { label: f.get("label"), day: f.get("day") },
        "Sesión asignada.",
      );
    if (form === "meta")
      void run(
        "clients/" + owner + "/goal",
        "PUT",
        {
          minutes: Number(f.get("minutes")),
          months: Number(f.get("months")),
          activity_weight: Number(f.get("weight")) / 100,
          fat_drop: Number(f.get("fat_drop")),
        },
        "Meta actualizada.",
      );
  }
  const mine = user.role === "cliente",
    current = data?.id === owner ? data : null,
    last = current?.history[0],
    g = current?.goal;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ENTRENAMIENTO / SEGUIMIENTO</div>
          <h1>{mine ? "Mi actividad" : "Mis clientes"}</h1>
          <p className="sub">
            {mine
              ? "Tu historial, tu plan y el avance de tus metas."
              : "Consulta el progreso y organiza el plan de tus clientes asignados."}
          </p>
        </div>
        {!mine && (
          <label>
            Cliente asignado
            <select
              aria-label="Cliente asignado"
              value={owner}
              onChange={(e) => {
                setOwner(e.target.value);
                setData(null);
                setMsg("");
                setForm("");
              }}
            >
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <Notice msg={msg} />
      {current ? (
        <>
          <div className="hero">
            <div className="hero-text">
              <div className="eyebrow">
                FICHA DE ACTIVIDAD{" "}
                {current.source === "demo_vinculado"
                  ? " / SIMULACIÓN FITBIT + GYM"
                  : current.source === "sintetico"
                    ? " / DEMOSTRACIÓN"
                    : ""}
              </div>
              <h2>{current.name}</h2>
              <p>
                {g
                  ? dateLabel(g.start) + " — " + dateLabel(g.end)
                  : "Sin meta asignada"}{" "}
                · Seguimiento individual
              </p>
            </div>
            <Track />
            <div className="hero-kpi">
              <strong>
                {g?.percent ?? "—"}
                <small>%</small>
              </strong>
              <span>Avance del periodo</span>
            </div>
          </div>
          <div className="metrics">
            {[
              ["pulse", "Minutos activos", last?.minutes, "min"],
              [
                "run",
                "Pasos registrados",
                last?.steps?.toLocaleString("es-PE"),
                "pasos",
              ],
              [
                "target",
                "Adherencia semanal",
                current.weekly_total
                  ? Math.round(
                      (100 * current.weekly_done) / current.weekly_total,
                    )
                  : null,
                "%",
              ],
            ].map(([ic, label, num, unit]) => (
              <div className="metric" key={String(label)}>
                <span className="metric-label">
                  <Icon name={String(ic)} />
                  {label}
                </span>
                <strong>
                  {num ?? "—"} <small>{unit}</small>
                </strong>
                <em>
                  {ic === "target"
                    ? current.weekly_done +
                      " de " +
                      current.weekly_total +
                      " sesiones"
                    : last
                      ? "Último registro · " + dateLabel(last.day)
                      : "Sin datos"}
                </em>
              </div>
            ))}
          </div>
          <div className="toolbar">
            <div className="tabs">
              {["resumen", "historial", "plan"].map((k) => (
                <button
                  key={k}
                  aria-pressed={tab === k}
                  onClick={() => {
                    setTab(k);
                    setForm("");
                  }}
                >
                  {k[0].toUpperCase() + k.slice(1)}
                </button>
              ))}
            </div>
            <button
              className="secondary"
              onClick={() => setForm(form === "medicion" ? "" : "medicion")}
            >
              + Registrar medición
            </button>
          </div>
          {tab === "historial" && (
            <Upload
              key={owner}
              owner={owner}
              name={current.name}
              saved={(message) => {
                setMsg(message);
                setReload((n) => n + 1);
              }}
            />
          )}
          {form && (
            <Panel
              over="EDICIÓN"
              title={
                {
                  medicion: "Registrar medición",
                  plan: "Asignar una sesión",
                  meta: "Definir meta del periodo",
                }[form] || ""
              }
            >
              <form onSubmit={submit}>
                <div className="formgrid">
                  {form === "medicion" && (
                    <>
                      <label>
                        Fecha
                        <input
                          type="date"
                          required
                          max={localDay()}
                          defaultValue={localDay()}
                          name="day"
                        />
                      </label>
                      <label>
                        Minutos activos
                        <input
                          type="number"
                          name="minutes"
                          required
                          min="0"
                          max="1440"
                        />
                      </label>
                      <label>
                        Pasos
                        <input
                          type="number"
                          name="steps"
                          required
                          min="0"
                          max="200000"
                        />
                      </label>
                      {[
                        ["sleep", "Sueño (min)", 0, 1440, 1],
                        ["pulse", "Pulso (lpm)", 1, 300, 1],
                        ["weight", "Peso (kg)", 0.1, 600, 0.1],
                        ["fat", "Grasa corporal (%)", 0, 100, 0.1],
                      ].map(([k, t, min, max, step]) => (
                        <label key={k}>
                          {t} · opcional
                          <input
                            type="number"
                            name={String(k)}
                            min={min}
                            max={max}
                            step={step}
                          />
                        </label>
                      ))}
                    </>
                  )}
                  {form === "plan" && (
                    <>
                      <label>
                        Fecha de sesión
                        <input
                          required
                          type="date"
                          name="day"
                          defaultValue={localDay()}
                        />
                      </label>
                      <label>
                        Actividad
                        <input
                          name="label"
                          required
                          minLength={3}
                          maxLength={100}
                          placeholder="Ej. Caminata al aire libre"
                        />
                      </label>
                    </>
                  )}
                  {form === "meta" && (
                    <>
                      <label>
                        Periodo
                        <select name="months" defaultValue={g?.months || 1}>
                          <option value="1">Un mes</option>
                          <option value="3">Tres meses</option>
                        </select>
                      </label>
                      <label>
                        Meta de minutos
                        <input
                          required
                          type="number"
                          name="minutes"
                          min={1}
                          max={130000}
                          defaultValue={g?.minutes || 750}
                        />
                      </label>
                      <label>
                        Peso de la actividad (%)
                        <input
                          required
                          type="number"
                          name="weight"
                          min={0}
                          max={100}
                          defaultValue={(g?.activity_weight ?? 0.6) * 100}
                        />
                      </label>
                      <label>
                        Cambio de grasa (puntos porcentuales)
                        <input
                          required
                          type="number"
                          name="fat_drop"
                          min={0.1}
                          max={50}
                          step="0.1"
                          defaultValue={g?.fat_drop || 1}
                        />
                      </label>
                    </>
                  )}
                </div>
                <div className="actions">
                  <button className="primary" disabled={busy}>
                    Guardar
                  </button>
                  <button
                    type="button"
                    className="textbtn"
                    onClick={() => setForm("")}
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            </Panel>
          )}
          {tab === "resumen" && (
            <div className="split">
              <Panel over="ÚLTIMOS REGISTROS" title="Ritmo de actividad">
                <Trend data={current.history} />
              </Panel>
              <Panel over="OBJETIVO PERSONAL" title="Meta del periodo">
                <p className="big">
                  {g?.observed_minutes ?? "—"}{" "}
                  <small>/ {g?.minutes ?? "—"} min</small>
                </p>
                <progress
                  max={g?.minutes || 1}
                  value={g?.observed_minutes || 0}
                />
                <p className="sub">
                  {g
                    ? "Actividad: " +
                      Math.round(g.activity_weight * 100) +
                      "% del avance. El resto corresponde al cambio corporal entre mediciones."
                    : "El entrenador aún no asignó una meta."}
                </p>
                {g?.percent == null && (
                  <p className="empty">
                    Datos insuficientes para calcular el avance total.
                  </p>
                )}
                {!mine && (
                  <button onClick={() => setForm("meta")} className="textbtn">
                    Editar meta →
                  </button>
                )}
              </Panel>
            </div>
          )}
          {tab === "historial" && (
            <Panel title="Historial de mediciones">
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      {[
                        "Fecha",
                        "Minutos",
                        "Pasos",
                        "Sueño (min)",
                        "Pulso",
                        "Peso (kg)",
                        "Grasa (%)",
                      ].map((t) => (
                        <th key={t}>{t}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {current.history.map((r) => (
                      <tr key={r.day}>
                        {[
                          r.day,
                          r.minutes,
                          r.steps,
                          r.sleep,
                          r.pulse,
                          r.weight,
                          r.fat,
                        ].map((v, i) => (
                          <td key={i}>{v ?? "—"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
          {tab === "plan" && (
            <Panel over="PLAN ASIGNADO" title="Sesiones de entrenamiento">
              {!mine && (
                <button className="secondary" onClick={() => setForm("plan")}>
                  + Asignar sesión
                </button>
              )}
              {!current.plans.length && (
                <p className="empty">No hay sesiones programadas.</p>
              )}
              {current.plans.map((p) => (
                <div className="row" key={p.id}>
                  <div>
                    <b>{p.label}</b>
                    <small>
                      {dateLabel(p.day)} ·{" "}
                      {p.done
                        ? "Completada"
                        : p.alert
                          ? "Sin cumplimiento declarado"
                          : "Programada"}
                    </small>
                  </div>
                  {mine && p.day <= localDay() && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        run(
                          "plans/" + p.id + "/attendance",
                          "PUT",
                          { done: !p.done },
                          p.done
                            ? "Cumplimiento retirado."
                            : "Sesión completada.",
                        )
                      }
                    >
                      {p.done ? "Desmarcar" : "Marcar completada"}
                    </button>
                  )}
                </div>
              ))}
            </Panel>
          )}
        </>
      ) : (
        !msg && <p className="empty">Cargando registros…</p>
      )}
    </>
  );
}
