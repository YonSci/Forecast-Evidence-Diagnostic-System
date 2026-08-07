import { useFetch } from "../../hooks/useFetch";
import { assetUrl } from "../../api/client";
import type { GalleryImage } from "../../api/types";
import { MapFigure } from "../../components/ui/MapFigure";

const GROUP_LABELS: Record<string, string> = {
  rainfall: "Rainfall anomaly (NMME, JJAS 2026)",
  oceanic: "SST / ocean-driver proxy (NMME)",
  circulation: "Circulation diagnostics (NMME / ERA5)",
};
const GROUP_ORDER = ["rainfall", "oceanic", "circulation"];

export function MapsDiagnostics() {
  const { data: images } = useFetch<GalleryImage[]>("/api/gallery");

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Maps and diagnostics</h2>
        <p className="sub">
          Report-style diagnostic maps behind the evidence matrix, grouped by evidence stream. For an interactive,
          selectable rainfall map across every region, period, and initialization, see the Anomaly Evidence tab. Click
          any map here to enlarge.
        </p>
      </div>

      {GROUP_ORDER.map((group) => {
        const groupImages = (images ?? []).filter((img) => img.group === group);
        if (!groupImages.length) return null;
        return (
          <div key={group}>
            <h3 style={{ margin: "30px 0 14px", fontSize: "1.05rem", fontFamily: "var(--sans)" }}>{GROUP_LABELS[group]}</h3>
            <div className="map-grid">
              {groupImages.map((img) => (
                <MapFigure key={img.key} src={assetUrl(img.url)} caption={img.caption} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
