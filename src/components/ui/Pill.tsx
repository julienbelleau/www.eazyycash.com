"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { ReactNode } from "react";

interface PillProps {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  title?: string;
  disabled?: boolean;
}

export function Pill({ active, onClick, children, className, title, disabled }: PillProps) {
  return (
    <motion.button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      whileTap={{ scale: 0.97 }}
      className={cn(
        "relative h-8 px-3 rounded-lg text-[12px] font-medium border transition-all",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        active
          ? "bg-gradient-to-b from-[var(--color-accent)] to-[var(--color-accent-2)] text-zinc-900 border-transparent shadow-[0_4px_16px_-6px_color-mix(in_oklch,var(--color-accent)_60%,transparent)]"
          : "bg-[var(--color-surface)]/60 border-[var(--color-border)] text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] hover:border-[var(--color-border-strong)]",
        className,
      )}
    >
      {children}
    </motion.button>
  );
}
