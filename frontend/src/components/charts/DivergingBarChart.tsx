import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from "recharts";
import { fmt, sign } from "../../lib/format";

export interface DivergingDatum {
  label: string;
  value: number | null;
  sub?: string;
}

function TooltipContent({ active, payload, unit }: { active?: boolean; payload?: { payload: DivergingDatum }[]; unit: string }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <b>{d.label}</b>
      {d.value == null ? "—" : `${sign(d.value)}${fmt(d.value, 3)} ${unit}`}
      {d.sub && (
        <>
          <br />
          {d.sub}
        </>
      )}
    </div>
  );
}

export function DivergingBarChart({
  data,
  unit = "",
  height = 240,
  highlightLabel,
  onBarClick,
  dryIsPositive = false,
}: {
  data: DivergingDatum[];
  unit?: string;
  height?: number;
  highlightLabel?: string;
  onBarClick?: (label: string) => void;
  /** Set true for fields where a positive value means dry (none currently; kept for completeness). */
  dryIsPositive?: boolean;
}) {
  const dry = "var(--dry)";
  const wet = "var(--wet)";
  const neutral = "var(--neutral-ev)";
  const ink = "var(--ink)";
  const muted = "var(--muted)";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 14, right: 14, bottom: 8, left: 8 }}>
        <XAxis
          dataKey="label"
          axisLine={{ stroke: "var(--hairline)" }}
          tickLine={false}
          tick={(props) => {
            const { x, y, payload } = props;
            const isHi = highlightLabel === payload.value;
            return (
              <text x={x} y={Number(y) + 14} textAnchor="middle" fontFamily="var(--mono)" fontSize={10.5} fill={isHi ? ink : muted} fontWeight={isHi ? 700 : 400}>
                {payload.value}
              </text>
            );
          }}
        />
        <YAxis hide />
        <ReferenceLine y={0} stroke={muted} />
        <Tooltip cursor={{ fill: "var(--surface-3)" }} content={<TooltipContent unit={unit} />} />
        <Bar dataKey="value" radius={[4, 4, 4, 4]} maxBarSize={46} onClick={(d) => onBarClick?.((d as unknown as DivergingDatum).label)} cursor={onBarClick ? "pointer" : "default"}>
          {data.map((d) => {
            const v = d.value ?? 0;
            let color = neutral;
            if (Math.abs(v) > 1e-9) {
              const positiveIsDry = dryIsPositive;
              const isDry = positiveIsDry ? v > 0 : v < 0;
              color = isDry ? dry : wet;
            }
            const isHi = highlightLabel == null || highlightLabel === d.label;
            return <Cell key={d.label} fill={color} opacity={isHi ? 1 : 0.36} stroke={highlightLabel === d.label ? ink : "none"} strokeWidth={1.4} />;
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
