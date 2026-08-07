import { useState } from "react";

export function ThemeToggle() {
  const [mode, setMode] = useState<"light" | "dark" | null>(
    (document.documentElement.getAttribute("data-theme") as "light" | "dark" | null) ?? null
  );

  function toggle() {
    const osDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const current = mode ?? (osDark ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setMode(next);
  }

  return (
    <button className="iconbtn" onClick={toggle} title="Toggle theme" aria-label="Toggle color theme">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="12" cy="12" r="4.2" />
        <path d="M12 2v2.4M12 19.6V22M4.2 4.2l1.7 1.7M18.1 18.1l1.7 1.7M2 12h2.4M19.6 12H22M4.2 19.8l1.7-1.7M18.1 5.9l1.7-1.7" />
      </svg>
    </button>
  );
}
