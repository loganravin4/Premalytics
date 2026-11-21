import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Monitor, Moon, Sun } from 'lucide-react';

type Theme = 'system' | 'light' | 'dark';
const NEXT: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' };

function readTheme(): Theme {
  try {
    const t = localStorage.getItem('ng-theme');
    return t === 'light' || t === 'dark' ? t : 'system';
  } catch {
    return 'system';
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    const el = document.documentElement;
    if (theme === 'system') el.removeAttribute('data-theme');
    else el.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('ng-theme', theme);
    } catch {
      // Storage can be blocked (private mode); the theme still applies for this visit
    }
  }, [theme]);
  const Icon = theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor;
  return (
    <button
      type="button"
      onClick={() => setTheme(NEXT[theme])}
      className="inline-flex size-10 items-center justify-center text-ink-2 hover:text-ink active:translate-y-px"
      aria-label={`Color theme: ${theme}. Switch to ${NEXT[theme]}.`}
      title={`Theme: ${theme}`}
    >
      <Icon aria-hidden className="size-[18px]" />
    </button>
  );
}

const NAV = [
  { to: '/', label: 'Volume', end: true },
  { to: '/wc2026', label: 'Matches', end: false },
  { to: '/nations', label: 'Nations', end: false },
  { to: '/method', label: 'Method', end: false },
];

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:bg-paper focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="border-b-2 border-rule-strong">
        <div className="mx-auto flex max-w-[82rem] flex-wrap items-center justify-between gap-x-6 px-4 sm:px-8 lg:px-12">
          <NavLink to="/" className="condensed py-3 text-xl font-extrabold tracking-[0.01em] uppercase no-underline">
            Neutral <span className="text-spot">Ground</span>
          </NavLink>
          <nav aria-label="Main" className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `whitespace-nowrap border-b-2 px-2 py-3 text-[0.9375rem] font-semibold no-underline sm:px-3 ${
                    isActive ? 'border-spot text-spot' : 'border-transparent text-ink-2 hover:text-ink'
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="flex-1 overflow-x-clip">
        <Outlet />
      </main>
      <footer className="mt-24 border-t-2 border-rule-strong">
        <div className="mx-auto grid max-w-[82rem] gap-6 px-4 py-10 text-sm text-ink-2 sm:px-8 md:grid-cols-[1fr_1fr] lg:px-12">
          <p className="max-w-[52ch]">
            <span className="condensed font-extrabold uppercase text-ink">Neutral Ground</span> prices international
            matches before kickoff and keeps the record, misses included. Not betting advice. Not affiliated with FIFA or
            any confederation.
          </p>
          <p className="max-w-[52ch] md:justify-self-end">
            Match data: martj42 international results and FBref via soccerdata. Shot data: StatsBomb open data. Team
            codes are FIFA-style three-letter codes.
          </p>
        </div>
      </footer>
    </div>
  );
}

/** Page frame: running head naming the volume, then the content column. */
export function Page({ head, children }: { head?: ReactNode; children: ReactNode }) {
  return (
    <>
      {head && (
        <div className="border-b border-rule">
          <div className="running-head mx-auto flex max-w-[82rem] flex-wrap justify-between gap-x-6 gap-y-1 px-4 py-2.5 sm:px-8 lg:px-12">
            {head}
          </div>
        </div>
      )}
      <div className="mx-auto max-w-[82rem] px-4 sm:px-8 lg:px-12">{children}</div>
    </>
  );
}
