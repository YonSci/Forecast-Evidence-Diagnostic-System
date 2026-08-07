import type { ReactNode } from "react";

const INFO_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </svg>
);

const WARN_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M12 3l9 17H3z" />
    <path d="M12 9v5M12 17h.01" />
  </svg>
);

export function Callout({ tone = "info", title, children }: { tone?: "info" | "warn"; title?: string; children: ReactNode }) {
  return (
    <div className={`callout${tone === "warn" ? " warn" : ""}`}>
      <span>{tone === "warn" ? WARN_ICON : INFO_ICON}</span>
      <div>
        {title && <b>{title} </b>}
        {children}
      </div>
    </div>
  );
}
