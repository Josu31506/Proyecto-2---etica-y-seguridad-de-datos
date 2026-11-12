export type Role = "cliente" | "entrenador" | "administrador";
export type User = {
  id: string;
  name: string;
  role: Role;
  analytics: boolean;
  consent_at: string | null;
};
export type Metric = {
  day: string;
  minutes: number;
  steps: number;
  sleep: number | null;
  pulse: number | null;
  weight: number | null;
  fat: number | null;
};
export type Plan = {
  id: string;
  day: string;
  label: string;
  done: boolean;
  attended: string | null;
  alert: boolean;
};
export type Goal = {
  months: number;
  minutes: number;
  activity_weight: number;
  fat_drop: number;
  start: string;
  end: string;
  observed_minutes: number;
  percent: number | null;
};
export type Profile = {
  id: string;
  name: string;
  source: string;
  history: Metric[];
  plans: Plan[];
  weekly_done: number;
  weekly_total: number;
  month_minutes: number;
  goal: Goal | null;
};
export type Release = {
  source: string;
  period: string;
  minutes: number | null;
  epsilon: number;
  delta: number;
  created: string;
};
export type Analytics = {
  budget: { spent: number; total: number };
  periods: Record<string, string[]>;
  releases: Release[];
};
export type AlertList = {
  period: string;
  hours: number | null;
  pending: { id: string; name: string; label: string; at: string }[];
};
export type Audit = {
  events: {
    id: number;
    at: string;
    actor: string;
    action: string;
    outcome: string;
  }[];
  retention: { period: string; retention: number | null };
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const r = await fetch("/api/" + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Alzace-Request": "web" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && !path.startsWith("auth/") && path !== "me")
      window.dispatchEvent(new Event("alzace:expired"));
    throw new ApiError(
      typeof d.detail === "string"
        ? d.detail
        : r.status === 422
          ? "Revisa los valores ingresados."
          : "No se pudo completar la solicitud.",
      r.status,
    );
  }
  return d;
}
export const dateLabel = (iso: string) =>
  new Intl.DateTimeFormat("es-PE", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(iso.slice(0, 10) + "T12:00:00Z"));
export const localDay = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "America/Lima" }).format(
    new Date(),
  );
export const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Error de conexión.";
export const roleLabel = (r: Role) =>
  ({
    cliente: "Cliente",
    entrenador: "Entrenador",
    administrador: "Administrador",
  })[r];
