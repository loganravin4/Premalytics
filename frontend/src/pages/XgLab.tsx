import { useCallback, useMemo, useRef, useState } from 'react';
import raw from '../data/generated/xg-lab.json';
import { Page } from '../components/Layout';

type BodyPart = 'right_foot' | 'left_foot' | 'head';
type Situation = 'open_play' | 'set_piece' | 'counter';

interface XgLabData {
  label: string;
  pitch: {
    cell_size_yd: number;
    x: number[];
    y: number[];
    values: Record<BodyPart, Record<Situation, (number | null)[][]>>;
  };
  metrics: {
    grid_xg_eval: { n: number; brier_score: number; log_loss: number; roc_auc: number };
    production_model_eval: { headline: { brier_score: number; log_loss: number; roc_auc: number } };
  };
}

const data = raw as unknown as XgLabData;
const { pitch } = data;

const BODY: { id: BodyPart; label: string }[] = [
  { id: 'right_foot', label: 'Right foot' },
  { id: 'left_foot', label: 'Left foot' },
  { id: 'head', label: 'Header' },
];
const SITUATION: { id: Situation; label: string }[] = [
  { id: 'open_play', label: 'Open play' },
  { id: 'set_piece', label: 'Set piece' },
  { id: 'counter', label: 'Counter' },
];

// StatsBomb yards: attacking toward x=120, goal centered on y=40
const PRESETS: { label: string; x: number; y: number }[] = [
  { label: 'Six-yard box, center', x: 116, y: 40 },
  { label: 'Penalty spot distance', x: 108, y: 40 },
  { label: 'Edge of the box', x: 101, y: 40 },
  { label: 'Tight angle', x: 116, y: 24 },
  { label: 'Thirty yards out', x: 90, y: 40 },
];

