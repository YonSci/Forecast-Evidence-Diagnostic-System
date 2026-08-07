import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LightboxProvider } from "./components/ui/Lightbox";
import { Home } from "./pages/Home";
import { Docs } from "./pages/Docs";
import { Dashboard } from "./pages/Dashboard";
import { AnomalyEvidence } from "./pages/dashboard/AnomalyEvidence";
import { AtmosphericEvidence } from "./pages/dashboard/AtmosphericEvidence";
import { OceanicEvidence } from "./pages/dashboard/OceanicEvidence";
import { EvidenceMatrix } from "./pages/dashboard/EvidenceMatrix";
import { MapsDiagnostics } from "./pages/dashboard/MapsDiagnostics";
import { Methodology } from "./pages/dashboard/Methodology";

export default function App() {
  return (
    <LightboxProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/dashboard" element={<Dashboard />}>
            <Route index element={<Navigate to="anomaly" replace />} />
            <Route path="anomaly" element={<AnomalyEvidence />} />
            <Route path="atmospheric" element={<AtmosphericEvidence />} />
            <Route path="oceanic" element={<OceanicEvidence />} />
            <Route path="matrix" element={<EvidenceMatrix />} />
            <Route path="maps" element={<MapsDiagnostics />} />
            <Route path="methodology" element={<Methodology />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </LightboxProvider>
  );
}
