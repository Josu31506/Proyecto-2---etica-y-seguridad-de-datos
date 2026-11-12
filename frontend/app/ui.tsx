import type { ReactNode } from "react";
export function Mark() {
  return (
    <span className="mark" aria-hidden="true">
      <svg viewBox="0 0 58 44">
        <path
          fill="currentColor"
          d="M1 40 25 3h9L10 40zm24-10L36 13l18 27H43l-7-12-8 12H18z"
        />
      </svg>
    </span>
  );
}
export function Brand() {
  return (
    <div className="brand">
      <Mark />
      <span>
        ALZACE<small>FITNESS CLUB</small>
      </span>
    </div>
  );
}
const paths: Record<string, string> = {
  grid: "M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z",
  stats: "M4 20V5m0 15h17M8 16v-3m5 3V8m5 8v-6",
  lock: "M6 10h12v10H6zM8 10V7a4 4 0 0 1 8 0v3",
  arrow: "M4 12h15m-6-6 6 6-6 6",
  pulse: "M2 12h5l3-8 4 16 3-8h5",
  run: "m4 17 5-4 4 2 3-7m-8 1 4-3 5 3 4-1M8 20l5-5m4-12h.01",
  list: "M4 6h2m3 0h12M4 12h2m3 0h12M4 18h2m3 0h12",
  exit: "M10 4H4v16h6m3-12 4 4-4 4m-5-4h12",
  target: "M21 12a9 9 0 1 1-9-9m5 9a5 5 0 1 1-5-5m0 5 9-9",
  shield: "m12 2 8 4v6c0 5-5 8-8 10-3-2-8-5-8-10V6zm-4 10 3 3 5-6",
  bell: "M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zm5 3h4",
};
export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
export function Track() {
  return (
    <svg
      aria-hidden="true"
      className="track"
      viewBox="0 0 430 330"
      preserveAspectRatio="xMaxYMid slice"
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth="2.3"
        transform="rotate(-31 235 154)"
      >
        {Array.from({ length: 9 }, (_, i) => (
          <rect
            key={i}
            x={31 + i * 8}
            y={25 + i * 8}
            width={390 - i * 16}
            height={253 - i * 16}
            rx={126 - i * 8}
          />
        ))}
      </g>
    </svg>
  );
}
export function Panel({
  over,
  title,
  children,
}: {
  over?: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      {over && <div className="eyebrow">{over}</div>}
      <h2>{title}</h2>
      {children}
    </section>
  );
}
export function Notice({ msg }: { msg: string }) {
  return msg ? (
    <p className="notice" role="status">
      {msg}
    </p>
  ) : null;
}
