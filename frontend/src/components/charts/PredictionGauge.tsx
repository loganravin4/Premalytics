import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { theme } from '../../styles/theme';

export interface PredictionGaugeProps {
  homePct: number;
  drawPct: number;
  awayPct: number;
  className?: string;
}

const row = (h: number, d: number, a: number) => [{ name: 'p', home: h, draw: d, away: a }];

function dotClass(dataKey: string): string {
  if (dataKey === 'home') return 'bg-[#00ff87]';
  if (dataKey === 'draw') return 'bg-[#ffd700]';
  return 'bg-[#ff4757]';
}

function GaugeTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { name: string; value: number; dataKey: string }[];
}) {
  if (!active || !payload?.length) return null;
  const order = ['home', 'draw', 'away'] as const;
  const labels: Record<string, string> = { home: 'Home win', draw: 'Draw', away: 'Away win' };
  const sorted = [...payload].sort(
    (a, b) =>
      order.indexOf(String(a.dataKey) as (typeof order)[number]) -
      order.indexOf(String(b.dataKey) as (typeof order)[number]),
  );
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs shadow-xl">
      {sorted.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-[var(--color-text)]">
          <span className={`h-2 w-2 rounded-full ${dotClass(String(p.dataKey))}`} />
          <span>{labels[String(p.dataKey)] ?? p.dataKey}</span>
          <span className="font-mono">{p.value}%</span>
        </p>
      ))}
    </div>
  );
}

/** Stacked horizontal bar for 1X2 probabilities (sums to 100) */
export function PredictionGauge({ homePct, drawPct, awayPct, className = '' }: PredictionGaugeProps) {
  const data = row(homePct, drawPct, awayPct);
  return (
    <div className={`h-14 w-full min-w-0 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 12, left: 12, bottom: 4 }}
          barCategoryGap={0}
        >
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis type="category" dataKey="name" hide width={0} />
          <Tooltip content={<GaugeTooltip />} cursor={{ fill: `${theme.colors.primary}18` }} />
          <Bar dataKey="home" stackId="stack" fill={theme.colors.green} isAnimationActive radius={[0, 0, 0, 0]} />
          <Bar dataKey="draw" stackId="stack" fill={theme.colors.yellow} isAnimationActive />
          <Bar dataKey="away" stackId="stack" fill={theme.colors.red} isAnimationActive radius={[0, 6, 6, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
