import { Pill } from "./Pill";
import type { PillTone } from "./Pill";
import { fmt, sign } from "../../lib/format";

export function StatTile({
  label,
  value,
  unit = "",
  footLabel,
  footTone = "neutral",
}: {
  label: string;
  value: number | null;
  unit?: string;
  footLabel?: string;
  footTone?: PillTone;
}) {
  return (
    <div className="stat-tile">
      <div className="label">{label}</div>
      <div className="value">
        {value == null ? "—" : `${sign(value)}${fmt(value, 2)}`}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {footLabel && (
        <div className="foot">
          <Pill tone={footTone}>{footLabel}</Pill>
        </div>
      )}
    </div>
  );
}
