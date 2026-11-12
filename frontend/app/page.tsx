"use client";
import { useState, useEffect, FormEvent } from "react";
import { api, User, Role, roleLabel, errorText, ApiError } from "./lib";
import { Brand, Track, Icon, Notice } from "./ui";
import { Training } from "./training";
import { Privacy, ConsentView, AuditView, AlertsView } from "./privacy";
import { OperationsView } from "./operations";
const views = {
  cliente: [
    ["actividad", "Mi actividad", "grid"],
    ["privacidad", "Mi privacidad", "shield"],
  ],
  entrenador: [
    ["actividad", "Mis clientes", "grid"],
    ["alertas", "Seguimiento", "bell"],
    ["grupal", "Estadísticas", "stats"],
  ],
  administrador: [
    ["grupal", "Estadísticas", "stats"],
    ["auditoria", "Auditoría", "list"],
    ["operaciones", "Operaciones", "lock"],
  ],
};
function SignIn({ enter }: { enter: (u: User) => void }) {
  const [demo, setDemo] = useState(false),
    [ready, setReady] = useState(false),
    [role, setRole] = useState<Role>("cliente");
  const [busy, setBusy] = useState(false),
    [msg, setMsg] = useState(""),
    [password, setPassword] = useState(false);
  useEffect(() => {
    api<{ demo: boolean }>("health")
      .then((v) => {
        setDemo(v.demo);
        setPassword(!v.demo);
        setReady(true);
      })
      .catch(() =>
        setMsg(
          "No hay conexión con la API. Comprueba que el backend esté en ejecución.",
        ),
      );
  }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setMsg("");
    try {
      enter(
        await api<User>(
          password ? "auth/login" : "auth/demo",
          "POST",
          password
            ? { email: data.get("email"), password: data.get("password") }
            : { alias: role },
        ),
      );
    } catch (err) {
      setMsg(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="entrance">
      <div className="entry-wrap">
        <section className="cover">
          <Brand />
          <div className="covercopy">
            <span className="eyebrow">CUADERNO DE ENTRENAMIENTO</span>
            <h1>
              Actividad <br />
              en perspectiva<span>.</span>
            </h1>
            <p>Tu progreso, tus sesiones y las personas que te acompañan.</p>
          </div>
          <Track />
          <div className="coverfoot">
            ALZACE FITNESS CORPORATION <span>LIMA · PERÚ</span>
          </div>
        </section>
        <section className="entry-panel">
          <div className="eyebrow">ACCESO AL CLUB</div>
          <h2>{password ? "Iniciar sesión" : "Elige tu perfil"}</h2>
          <p className="sub">
            {password
              ? "Usa tu cuenta para acceder a tu espacio."
              : "Explora el seguimiento de entrenamiento con perfiles de demostración."}
          </p>
          <form onSubmit={submit}>
            {password ? (
              <>
                <label>
                  Correo electrónico
                  <input
                    required
                    type="email"
                    autoComplete="username"
                    name="email"
                  />
                </label>
                <label>
                  Contraseña
                  <input
                    required
                    type="password"
                    autoComplete="current-password"
                    name="password"
                  />
                </label>
              </>
            ) : (
              <div
                role="group"
                aria-label="Perfil de demostración"
                className="roles"
              >
                {(["cliente", "entrenador", "administrador"] as Role[]).map(
                  (r, i) => (
                    <button
                      aria-pressed={r === role}
                      key={r}
                      className={r === role ? "selected" : ""}
                      type="button"
                      onClick={() => setRole(r)}
                    >
                      <Icon name={["pulse", "target", "lock"][i]} />
                      <span>
                        {roleLabel(r)}
                        <small>
                          {
                            [
                              "Mi actividad y mis metas",
                              "Planes y clientes asignados",
                              "Estadísticas protegidas y auditoría",
                            ][i]
                          }
                        </small>
                      </span>
                      <span className="radio" />
                    </button>
                  ),
                )}
              </div>
            )}
            <button className="primary wide" disabled={busy || !ready}>
              {busy
                ? "Entrando…"
                : password
                  ? "Iniciar sesión"
                  : "Entrar al panel"}
              <Icon name="arrow" />
            </button>
          </form>
          <Notice msg={msg} />
          {demo && (
            <button className="textbtn" onClick={() => setPassword(!password)}>
              {password
                ? "Volver a perfiles de demostración"
                : "Usar correo y contraseña"}
            </button>
          )}
          <p className="entrynote">
            <Icon name="shield" size={16} />
            {demo
              ? "Entorno académico local · perfiles ficticios"
              : "Acceso personal · sesión protegida"}
          </p>
        </section>
      </div>
    </main>
  );
}
export default function Page() {
  const [u, setU] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [view, setView] = useState(""),
    [err, setErr] = useState("");
  function enter(x: User) {
    setU(x);
    setView(views[x.role][0][0]);
    setErr("");
  }
  useEffect(() => {
    let alive = true;
    api<User>("me")
      .then((x) => {
        if (alive) enter(x);
      })
      .catch((e) => {
        if (alive && !(e instanceof ApiError && e.status === 401))
          setErr(errorText(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    const clear = () => setU(null);
    window.addEventListener("alzace:expired", clear);
    return () => {
      alive = false;
      window.removeEventListener("alzace:expired", clear);
    };
  }, []);
  if (loading)
    return (
      <main className="loading">
        <Brand />
        <p>Cargando tu espacio…</p>
      </main>
    );
  if (!u) return <SignIn enter={enter} />;
  const current = views[u.role].find(([k]) => k === view);
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand />
        <div className="side-line" />
        <small className="eyebrow nav-label">MI ESPACIO</small>
        <nav>
          {views[u.role].map(([k, t, ic]) => (
            <button
              key={k}
              aria-current={k === view ? "page" : undefined}
              onClick={() => setView(k)}
            >
              <Icon name={ic} />
              {t}
            </button>
          ))}
        </nav>
        <div className="sidelow">
          <span className="avatar">{u.name[0]}</span>
          <span>
            {u.name}
            <small>{roleLabel(u.role)}</small>
          </span>
          <button
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
            onClick={() =>
              api("auth/logout", "POST")
                .then(() => setU(null))
                .catch((e) => setErr(errorText(e)))
            }
          >
            <Icon name="exit" />
          </button>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <span>
            Club <b>/</b> {current?.[1]}
          </span>
          <span className="badge">
            <i />
            {roleLabel(u.role)}
          </span>
        </header>
        <Notice msg={err} />
        {view === "actividad" && <Training user={u} />}
        {view === "grupal" && <Privacy user={u} />}
        {view === "privacidad" && <ConsentView user={u} change={setU} />}
        {view === "auditoria" && <AuditView />}
        {view === "operaciones" && <OperationsView />}
        {view === "alertas" && <AlertsView />}
        <footer>
          ALZACE <span>Seguimiento de entrenamiento · DS3031</span>
        </footer>
      </main>
    </div>
  );
}
