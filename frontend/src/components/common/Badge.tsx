import type { ReactNode } from 'react';

export type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'primary';

export interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantClass: Record<BadgeVariant, string> = {
  default: 'bg-white/[0.06] text-[var(--color-text)] border-white/[0.08] backdrop-blur-md',
  success: 'bg-[#00ff87]/12 text-[#00ff87] border-[#00ff87]/35 backdrop-blur-md',
  warning: 'bg-[#ffd700]/12 text-[#ffd700] border-[#ffd700]/35 backdrop-blur-md',
  danger: 'bg-[#ff4757]/12 text-[#ff4757] border-[#ff4757]/35 backdrop-blur-md',
  primary: 'bg-[#37003c]/45 text-[#f1f5f9] border-[#37003c]/60 backdrop-blur-md shadow-[0_0_20px_rgba(55,0,60,0.25)]',
};

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-lg border px-2 py-0.5 text-xs font-semibold tracking-wide ${variantClass[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
