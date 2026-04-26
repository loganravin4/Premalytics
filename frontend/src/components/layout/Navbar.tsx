import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Menu, X } from 'lucide-react';
import { Sidebar } from './Sidebar';

export function Navbar() {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();

  return (
    <>
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-white/[0.08] bg-white/[0.04] px-4 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.35)] backdrop-blur-2xl lg:hidden">
        <motion.div
          className="flex items-center gap-2"
          initial={reduce ? false : { opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <motion.span
            className="text-xl leading-none"
            aria-hidden
            whileTap={reduce ? undefined : { scale: 0.92 }}
          >
            ⚽
          </motion.span>
          <span className="text-base font-bold tracking-tight text-[var(--color-text)]">Premalytics</span>
        </motion.div>
        <motion.button
          type="button"
          className="rounded-xl border border-white/[0.1] bg-white/[0.05] p-2 text-[var(--color-text)] shadow-inner backdrop-blur-md transition-colors duration-200 hover:border-[#37003c]/50"
          aria-expanded={open}
          aria-controls="mobile-nav-drawer"
          onClick={() => setOpen((v) => !v)}
          whileTap={reduce ? undefined : { scale: 0.95 }}
        >
          {open ? <X className="h-5 w-5" aria-hidden /> : <Menu className="h-5 w-5" aria-hidden />}
          <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
        </motion.button>
      </header>
      <AnimatePresence>
        {open ? (
          <motion.div
            className="fixed inset-0 z-50 flex lg:hidden"
            id="mobile-nav-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.button
              type="button"
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              aria-label="Close menu"
              onClick={() => setOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
            <motion.div
              className="relative z-10 h-full w-[min(280px,85vw)] border-r border-white/[0.08] bg-[var(--color-background)]/95 shadow-2xl backdrop-blur-2xl"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 400, damping: 38 }}
            >
              <Sidebar onNavigate={() => setOpen(false)} />
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
