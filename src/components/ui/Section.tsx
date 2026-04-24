"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface SectionProps {
  title: string;
  hint?: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  delay?: number;
}

export function Section({ title, hint, icon, children, className, delay = 0 }: SectionProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: "easeOut" }}
      className={cn("space-y-3", className)}
    >
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon && (
            <span className="grid place-items-center size-6 rounded-md bg-[var(--color-surface-2)] text-[var(--color-fg-muted)]">
              {icon}
            </span>
          )}
          <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--color-fg-muted)]">
            {title}
          </h3>
        </div>
        {hint && (
          <span className="text-[11px] text-[var(--color-fg-dim)]">{hint}</span>
        )}
      </header>
      <div>{children}</div>
    </motion.section>
  );
}
