import { useEffect, useState } from "react";
import { API_BASE, getJson } from "../../api/client";
import { Callout } from "./Callout";

type Status = "checking" | "ok" | "unreachable" | "unexpected";

/**
 * Pings /api/health once per mount and shows a persistent, specific banner
 * if the backend can't be reached or doesn't look like this app's API --
 * e.g. VITE_API_BASE_URL pointing at the wrong port, or another service
 * already squatting on the expected port. Without this, every page just
 * shows an unexplained "Loading..." forever.
 */
export function ApiHealthBanner() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    getJson<{ status?: string; service?: string }>("/api/health")
      .then((data) => {
        if (cancelled) return;
        // Check the "service" marker, not just status === "ok" -- another
        // local API can coincidentally return the exact same generic shape
        // for its own health check (this bit us during development: a
        // pre-existing service on the same port also returned {"status":"ok"}).
        setStatus(data?.status === "ok" && data?.service === "forecast-evidence-api" ? "ok" : "unexpected");
      })
      .catch(() => {
        if (!cancelled) setStatus("unreachable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "checking" || status === "ok") return null;

  return (
    <Callout tone="warn" title="Can't reach the Forecast Evidence API.">
      This dashboard is configured to call <code className="mono">{API_BASE}</code>, but{" "}
      {status === "unreachable"
        ? "the request failed (no response, CORS block, or connection refused)."
        : "a response came back that doesn't look like this API (something else may be running on that port)."}{" "}
      Confirm the FastAPI backend is running there, and that <code className="mono">FRONTEND_ORIGIN</code> on the
      backend and <code className="mono">VITE_API_BASE_URL</code> on the frontend point at each other &mdash; see the
      README or <a href="/docs">Docs</a> page.
    </Callout>
  );
}
