import { NavLink } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { LayoutDashboard, Table2, Users, LineChart, Trophy } from 'lucide-react';

const linkBase =
  'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--color-text-muted)] transition-colors duration-200 hover:text-[var(--color-text)]';

const linkActive =
  'bg-[#37003c]/40 text-[#f1f5f9] border border-[#37003c]/55 shadow-[0_0_24px_rgba(55,0,60,0.35)] backdrop-blur-md';

export interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const reduce = useReducedMotion();

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-white/[0.06] bg-white/[0.04] px-4 py-6 shadow-[inset_-1px_0_0_rgba(255,255,255,0.04)] backdrop-blur-2xl">
      <motion.div
        className="mb-8 flex items-center gap-2 px-2"
        initial={reduce ? false : { opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        <motion.span
          className="text-2xl leading-none"
          aria-hidden
          whileHover={reduce ? undefined : { rotate: [0, -12, 12, 0], scale: 1.08 }}
          transition={{ type: 'spring', stiffness: 300, damping: 16 }}
        >
          ⚽
        </motion.span>
        <div>
          <p className="text-lg font-bold tracking-tight text-[var(--color-text)]">Premalytics</p>
          <p className="text-xs text-[var(--color-text-muted)]">Premier League analytics</p>
        </div>
      </motion.div>
      <nav className="flex flex-1 flex-col gap-1" aria-label="Main">
        {(
          [
            { to: '/', end: true as boolean, icon: LayoutDashboard, label: 'Dashboard' },
            { to: '/teams', end: false, icon: Users, label: 'Teams' },
            { to: '/players', end: false, icon: Trophy, label: 'Players' },
            { to: '/predictions', end: false, icon: LineChart, label: 'Predictions' },
            { to: '/standings', end: false, icon: Table2, label: 'Standings' },
          ] as const
        ).map((item, i) => (
          <motion.div
            key={item.to}
            initial={reduce ? false : { opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: reduce ? 0 : 0.04 * i, duration: 0.3 }}
          >
            <NavLink
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `${linkBase} ${isActive ? linkActive : 'border border-transparent hover:border-white/[0.06] hover:bg-white/[0.04]'}`
              }
            >
              <item.icon className="h-4 w-4 shrink-0" aria-hidden />
              {item.label}
            </NavLink>
          </motion.div>
        ))}
      </nav>
      <p className="mt-auto px-2 pt-6 text-[10px] leading-relaxed text-[var(--color-text-muted)]">
        Powered by FBRef data
      </p>
    </aside>
  );
}
