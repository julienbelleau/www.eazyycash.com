"use client";

import { motion } from "framer-motion";
import { CloudCheck, FolderOpen, Layers3, Save, SquareKanban } from "lucide-react";
import { useConfigurator } from "@/lib/store";
import { saveProject } from "@/lib/storage";
import { useEffect, useState } from "react";

export function Navbar() {
  const project = useConfigurator((s) => s.project);
  const setUI = useConfigurator((s) => s.setUI);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Debounced auto-save
  useEffect(() => {
    const id = setTimeout(() => {
      saveProject(project);
      setSavedAt(Date.now());
    }, 800);
    return () => clearTimeout(id);
  }, [project]);

  const onManualSave = () => {
    saveProject(project);
    setSavedAt(Date.now());
  };

  return (
    <header className="relative z-20 border-b border-[var(--color-border)] glass">
      <div className="h-14 px-5 flex items-center gap-5">
        <div className="flex items-center gap-2.5">
          <motion.div
            initial={{ rotate: -8, scale: 0.9 }}
            animate={{ rotate: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 220, damping: 18 }}
            className="grid place-items-center size-8 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-2)] text-zinc-900 shadow-[0_6px_18px_-6px_color-mix(in_oklch,var(--color-accent)_60%,transparent)]"
          >
            <Layers3 className="size-4" strokeWidth={2.4} />
          </motion.div>
          <div className="leading-tight">
            <div className="text-[13px] font-semibold tracking-tight">
              Moderco <span className="text-[var(--color-fg-dim)]">Studio</span>
            </div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-fg-dim)]">
              Operable Partition Configurator
            </div>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-2 ml-3 px-3 h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/60">
          <SquareKanban className="size-3.5 text-[var(--color-fg-dim)]" />
          <div className="text-[12.5px] font-medium truncate max-w-[280px]">{project.name}</div>
          <span className="mx-1 text-[var(--color-fg-dim)]">·</span>
          <div className="text-[12px] text-[var(--color-fg-muted)] truncate max-w-[200px]">{project.client}</div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5 text-[11.5px] text-[var(--color-fg-muted)] mr-2">
            <CloudCheck className="size-3.5 text-[var(--color-positive)]" />
            <span>{savedAt ? `Saved ${formatRelative(savedAt)}` : "Auto-saved"}</span>
          </div>
          <button
            onClick={() => setUI("projectsManagerOpen", true)}
            className="btn-ghost h-9 px-3 rounded-lg flex items-center gap-1.5 text-[12.5px]"
          >
            <FolderOpen className="size-3.5" /> Projects
          </button>
          <button
            onClick={onManualSave}
            className="btn-primary h-9 px-3.5 rounded-lg flex items-center gap-1.5 text-[12.5px]"
          >
            <Save className="size-3.5" /> Save
          </button>
        </div>
      </div>
    </header>
  );
}

function formatRelative(ts: number) {
  const diff = Date.now() - ts;
  if (diff < 5000) return "just now";
  if (diff < 60000) return `${Math.round(diff / 1000)}s ago`;
  if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`;
  return new Date(ts).toLocaleTimeString();
}
