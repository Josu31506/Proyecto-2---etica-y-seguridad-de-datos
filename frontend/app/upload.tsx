"use client";
import { FormEvent, useState } from "react";
import { api, errorText } from "./lib";
import { Notice, Panel } from "./ui";

export function Upload({
  owner,
  name,
  saved,
}: {
  owner: string;
  name: string;
  saved: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = new FormData(event.currentTarget).get("archive");
    if (!(file instanceof File) || file.size === 0 || file.size > 65536) {
      setMessage("Selecciona un CSV de hasta 64 KiB.");
      return;
    }
    setBusy(true);
    try {
      const result = await api<{ days: number }>(
        "clients/" + owner + "/metrics/import",
        "POST",
        { csv: await file.text() },
      );
      saved(
        "Importación completada: " +
          result.days +
          (result.days === 1 ? " día." : " días."),
      );
    } catch (error) {
      setMessage(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="Importar mediciones CSV">
      <p>
        Selecciona un archivo de {name}. Usa las columnas{" "}
        <code>day,minutes,steps</code> y fechas AAAA-MM-DD. Puedes añadir{" "}
        <code>sleep,pulse,weight,fat</code>. Cada fila corresponde a un día.
      </p>
      <form onSubmit={send}>
        <label>
          Archivo CSV
          <input name="archive" type="file" accept=".csv,text/csv" required />
        </label>
        <button className="primary" disabled={busy}>
          {busy ? "Importando…" : "Importar archivo"}
        </button>
      </form>
      <Notice msg={message} />
    </Panel>
  );
}
