import { Link, NavLink, Outlet } from "react-router-dom";
import { ThemeToggle } from "../components/ui/ThemeToggle";
import { ApiHealthBanner } from "../components/ui/ApiHealthBanner";

const TABS: { to: string; label: string; icon: string }[] = [
  { to: "anomaly", label: "Anomaly Evidence", icon: '<path d="M12 3v11"/><path d="M7 9l5 5 5-5"/><path d="M5 21h14"/>' },
  { to: "atmospheric", label: "Atmospheric Evidence", icon: '<path d="M3 10c2-3.5 4-3.5 6 0s4 3.5 6 0 4-3.5 6 0"/><path d="M3 16c2-3.5 4-3.5 6 0s4 3.5 6 0 4-3.5 6 0"/>' },
  { to: "oceanic", label: "Oceanic Evidence", icon: '<path d="M2 15c2.5-2 4.5-2 7 0s4.5 2 7 0 4.5-2 6-1"/><circle cx="17" cy="6" r="3"/>' },
  { to: "matrix", label: "Integrated Evidence Matrix", icon: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>' },
  { to: "maps", label: "Maps & Diagnostics", icon: '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M3 15l5-4 4 3 4-5 5 4"/>' },
  { to: "methodology", label: "Methodology & Data", icon: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>' },
];

export function Dashboard() {
  return (
    <div>
      <div className="topbar">
        <div className="wrap topbar-inner">
          <Link to="/" className="back-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M19 12H5M11 18l-6-6 6-6" />
            </svg>
            Overview
          </Link>
          <Link to="/dashboard" className="brand">
            <svg className="mark" viewBox="0 0 24 24" fill="none" strokeWidth="1.6">
              <path d="M3 14c2-4 4-4 6 0s4 4 6 0 4-4 6 0" stroke="var(--wet)" />
              <path d="M4 18c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="var(--dry)" />
            </svg>
            Forecast Evidence &amp; Diagnostic System
          </Link>
          <div className="topbar-meta">
            <span>NMME ENSMEAN</span>
            <ThemeToggle />
          </div>
        </div>
      </div>

      <div className="tabs">
        <div className="wrap tabs-inner">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} className={({ isActive }) => `tab-btn${isActive ? " active" : ""}`}>
              <span dangerouslySetInnerHTML={{ __html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${t.icon}</svg>` }} />
              <span>{t.label}</span>
            </NavLink>
          ))}
        </div>
      </div>

      <div className="wrap">
        <ApiHealthBanner />
        <Outlet />
      </div>
    </div>
  );
}
