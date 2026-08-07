export function fmt(v: number | null | undefined, nd = 2): string {
  if (v == null || Number.isNaN(v)) return "—";
  const av = Math.abs(v);
  if (av !== 0 && (av < 0.001 || av >= 100000)) return v.toExponential(2);
  return v.toLocaleString(undefined, { minimumFractionDigits: nd, maximumFractionDigits: nd });
}

export function sign(v: number | null | undefined): string {
  return v != null && v > 0 ? "+" : "";
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ");
}
