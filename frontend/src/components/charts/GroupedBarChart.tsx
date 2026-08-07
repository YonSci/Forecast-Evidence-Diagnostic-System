import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from "recharts";
import { fmt, sign } from "../../lib/format";

export interface GroupedSeries {
  key: string;
  name: string;
  color: string;
}

function TooltipContent({ active, payload, label, unit }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; unit: string }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="chart-tooltip">
      <b>{label}</b>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {sign(p.value)}{fmt(p.value, 2)} {unit}
        </div>
      ))}
    </div>
  );
}

export function GroupedBarChart({
  data,
  series,
  unit = "",
  height = 240,
}: {
  data: Record<string, number | string>[];
  series: GroupedSeries[];
  unit?: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 14, right: 14, bottom: 8, left: 8 }}>
        <XAxis dataKey="label" axisLine={{ stroke: "var(--hairline)" }} tickLine={false} tick={{ fontFamily: "var(--mono)", fontSize: 10.5, fill: "var(--muted)" }} />
        <YAxis hide />
        <ReferenceLine y={0} stroke="var(--muted)" />
        <Tooltip cursor={{ fill: "var(--surface-3)" }} content={<TooltipContent unit={unit} />} />
        {series.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[3, 3, 3, 3]} maxBarSize={22} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
