import { useState, type ReactNode } from 'react';
import raw from '../data/generated/penalties.json';
import { Page } from '../components/Layout';
import { pct } from '../lib/format';

interface Rate {
  n: number;
  goals: number;
  conversion: number;
  ci95: [number, number];
  share?: number;
  low_sample?: boolean;
}
interface ZoneCell extends Rate {
  zone: string;
  row: 'high' | 'mid' | 'low';
  col: 'left' | 'center' | 'right';
  saved: number;
  missed: number;
}
interface Scope {
  n_kicks: number;
  overall: Rate;
  by_phase: (Rate & { phase: string })[];
  zones: { cells: ZoneCell[][] };
  on_target_rate: number;
  save_rate_on_target: number;
  foot_x_side: (Rate & { taker_foot: string; foot_side: string })[];
  shootout_order: (Rate & { order_bucket: string })[];
  shootout_pressure: (Rate & { shootout_pressure: string })[];
  in_game_state: (Rate & { game_state: string })[];
  shootouts: { n_shootouts: number; first_kicker_won: number; first_kicker_win_rate: number; ci95: [number, number] };
}
interface PenaltyData {
  label: string;
  min_display_n: number;
  scopes: Record<'mens' | 'all', Scope>;
  model_check: { constant_log_loss: number; best_other: [string, number]; any_beats_constant: boolean; n_scored_kicks: number };
}

const data = raw as unknown as PenaltyData;
type ScopeId = 'mens' | 'all';

