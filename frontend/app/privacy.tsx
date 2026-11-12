"use client";
import { useEffect, useState } from "react";
import {
  api,
  User,
  Analytics,
  Release,
  AlertList,
  Audit,
  errorText,
  dateLabel,
} from "./lib";
import { Panel, Notice, Icon } from "./ui";
function Heading({
  over,
  title,
  sub,
}: {
  over: string;
  title: string;
  sub: string;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{over}</div>
        <h1>{title}</h1>
        <p className="sub">{sub}</p>
      </div>
    </div>
  );
}
function seriesName(key: string) {
  return key === "estudio" ? "Estudio Fitbit" : "Programa de entrenamiento";
}
export function Privacy({ user }: { user: User }) {
  const [x, setX] = useState<Analytics | null>(null),
    [source, setSource] = useState("estudio"),
    [month, setMonth] = useState("2016-04"),
    [busy, setBusy] = useState(false),
    [msg, setMsg] = useState("");
  const reload = () => api<Analytics>("analytics").then(setX);
  useEffect(() => {
    reload().catch((e) => setMsg(errorText(e)));
  }, []);
  const old = x?.releases.find(
    (r) => r.source === source && r.period === month,
  );
  async function publish() {
    setBusy(true);
    setMsg("");
    try {
      const r = await api<{ cached: boolean; release: Release }>(
        "analytics/publish",
        "POST",
        { source, period: month },
      );
      await reload();
      setMsg(
        r.cached
          ? "Se recuperó la publicación existente."
          : "Publicación guardada. Consultarla de nuevo no consume presupuesto.",
      );
    } catch (e) {
      setMsg(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        over="ANÁLISIS DE COHORTES"
        title="Estadísticas protegidas"
        sub="Promedio diario de minutos activos por participante. Los resultados grupales incluyen ruido para proteger la contribución individual."
      />
      <Notice msg={msg} />
      {x && (
        <>
          <div className="budget">
            <div>
              <div className="eyebrow">PRESUPUESTO COMPARTIDO</div>
              <h2>Privacidad diferencial</h2>
              <p>
                Cada publicación nueva utiliza ε = 1. Leer una existente no
                genera ruido adicional.
              </p>
            </div>
            <div className="budget-side">
              <b>
                {x.budget.spent} <small>/ {x.budget.total} ε</small>
              </b>
              <progress value={x.budget.spent} max={x.budget.total} />
              <small>Presupuesto utilizado</small>
            </div>
          </div>
          <div className="split">
            <Panel over="CONSULTA" title="Actividad del grupo">
              <div className="formgrid">
                <label>
                  Fuente
                  <select
                    aria-label="Fuente"
                    value={source}
                    onChange={(e) => {
                      const s = e.target.value;
                      setSource(s);
                      setMonth(s === "estudio" ? "2016-04" : x.periods[s][0]);
                      setMsg("");
                    }}
                  >
                    <option value="estudio">Estudio Fitbit</option>
                    <option value="programa">Programa de entrenamiento</option>
                  </select>
                </label>
                <label>
                  Periodo
                  <select
                    aria-label="Periodo"
                    value={month}
                    onChange={(e) => {
                      setMonth(e.target.value);
                      setMsg("");
                    }}
                  >
                    {x.periods[source].map((d) => (
                      <option key={d}>{d}</option>
                    ))}
                  </select>
                </label>
              </div>
              {old ? (
                <div className="answer">
                  <small>ESTIMACIÓN PUBLICADA</small>
                  <div>
                    {old.minutes ?? "—"}{" "}
                    <span>{old.minutes !== null ? "min/día" : ""}</span>
                  </div>
                  <p>
                    {old.minutes === null
                      ? "Estimación omitida: el conteo protegido no alcanzó el mínimo."
                      : "Media protegida de los promedios personales."}
                  </p>
                </div>
              ) : (
                <div className="empty">
                  Todavía no se ha publicado una estimación para este periodo.
                </div>
              )}
              {user.role === "administrador" && !old && (
                <button
                  className="primary"
                  disabled={busy || x.budget.spent >= x.budget.total}
                  onClick={publish}
                >
                  {busy
                    ? "Publicando…"
                    : x.budget.spent >= x.budget.total
                      ? "Presupuesto agotado"
                      : "Publicar estimación · ε = 1"}
                </button>
              )}
            </Panel>
            <Panel over="TRANSPARENCIA" title="Cómo leer la cifra">
              <p>
                Una persona aporta un promedio de sus días con registro. El
                aporte se limita a 120 minutos; los días ausentes no se
                convierten en cero.
              </p>
              <p>
                Se protegen tanto la suma como el conteo. Los grupos pequeños
                pueden tener más error. Esta consulta sirve para tendencias del
                grupo y no para evaluar a un cliente.
              </p>
              <div className="mini-note">
                <Icon name="shield" />
                <span>
                  Consulta mensual fija · δ = 0<br />
                  Sin filtros individuales ni totales exactos.
                </span>
              </div>
            </Panel>
          </div>
          <Panel over="RESULTADOS GUARDADOS" title="Publicaciones">
            {!x.releases.length ? (
              <p className="empty">Aún no se han publicado resultados.</p>
            ) : (
              x.releases.map((r) => (
                <div className="row" key={r.source + r.period}>
                  <span>
                    <b>{seriesName(r.source)}</b>
                    <small>
                      {r.period} · ε = {r.epsilon}
                    </small>
                  </span>
                  <strong>
                    {r.minutes === null ? "Omitida" : r.minutes + " min/día"}
                  </strong>
                </div>
              ))
            )}
          </Panel>
        </>
      )}
    </>
  );
}
export function ConsentView({
  user,
  change,
}: {
  user: User;
  change: (u: User) => void;
}) {
  const [msg, setMsg] = useState(""),
    [busy, setBusy] = useState(false);
  async function toggle() {
    setBusy(true);
    try {
      change(await api<User>("me/consent", "PUT", { allow: !user.analytics }));
      setMsg("Preferencia guardada.");
    } catch (e) {
      setMsg(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        over="PREFERENCIAS PERSONALES"
        title="Mi privacidad"
        sub="Tú decides si tu actividad puede contribuir a las próximas estadísticas del programa."
      />
      <Panel title="Participación en estadísticas grupales">
        <p>
          La finalidad es estimar la actividad media del grupo. Participar es
          opcional. Tu entrenador puede seguir acompañándote aunque elijas no
          participar.
        </p>
        <p>
          Si retiras el permiso, no contribuirás a publicaciones nuevas. Las
          estadísticas protegidas ya publicadas se mantienen.
        </p>
        <div className="row">
          <div>
            <b>
              {user.analytics
                ? "Participación habilitada"
                : "Participación desactivada"}
            </b>
            <small>
              {user.consent_at
                ? "Preferencia registrada: " + dateLabel(user.consent_at)
                : "No has dado permiso para este uso."}
            </small>
          </div>
          <button className="secondary" disabled={busy} onClick={toggle}>
            {user.analytics ? "Retirar permiso" : "Permitir uso grupal"}
          </button>
        </div>
        <Notice msg={msg} />
      </Panel>
    </>
  );
}
export function AlertsView() {
  const [data, setData] = useState<AlertList | null>(null),
    [msg, setMsg] = useState(""),
    [busy, setBusy] = useState(false);
  const refresh = () => api<AlertList>("trainer/alerts").then(setData);
  useEffect(() => {
    refresh().catch((e) => setMsg(errorText(e)));
  }, []);
  async function respond(id: string) {
    setBusy(true);
    try {
      await api("plans/" + id + "/respond", "POST");
      await refresh();
      setMsg("Primera atención registrada.");
    } catch (e) {
      setMsg(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        over="ACOMPAÑAMIENTO"
        title="Seguimiento de sesiones"
        sub="Una sesión sigue pendiente al comenzar el segundo día posterior a su fecha si el cliente no la marcó como completada. No es una alerta médica."
      />
      <Notice msg={msg} />
      {data && (
        <Panel title="Alertas sin atender">
          <p>
            Primera respuesta media ({data.period}):{" "}
            <b>
              {data.hours === null
                ? "Sin respuestas registradas"
                : data.hours + " horas"}
            </b>
            .
          </p>
          {!data.pending.length && (
            <p className="empty">No hay alertas pendientes.</p>
          )}
          {data.pending.map((p) => (
            <div key={p.id} className="row">
              <div>
                <b>
                  {p.name} · {p.label}
                </b>
                <small>Pendiente desde {dateLabel(p.at)}</small>
              </div>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => respond(p.id)}
              >
                Registrar atención
              </button>
            </div>
          ))}
        </Panel>
      )}
    </>
  );
}
export function AuditView() {
  const [data, setData] = useState<Audit | null>(null),
    [msg, setMsg] = useState("");
  const refresh = () =>
    api<Audit>("admin/audit")
      .then(setData)
      .catch((e) => setMsg(errorText(e)));
  useEffect(() => {
    refresh();
  }, []);
  return (
    <>
      <Heading
        over="ADMINISTRACIÓN"
        title="Registro de auditoría"
        sub="Accesos y acciones sobre la plataforma. Las mediciones y las credenciales no se incluyen en el registro."
      />
      <Notice msg={msg} />
      {data && (
        <>
          <Panel title="Continuidad del servicio">
            <p>
              Retención del último mes cerrado ({data.retention.period}):{" "}
              <b>
                {data.retention.retention === null
                  ? "No aplica"
                  : data.retention.retention + "%"}
              </b>
              .
            </p>
          </Panel>
          <Panel title="Eventos recientes">
            <button className="secondary" onClick={refresh}>
              Actualizar
            </button>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Fecha (UTC)</th>
                    <th>Actor</th>
                    <th>Acción</th>
                    <th>Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {data.events.map((r) => (
                    <tr key={r.id}>
                      <td>{r.at.slice(0, 19).replace("T", " ")}</td>
                      <td>{r.actor}</td>
                      <td>{r.action}</td>
                      <td>{r.outcome === "ok" ? "Correcto" : "Denegado"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
