import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { MonthlyGoals } from '../../types/team';
import { theme } from '../../styles/theme';

export interface GoalsChartProps {
  data: MonthlyGoals[];
  className?: string;
}

interface TooltipPayload {
  month: string;
  goals: number;
}

function GoalsTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: TooltipPayload }[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold text-[var(--color-text)]">{row.month}</p>
      <p className="text-[var(--color-text-muted)]">Goals: {row.goals}</p>
    </div>
  );
}

export function GoalsChart({ data, className = '' }: GoalsChartProps) {
  return (
    <div className={`h-64 w-full min-w-0 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={theme.colors.chartGrid} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="month"
            tick={{ fill: theme.colors.chartAxis, fontSize: 11 }}
            axisLine={{ stroke: theme.colors.border }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: theme.colors.chartAxis, fontSize: 11 }}
            axisLine={{ stroke: theme.colors.border }}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<GoalsTooltip />} cursor={{ fill: `${theme.colors.primary}22` }} />
          <Bar dataKey="goals" fill={theme.colors.green} radius={[6, 6, 0, 0]} name="Goals" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
