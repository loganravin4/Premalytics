/**
 * Reusable Framer Motion presets (variants + springs).
 * Import these in pages/components so animation timing stays consistent.
 */
import type { Transition, Variants } from 'framer-motion';

/** Fade + move up: use with `initial="hidden"` / `animate="show"` */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
};

/** Parent: orchestrates staggered children via `staggerChildren` */
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
};

/** Child: each list/grid item fades in slightly after the previous (paired with `staggerContainer`) */
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

/** Snappy spring for cards and small UI (hover, press) */
export const cardSpring: Transition = {
  type: 'spring',
  stiffness: 380,
  damping: 28,
};

/** Softer spring for larger moves */
export const softSpring: Transition = {
  type: 'spring',
  stiffness: 280,
  damping: 24,
};

/** W/D/L form dots: scale from small to full */
export const formDot: Variants = {
  hidden: { opacity: 0, scale: 0.4 },
  show: { opacity: 1, scale: 1 },
};

/** Optional full-page variant (not wired by default; use if you switch off `AnimatedOutlet` custom props) */
export const pageTransition: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};
