import { test, expect, Page } from "@playwright/test";
import { join } from "node:path";
async function login(page: Page, role: RegExp) {
  await page.goto("/");
  await page.getByRole("button", { name: role }).click();
  await page.getByRole("button", { name: "Entrar al panel" }).click();
}
test("cliente: seguimiento real, registro guardado, consentimiento reversible", async ({
  page,
}) => {
  await login(page, /^Cliente Mi actividad/);
  await expect(
    page.getByRole("heading", { name: "Lucía Valle" }),
  ).toBeVisible();
  if (process.env.QA_DIR)
    await page.screenshot({
      path: join(process.env.QA_DIR, "dashboard.png"),
      fullPage: true,
    });
  await page.getByRole("button", { name: "Registrar medición" }).click();
  await page.getByLabel("Minutos activos", { exact: true }).fill("47");
  await page.getByLabel("Pasos", { exact: true }).fill("4321");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Medición guardada.")).toBeVisible();
  await page.getByRole("button", { name: "Historial", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "4321", exact: true }).first(),
  ).toBeVisible();
  const day = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "America/Lima",
  }).format(new Date());
  await page
    .getByLabel("Archivo CSV")
    .setInputFiles({
      name: "actividad.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("day,minutes,steps\n" + day + ",45,5432"),
    });
  await page.getByRole("button", { name: "Importar archivo" }).click();
  await expect(page.getByText("Importación completada: 1 día.")).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "5432", exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mi privacidad" }).click();
  await page.getByRole("button", { name: "Permitir uso grupal" }).click();
  await expect(page.getByText("Participación habilitada")).toBeVisible();
  await page.getByRole("button", { name: "Retirar permiso" }).click();
  await expect(page.getByText("Participación desactivada")).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(
    page.getByRole("heading", { name: "Elige tu perfil" }),
  ).toBeVisible();
});
test("administración: publicación, caché y auditoría", async ({ page }) => {
  await login(page, /^Administrador Estadísticas/);
  await page
    .getByRole("combobox", { name: "Fuente", exact: true })
    .selectOption("programa");
  await page.getByRole("button", { name: /Publicar estimación/ }).click();
  await expect(
    page.getByText("ESTIMACIÓN PUBLICADA", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("combobox", { name: "Fuente", exact: true })
    .selectOption("programa");
  await expect(
    page.getByText("ESTIMACIÓN PUBLICADA", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Auditoría", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "estadistica.publicar" }),
  ).toBeVisible();
});
test("entrenador en pantalla móvil: clientes y alertas", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, /^Entrenador Planes/);
  await page
    .getByRole("combobox", { name: "Cliente asignado", exact: true })
    .selectOption("demo-lucia");
  await expect(
    page.getByRole("heading", { name: "Lucía Valle" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Seguimiento", exact: true }).click();
  await page
    .getByRole("button", { name: "Registrar atención" })
    .first()
    .click();
  await expect(page.getByText("Primera atención registrada.")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  if (process.env.QA_DIR)
    await page.screenshot({
      path: join(process.env.QA_DIR, "movil.png"),
      fullPage: true,
    });
});
