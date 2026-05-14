import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import type { FormResult } from '../../types/team';

export interface FormChartProps {
  results: FormResult[];
  maxVisible?: number;
  className?: string;
}

const dotClass: Record<FormResult, string> = {
  W: 'bg-[#00ff87] shadow-[0_0_10px_#00ff8799]',
  D: 'bg-[#ffd700] shadow-[0_0_10px_#ffd70055]',
  L: 'bg-[#ff4757] shadow-[0_0_10px_#ff475799]',
};

export function FormChart({ results, maxVisible = 5, className = '' }: FormChartProps) {
  const slice = results.slice(-maxVisible);
  const reduce = useReducedMotion();

  const containerVariants = useMemo(
    () => ({
      hidden: { opacity: 0 },
      show: {
        opacity: 1,
        transition: { staggerChildren: reduce ? 0 : 0.05 },
      },
    }),
    [reduce],
  );

  const itemVariants = useMemo(
    () => ({
      hidden: { opacity: 0, scale: 0.5, y: 4 },
      show: { opacity: 1, scale: 1, y: 0 },
    }),
    [],
  );

  return (
    <motion.div
      className={`flex flex-wrap items-center gap-1.5 ${className}`}
      role="list"
      aria-label="Recent form"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {slice.map((r, i) => (
        <motion.span
          key={`${r}-${i}`}
          role="listitem"
          title={r === 'W' ? 'Win' : r === 'D' ? 'Draw' : 'Loss'}
          variants={itemVariants}
          whileHover={reduce ? undefined : { scale: 1.15, y: -2 }}
          transition={{ type: 'spring', stiffness: 500, damping: 22 }}
          className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold text-[#0a0e1a] ${dotClass[r]}`}
        >
          {r}
        </motion.span>
      ))}
    </motion.div>
  );
}
