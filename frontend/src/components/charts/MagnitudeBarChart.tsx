import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmt } from "../../lib/format";

function TooltipContent({ active, payload, unit }: { active?: boolean; payload?: { payload: { label: string; value: number } }[]; unit: string }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <b>{d.label}</b>
      {fmt(d.value, 1)} {unit}
    </div>
  );
}

export function MagnitudeBarChart({
  data,
  unit = "",
  height = 200,
}: {
  data: { label: string; value: number }[];
  unit?: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 14, right: 14, bottom: 8, left: 8 }}>
        <XAxis dataKey="label" axisLine={{ stroke: "var(--hairline)" }} tickLine={false} tick={{ fontFamily: "var(--mono)", fontSize: 10.5, fill: "var(--muted)" }} />
        <YAxis hide />
        <Tooltip cursor={{ fill: "var(--surface-3)" }} content={<TooltipContent unit={unit} />} />
        <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} maxBarSize={50} />
      </BarChart>
    </ResponsiveContainer>
  );
}
