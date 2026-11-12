import type { Metadata } from "next";
import { connection } from "next/server";
import "./style.css";
export const metadata: Metadata = {
  title: "Alzace | Seguimiento de entrenamiento",
  description:
    "Seguimiento individual y estadísticas protegidas para Alzace Fitness.",
};
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  await connection();
  return (
    <html lang="es-PE">
      <body>{children}</body>
    </html>
  );
}
