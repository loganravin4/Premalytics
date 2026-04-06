import type { Transition, Variants } from 'framer-motion';

/** Page / section entrance */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
};

/** Stagger list children */
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

/** Card hover spring */
export const cardSpring: Transition = {
  type: 'spring',
  stiffness: 380,
  damping: 28,
};

export const softSpring: Transition = {
  type: 'spring',
  stiffness: 280,
  damping: 24,
};

/** Form dots pop-in */
export const formDot: Variants = {
  hidden: { opacity: 0, scale: 0.4 },
  show: { opacity: 1, scale: 1 },
};

export const pageTransition: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};
