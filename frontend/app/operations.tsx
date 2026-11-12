"use client";
import { FormEvent, useEffect, useState } from "react";
import { api, dateLabel, errorText, roleLabel, Role } from "./lib";
import { Panel, Notice } from "./ui";
type Account = { id: string; name: string; role: Role; trainer: string | null };
type Operations = {
  accounts: Account[];
  incidents: {
    id: string;
    category: string;
    created: string;
    resolved: string | null;
  }[];
  backups: { at: string; action: string }[];
};
const names: Record<string, string> = {
  acceso: "Acceso indebido",
  divulgacion: "Divulgación de información",
  perdida: "Pérdida de datos",
};
export function OperationsView() {
  const [data, setData] = useState<Operations | null>(null);
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [owner, setOwner] = useState(""),
    [trainer, setTrainer] = useState("");
  const reload = () => api<Operations>("admin/operations").then(setData);
  useEffect(() => {
    reload().catch((e) => setMessage(errorText(e)));
  }, []);
  async function submit(
    path: string,
    method: string,
    body: unknown,
    ok: string,
  ) {
    setBusy(true);
    try {
      await api(path, method, body);
      await reload();
      setMessage(ok);
    } catch (e) {
      setMessage(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  function incident(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    void submit(
      "admin/incidents",
      "POST",
      { category: f.get("category") },
      "Incidente registrado.",
    );
  }
  const clients = data?.accounts.filter((a) => a.role === "cliente") || [],
    staff = data?.accounts.filter((a) => a.role === "entrenador") || [];
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Operaciones del club</h1>
          <p className="sub">
            Asignaciones de acceso, incidentes y comprobaciones de respaldo.
          </p>
        </div>
      </div>
      <Notice msg={message} />
      {data && (
        <>
          <Panel title="Usuarios y asignaciones">
            <p>
              Selecciona un cliente para revisar quién puede consultar su ficha.
              El cambio se aplica al siguiente acceso.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void submit(
                  "admin/assignments/" + owner,
                  "PUT",
                  { trainer },
                  "Asignación guardada.",
                );
              }}
            >
              <div className="formgrid">
                <label>
                  Cliente
                  <select
                    aria-label="Cliente de la asignación"
                    required
                    value={owner}
                    onChange={(e) => {
                      setOwner(e.target.value);
                      setTrainer(
                        clients.find((a) => a.id === e.target.value)?.trainer ||
                          "",
                      );
                    }}
                  >
                    <option value="">Seleccionar</option>
                    {clients.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Entrenador
                  <select
                    aria-label="Entrenador de la asignación"
                    required
                    value={trainer}
                    onChange={(e) => setTrainer(e.target.value)}
                  >
                    <option value="">Seleccionar</option>
                    {staff.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                disabled={busy || !owner || !trainer}
                className="secondary"
              >
                Guardar asignación
              </button>
            </form>
            <details>
              <summary>Ver usuarios y roles</summary>
              <ul>
                {data.accounts.map((a) => (
                  <li key={a.id}>
                    {a.name} · {roleLabel(a.role)}
                  </li>
                ))}
              </ul>
            </details>
          </Panel>
          <div className="split">
            <Panel title="Incidentes de seguridad">
              <form onSubmit={incident}>
                <label>
                  Categoría
                  <select name="category" aria-label="Categoría del incidente">
                    {Object.entries(names).map(([value, name]) => (
                      <option key={value} value={value}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="secondary" disabled={busy}>
                  Registrar incidente
                </button>
              </form>
              {data.incidents.length === 0 ? (
                <p>Aún no hay incidentes.</p>
              ) : (
                data.incidents.map((i) => (
                  <div className="row" key={i.id}>
                    <div>
                      <b>{names[i.category]}</b>
                      <small>
                        {dateLabel(i.created)} ·{" "}
                        {i.resolved ? "Cerrado" : "Abierto"}
                      </small>
                    </div>
                    {!i.resolved && (
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          void submit(
                            "admin/incidents/" + i.id + "/resolve",
                            "PUT",
                            undefined,
                            "Incidente cerrado.",
                          )
                        }
                      >
                        Cerrar caso
                      </button>
                    )}
                  </div>
                ))
              )}
            </Panel>
            <Panel title="Respaldos y restauraciones">
              {data.backups.length === 0 ? (
                <p>Aún no se ha registrado una operación de respaldo.</p>
              ) : (
                data.backups.map((v, i) => (
                  <div className="row" key={i}>
                    <b>
                      {v.action === "respaldo.crear"
                        ? "Copia creada"
                        : "Restauración verificada"}
                    </b>
                    <small>{dateLabel(v.at)}</small>
                  </div>
                ))
              )}
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
