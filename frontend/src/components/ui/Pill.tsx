import type { ReactNode } from "react";

export type PillTone = "dry" | "wet" | "neutral" | "outline";

export function Pill({ tone = "neutral", small = false, children }: { tone?: PillTone; small?: boolean; children: ReactNode }) {
  const cls = `pill pill-${tone}${small ? " pill-sm" : ""}`;
  return <span className={cls}>{children}</span>;
}

export function directionTone(direction: string | null | undefined): { tone: PillTone; label: string } {
  if (direction === "supports_dry_kiremt") return { tone: "dry", label: "Supports dry" };
  if (direction === "supports_wet_or_reduces_dry_risk") return { tone: "wet", label: "Supports wet" };
  return { tone: "neutral", label: "Neutral / context" };
}