// Classed steps read more honestly than a smooth ramp when most of the pitch sits below 0.05
const BINS: { max: number; mix: number; label: string }[] = [
  { max: 0.02, mix: 0, label: '< 0.02' },
  { max: 0.05, mix: 14, label: '0.02' },
  { max: 0.1, mix: 28, label: '0.05' },
  { max: 0.2, mix: 44, label: '0.10' },
  { max: 0.35, mix: 62, label: '0.20' },
  { max: 0.5, mix: 80, label: '0.35' },
  { max: Infinity, mix: 100, label: '0.50+' },
];
const fill = (p: number | null) => {
  if (p == null) return 'transparent';
  const mix = BINS.find((b) => p < b.max)!.mix;
  return mix === 0 ? 'transparent' : `color-mix(in oklab, var(--spot) ${mix}%, var(--paper))`;
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const cellIndex = (v: number, axis: number[]) =>
  clamp(Math.round((v - axis[0]) / pitch.cell_size_yd), 0, axis.length - 1);

function oneIn(p: number) {
  if (p >= 0.5) return `About ${Math.round(p * 10)} in 10 shots like this are scored.`;
  return `About 1 in ${Math.max(2, Math.round(1 / p))} shots like this is scored.`;
}

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

// Goal at the top: screen x is StatsBomb y, screen y runs from the goal line (x=120) down to halfway (x=60)
const sx = (y: number) => y;
const sy = (x: number) => 120 - x;

function PitchLines() {
  return (
    <g fill="none" stroke="var(--ink)" strokeWidth={0.35} vectorEffect="non-scaling-stroke" pointerEvents="none">
      <rect x={0} y={0} width={80} height={60} />
      <rect x={sx(18)} y={0} width={44} height={18} />
      <rect x={sx(30)} y={0} width={20} height={6} />
      <path d={`M ${sx(32)} ${sy(102)} A 10 10 0 0 0 ${sx(48)} ${sy(102)}`} />
      <path d={`M ${sx(30)} 60 A 10 10 0 0 1 ${sx(50)} 60`} />
      <circle cx={sx(40)} cy={sy(108)} r={0.4} fill="var(--ink)" />
      <rect x={sx(36)} y={-2.4} width={8} height={2.4} strokeWidth={0.6} />
    </g>
  );
}

export function XgLab() {
  const [body, setBody] = useState<BodyPart>('right_foot');
  const [situation, setSituation] = useState<Situation>('open_play');
  const [pos, setPos] = useState({ x: 108, y: 40 });
  const svgRef = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);

  const grid = pitch.values[body][situation];
  const xi = cellIndex(pos.x, pitch.x);
  const yi = cellIndex(pos.y, pitch.y);
  const p = grid[xi][yi];
  const dx = 120 - pos.x, dy = 40 - pos.y;
  const distanceM = Math.hypot(dx, dy) * 0.9144;
  const angleDeg = (Math.atan2(Math.abs(dy), dx) * 180) / Math.PI;

  const cells = useMemo(
    () =>
      pitch.x.flatMap((x, i) =>
        pitch.y.map((y, j) => ({ key: `${i}-${j}`, x, y, color: fill(grid[i][j]) })),
      ),
    [grid],
  );

  const moveTo = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return;
    const pt = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    setPos({ x: clamp(120 - pt.y, 60, 120), y: clamp(pt.x, 0, 80) });
  }, []);

  const onKey = (e: React.KeyboardEvent) => {
    const step = (e.shiftKey ? 5 : 1) * pitch.cell_size_yd;
    const moves: Record<string, [number, number]> = {
      ArrowUp: [step, 0],
      ArrowDown: [-step, 0],
      ArrowLeft: [0, -step],
      ArrowRight: [0, step],
    };
    const m = moves[e.key];
    if (!m) return;
    e.preventDefault();
    setPos((s) => ({ x: clamp(s.x + m[0], 60, 120), y: clamp(s.y + m[1], 0, 80) }));
  };

  const readout =
    p == null
      ? 'No estimate here.'
      : `${p.toFixed(2)} xG from ${distanceM.toFixed(1)} meters at ${Math.round(angleDeg)} degrees.`;
  const gridEval = data.metrics.grid_xg_eval;
  const fullEval = data.metrics.production_model_eval.headline;

  return (
    <Page
      head={
        <>
          <span>Lab · Shot xG</span>
          <span>{data.label}</span>
        </>
      }
    >
      <h1 className="condensed mt-10 text-[clamp(2.5rem,7vw,4.5rem)] leading-none font-extrabold">xG lab</h1>
      <p className="mt-4 max-w-[60ch] text-ink-2">
        Pick a spot on the pitch to see how often a shot from there is scored, according to a model trained on 9,868
        shots from 16 international tournaments. Penalties are not included.
      </p>

      <div className="mt-10 grid gap-10 lg:grid-cols-[7fr_5fr] lg:gap-16">
        <figure className="min-w-0">
          <svg
            ref={svgRef}
            viewBox="-1 -4 82 65"
            className="block w-full cursor-crosshair touch-none select-none outline-none focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--focus)]"
            role="application"
            aria-roledescription="shot position picker"
            aria-label={`Shot position. ${readout} Use the arrow keys to move the shot; hold Shift for bigger steps.`}
            tabIndex={0}
            onKeyDown={onKey}
            onPointerDown={(e) => {
              dragging.current = true;
              e.currentTarget.setPointerCapture(e.pointerId);
              moveTo(e.clientX, e.clientY);
            }}
            onPointerMove={(e) => {
              if (dragging.current) moveTo(e.clientX, e.clientY);
            }}
            onPointerUp={() => {
              dragging.current = false;
            }}
            onPointerCancel={() => {
              dragging.current = false;
            }}
          >
            <g shapeRendering="crispEdges">
              {cells.map((c) => (
                <rect
                  key={c.key}
                  x={sx(c.y) - pitch.cell_size_yd / 2}
                  y={sy(c.x) - pitch.cell_size_yd / 2}
                  width={pitch.cell_size_yd}
                  height={pitch.cell_size_yd}
                  fill={c.color}
                />
              ))}
            </g>
            <PitchLines />
            <g pointerEvents="none">
              <line x1={sx(pos.y)} y1={sy(pos.x)} x2={sx(36)} y2={0} stroke="var(--ink)" strokeWidth={0.25} strokeDasharray="0.8 0.8" />
              <line x1={sx(pos.y)} y1={sy(pos.x)} x2={sx(44)} y2={0} stroke="var(--ink)" strokeWidth={0.25} strokeDasharray="0.8 0.8" />
              <circle cx={sx(pos.y)} cy={sy(pos.x)} r={1.6} fill="var(--paper)" stroke="var(--ink)" strokeWidth={0.6} />
              <circle cx={sx(pos.y)} cy={sy(pos.x)} r={0.5} fill="var(--ink)" />
            </g>
          </svg>
          <figcaption className="mt-4">
            <div className="flex items-center gap-2 text-xs text-muted" aria-hidden>
              <span className="running-head mr-2">xG</span>
              {BINS.map((b) => (
                <span key={b.label} className="flex flex-col items-center gap-1">
                  <span
                    className="block h-3 w-8 border border-rule"
                    style={{ background: b.mix ? `color-mix(in oklab, var(--spot) ${b.mix}%, var(--paper))` : 'var(--paper)' }}
                  />
                  {b.label}
                </span>
              ))}
            </div>
            <p className="mt-3 text-sm text-ink-2">
              Click or drag on the pitch, or focus it and use the arrow keys. Each square is 2 × 2 yards.
            </p>
          </figcaption>
        </figure>

        <div>
          <p className="running-head">Chance of scoring</p>
          <p className="display mt-2 text-[clamp(4.5rem,14vw,9rem)]" aria-live="polite">
            {p == null ? '—' : p.toFixed(2)}
            <span className="ml-3 text-[0.35em] text-muted">xG</span>
          </p>
          <p className="balance mt-5 max-w-[30ch] text-[1.3125rem] leading-snug">{p == null ? 'No estimate here.' : oneIn(p)}</p>

          <dl className="mt-6 grid grid-cols-2 border-y-2 border-rule-strong text-[0.9375rem]">
            <div className="border-r border-rule py-3 pr-3">
              <dt className="running-head">Distance to goal</dt>
              <dd className="mt-1 font-bold">{distanceM.toFixed(1)} m</dd>
            </div>
            <div className="py-3 pl-4">
              <dt className="running-head">Angle off center</dt>
              <dd className="mt-1 font-bold">{Math.round(angleDeg)}°</dd>
            </div>
          </dl>

          <div className="mt-8 space-y-5">
            <Segmented label="Body part" options={BODY} value={body} onChange={setBody} />
            <Segmented label="Situation" options={SITUATION} value={situation} onChange={setSituation} />
          </div>

          <div className="mt-8">
            <p className="running-head mb-2">Try a shot</p>
            <ul className="border-t border-rule">
              {PRESETS.map((s) => {
                const active = pos.x === s.x && pos.y === s.y;
                return (
                  <li key={s.label} className="border-b border-rule">
                    <button
                      type="button"
                      onClick={() => setPos({ x: s.x, y: s.y })}
                      aria-pressed={active}
                      className={`flex w-full items-center justify-between py-2.5 text-left text-[0.9375rem] hover:bg-paper-2 ${
                        active ? 'font-semibold text-spot' : ''
                      }`}
                    >
                      {s.label}
                      <span className="pr-1 text-muted">
                        {(grid[cellIndex(s.x, pitch.x)][cellIndex(s.y, pitch.y)] ?? 0).toFixed(2)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>

      <section className="mt-24 grid gap-8 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-16">
        <h2 className="condensed text-[2rem] leading-[1.05] font-extrabold">What this is</h2>
        <div className="max-w-[60ch] space-y-4 text-ink-2">
          <p>
            A logistic model that only knows where the shot was taken, the body part, and how the attack started. The
            site's full xG model also sees defenders between the ball and goal and where the keeper stood, which this
            page can't ask you for.
          </p>
          <table className="w-full max-w-[36rem] border-collapse text-[0.9375rem] text-ink">
            <caption className="running-head mb-2 text-left">
              Tested on {gridEval.n.toLocaleString('en-US')} shots from Euro 2024 and Copa América 2024
            </caption>
            <thead>
              <tr className="running-head border-b-2 border-rule-strong text-left">
                <th className="py-2 font-normal">Model</th>
                <th className="py-2 pl-4 text-right font-normal">Log loss</th>
                <th className="py-2 pl-4 text-right font-normal">Brier</th>
                <th className="py-2 pl-4 text-right font-normal">AUC</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-rule font-bold">
                <td className="py-2.5">This page (location, body part, situation)</td>
                <td className="py-2.5 pl-4 text-right">{gridEval.log_loss.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right">{gridEval.brier_score.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right">{gridEval.roc_auc.toFixed(3)}</td>
              </tr>
              <tr className="border-b border-rule">
                <td className="py-2.5">Full model (adds defenders and keeper)</td>
                <td className="py-2.5 pl-4 text-right">{fullEval.log_loss.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right">{fullEval.brier_score.toFixed(3)}</td>
                <td className="py-2.5 pl-4 text-right">{fullEval.roc_auc.toFixed(3)}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-sm">{data.label}. Shot data: StatsBomb open data.</p>
        </div>
      </section>
    </Page>
  );
}
