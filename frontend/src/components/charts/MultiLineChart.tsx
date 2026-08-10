import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine, Legend } from "recharts";
import { fmt, sign } from "../../lib/format";

export interface LineSeries {
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

export function MultiLineChart({
  data,
  series,
  unit = "",
  height = 260,
}: {
  data: Record<string, number | string | null>[];
  series: LineSeries[];
  unit?: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 14, right: 14, bottom: 8, left: 8 }}>
        <XAxis dataKey="label" axisLine={{ stroke: "var(--hairline)" }} tickLine={false} tick={{ fontFamily: "var(--mono)", fontSize: 10.5, fill: "var(--muted)" }} />
        <YAxis hide domain={["auto", "auto"]} />
        <ReferenceLine y={0} stroke="var(--muted)" />
        <Tooltip cursor={{ stroke: "var(--surface-3)" }} content={<TooltipContent unit={unit} />} />
        <Legend wrapperStyle={{ fontSize: "0.72rem", fontFamily: "var(--sans)" }} />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