const PHASE: Record<string, string> = { in_game: 'During a match', shootout: 'In a shootout' };
const SIDE: Record<string, string> = { natural: 'Natural side', across: 'Across the body', center: 'Down the middle' };
const PRESSURE: Record<string, string> = {
  can_win: 'Scoring wins the shootout',
  must_score: 'Missing loses the shootout',
  neutral: 'Neither',
};
const STATE: Record<string, string> = { leading: 'Taker’s team leading', level: 'Level', trailing: 'Taker’s team trailing' };

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap border-b border-rule">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          onClick={() => onChange(o.id)}
          className={`-mb-px border-b-2 px-3 py-2.5 text-[0.9375rem] font-semibold first:pl-0 ${
            value === o.id ? 'border-spot text-spot' : 'border-transparent text-ink-2 hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** The 95% interval drawn on a fixed 40–100% scale, so rows compare at a glance. */
function Interval({ r }: { r: Rate }) {
  const at = (v: number) => `${((Math.max(0.4, v) - 0.4) / 0.6) * 100}%`;
  return (
    <span className="relative block h-3 w-full min-w-24" aria-hidden>
      <span className="absolute inset-x-0 top-1/2 h-px bg-rule" />
      <span
        className="absolute top-1/2 h-[3px] -translate-y-1/2 bg-tint-away"
        style={{ left: at(r.ci95[0]), width: `calc(${at(r.ci95[1])} - ${at(r.ci95[0])})` }}
      />
      <span
        className={`absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 ${r.low_sample ? 'border-2 border-spot bg-paper' : 'bg-spot'}`}
        style={{ left: at(r.conversion) }}
      />
    </span>
  );
}

function RateTable({ caption, rows }: { caption: string; rows: { label: string; r: Rate }[] }) {
  return (
    <table className="w-full border-collapse text-[0.9375rem]">
      <caption className="running-head mb-2 text-left">{caption}</caption>
      <thead>
        <tr className="running-head border-b-2 border-rule-strong text-left">
          <th className="py-2 font-normal">Situation</th>
          <th className="py-2 pl-3 text-right font-normal">Kicks</th>
          <th className="py-2 pl-3 text-right font-normal">Scored</th>
          <th className="hidden w-[40%] py-2 pl-5 font-normal sm:table-cell">95% interval, 40–100%</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, r }) => (
          <tr key={label} className="border-b border-rule">
            <td className="py-2.5 pr-2">
              {label}
              {r.low_sample && <span className="ml-2 text-xs text-muted">few kicks</span>}
            </td>
            <td className="py-2.5 pl-3 text-right">{r.n}</td>
            <td className={`py-2.5 pl-3 text-right ${r.low_sample ? 'text-ink-2' : 'font-bold'}`}>
              {pct(r.conversion)}
              <span className="sr-only">
                , 95% interval {pct(r.ci95[0])} to {pct(r.ci95[1])}
              </span>
            </td>
            <td className="hidden py-2.5 pl-5 sm:table-cell">
              <Interval r={r} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Capped at 55% spot so ink text stays readable on every cell in both themes
const shareFill = (share: number) =>
  `color-mix(in oklab, var(--spot) ${Math.round(Math.min(1, share / 0.3) * 55)}%, var(--paper))`;

function GoalMouth({ scope }: { scope: Scope }) {
  return (
    <figure>
      <div className="relative mx-auto w-full max-w-[40rem]">
        <div className="border-x-[6px] border-t-[6px] border-ink">
          <div className="grid aspect-[2/1] grid-cols-3 grid-rows-3 gap-px bg-rule sm:aspect-[3/1]">
            {scope.zones.cells.flat().map((c) => {
              return (
                <div
                  key={c.zone}
                  className="flex flex-col items-center justify-center p-1 text-center"
                  style={{ background: shareFill(c.share ?? 0) }}
                  aria-label={`${c.row} ${c.col}: ${c.n} kicks, ${pct(c.share ?? 0)} of all, ${pct(c.conversion)} scored${
                    c.low_sample ? ', few kicks' : ''
                  }`}
                  role="img"
                >
                  <span
                    className={`condensed text-[clamp(1.1rem,4vw,2rem)] leading-none font-extrabold ${
                      c.low_sample ? 'text-ink-2' : 'text-ink'
                    }`}
                  >
                    {pct(c.conversion)}
                  </span>
                  <span className="mt-1 text-[0.6875rem] text-ink sm:text-xs">
                    {c.n} kicks{c.low_sample ? ' · few' : ''}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="h-px bg-ink" aria-hidden />
      </div>
      <figcaption className="mx-auto mt-4 flex max-w-[40rem] flex-wrap items-center justify-between gap-3 text-sm text-ink-2">
        <span>Seen from behind the taker. Number: share scored. Shade: how often kicks went there.</span>
        <span className="flex items-center gap-1.5 text-xs text-muted" aria-hidden>
          fewer
          {[0.03, 0.1, 0.2, 0.3].map((s) => (
            <span key={s} className="block h-3 w-6 border border-rule" style={{ background: shareFill(s) }} />
          ))}
          more
        </span>
      </figcaption>
    </figure>
  );
}

function Section({ title, lede, children }: { title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-24 grid gap-8 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-16">
      <div>
        <h2 className="condensed balance text-[2rem] leading-[1.05] font-extrabold">{title}</h2>
        {lede && <div className="mt-3 max-w-[40ch] text-ink-2">{lede}</div>}
      </div>
      <div className="min-w-0 space-y-10">{children}</div>
    </section>
  );
}

export function PenaltyLab() {
  const [scopeId, setScopeId] = useState<ScopeId>('mens');
  const s = data.scopes[scopeId];
  const who = scopeId === 'mens' ? 'men’s' : 'men’s and women’s';
  const mc = data.model_check;

  return (
    <Page
      head={
        <>
          <span>Lab · Penalties</span>
          <span>Experimental: past kicks described, not predicted</span>
        </>
      }
    >
      <h1 className="condensed mt-10 text-[clamp(2.5rem,7vw,4.5rem)] leading-none font-extrabold">Penalties</h1>
      <p className="mt-4 max-w-[60ch] text-ink-2">
        Every penalty in the international tournaments StatsBomb has published, nearly all from 2018 to 2025: where
        takers put the ball and how often it went in. Nothing here predicts the next kick.
      </p>
      <div className="mt-8">
        <Segmented
          label="Which kicks"
          value={scopeId}
          onChange={setScopeId}
          options={[
            { id: 'mens' as const, label: `Men’s (${data.scopes.mens.n_kicks})` },
            { id: 'all' as const, label: `Men’s and women’s (${data.scopes.all.n_kicks})` },
          ]}
        />
      </div>

      <section className="grid gap-12 pt-12 lg:grid-cols-[5fr_7fr] lg:items-center lg:gap-16">
        <div>
          <p className="display text-[clamp(5rem,16vw,10rem)]" aria-hidden>
            {Math.round(s.overall.conversion * 100)}
            <span className="text-spot">%</span>
          </p>
          <p className="sr-only">{pct(s.overall.conversion)} scored</p>
          <p className="balance mt-6 max-w-[32ch] text-[1.3125rem] leading-snug">
            of {s.overall.n} {who} tournament penalties were scored.
          </p>
          <p className="mt-4 max-w-[46ch] text-ink-2">
            95% interval {pct(s.overall.ci95[0])}–{pct(s.overall.ci95[1])}. {pct(s.on_target_rate)} were on target, and
            keepers saved {pct(s.save_rate_on_target)} of those.
          </p>
        </div>
        <GoalMouth scope={s} />
      </section>

      <Section
        title="When it was taken"
        lede="Every interval overlaps. With a few hundred kicks, none of these gaps is clearly real."
      >
        <RateTable caption="Match or shootout" rows={s.by_phase.map((r) => ({ label: PHASE[r.phase] ?? r.phase, r }))} />
        <RateTable
          caption="Score during the match"
          rows={s.in_game_state.map((r) => ({ label: STATE[r.game_state] ?? r.game_state, r }))}
        />
      </Section>

      <Section title="In a shootout" lede="Kick order and what was riding on it.">
        <RateTable
          caption="Kick number"
          rows={s.shootout_order.map((r) => ({ label: `Kick ${r.order_bucket}`, r }))}
        />
        <RateTable
          caption="Pressure"
          rows={s.shootout_pressure.map((r) => ({ label: PRESSURE[r.shootout_pressure] ?? r.shootout_pressure, r }))}
        />
        <p className="max-w-[60ch] text-[0.9375rem] text-ink-2">
          The team kicking first won {s.shootouts.first_kicker_won} of {s.shootouts.n_shootouts} shootouts (
          {pct(s.shootouts.first_kicker_win_rate)}, 95% interval {pct(s.shootouts.ci95[0])}–{pct(s.shootouts.ci95[1])}).
        </p>
      </Section>

      <Section title="Which foot, which side" lede="Natural side means a right-footer shooting to their left, and the reverse.">
        <RateTable
          caption="Taker’s foot and placement"
          rows={s.foot_x_side.map((r) => ({
            label: `${r.taker_foot === 'left' ? 'Left' : 'Right'} foot, ${(SIDE[r.foot_side] ?? r.foot_side).toLowerCase()}`,
            r,
          }))}
        />
      </Section>

      <Section title="Can anything predict a penalty?">
        <div className="max-w-[60ch] space-y-4">
          <p className="condensed text-[2.5rem] leading-none font-extrabold">Not yet.</p>
          <p className="text-ink-2">
            Each tournament was scored with rates learned only from earlier tournaments ({mc.n_scored_kicks} kicks). No
            pre-kick fact (match or shootout, foot, kick order, pressure, score) beat simply using the overall scoring
            rate. The best, match versus shootout, improved log loss from {mc.constant_log_loss.toFixed(4)} to{' '}
            {mc.best_other[1].toFixed(4)}, well within noise.
          </p>
          <p className="text-sm text-muted">
            {data.label} Rows with fewer than {data.min_display_n} kicks are marked “few kicks”. Dive direction isn’t in
            the data. Source: StatsBomb open data.
          </p>
        </div>
      </Section>
    </Page>
  );
}
