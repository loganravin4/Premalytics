/**
 * Wraps React Router’s `<Outlet />` with a short cross-fade + slide when the pathname changes.
 * `mode="wait"` runs exit on the old page before enter on the new one (avoids overlapping routes).
 * `key={location.pathname}` forces remount when navigating so enter/exit animations run.
 */
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Outlet, useLocation } from 'react-router-dom';

export function AnimatedOutlet() {
  const location = useLocation();
  const reduce = useReducedMotion();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduce ? undefined : { opacity: 0, y: -10 }}
        transition={{ duration: reduce ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
        className="flex min-h-0 w-full flex-1 flex-col"
      >
        <Outlet />
      </motion.div>
    </AnimatePresence>
  );
}
