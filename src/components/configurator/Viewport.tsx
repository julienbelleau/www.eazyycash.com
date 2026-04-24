"use client";

import { Scene } from "@/components/scene/Scene";
import { useConfigurator } from "@/lib/store";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronsLeftRight,
  ChevronsRightLeft,
  Compass,
  Maximize,
  Pause,
  Play,
} from "lucide-react";
import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";

// Avoid hydration issues — Canvas is client only.
const ClientScene = dynamic(async () => ({ default: Scene }), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 grid place-items-center">
      <div className="flex flex-col items-center gap-3">
        <div className="size-10 rounded-full border-2 border-[var(--color-border-strong)] border-t-[var(--color-accent)] animate-spin" />
        <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-fg-dim)]">
          Loading scene
        </div>
      </div>
    </div>
  ),
});

export function Viewport() {
  const { openProgress, isAnimating } = useConfigurator((s) => ({
    openProgress: s.openProgress,
    isAnimating: s.isAnimating,
  }));
  const set = useConfigurator((s) => s.set);
  const direction = useRef(1);

  // Auto-cycle panels open/close when isAnimating.
  useEffect(() => {
    if (!isAnimating) return;
    const id = setInterval(() => {
      const current = useConfigurator.getState().openProgress;
      let next = current + direction.current * 0.018;
      if (next >= 1) {
        next = 1;
        direction.current = -1;
      } else if (next <= 0) {
        next = 0;
        direction.current = 1;
      }
      set("openProgress", next);
    }, 30);
    return () => clearInterval(id);
  }, [isAnimating, set]);

  return (
    <div className="relative h-full w-full rounded-xl overflow-hidden surface canvas-wrap">
      {/* Decorative grid + glow */}
      <div className="pointer-events-none absolute inset-0 grid-bg opacity-50" />
      <div className="pointer-events-none absolute -top-20 -right-20 size-80 rounded-full bg-[color-mix(in_oklch,var(--color-accent)_18%,transparent)] blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -left-20 size-80 rounded-full bg-[color-mix(in_oklch,oklch(0.5_0.18_250)_18%,transparent)] blur-3xl" />

      <ClientScene />

      {/* Top-left: live tag */}
      <motion.div
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        className="absolute top-4 left-4 glass rounded-full px-3 py-1.5 flex items-center gap-2"
      >
        <span className="dot" />
        <span className="text-[11px] uppercase tracking-[0.16em] text-[var(--color-fg-muted)]">
          Realtime 3D
        </span>
      </motion.div>

      {/* Top-right: orbit hint */}
      <motion.div
        initial={{ opacity: 0, x: 8 }}
        animate={{ opacity: 1, x: 0 }}
        className="absolute top-4 right-4 glass rounded-lg px-3 py-1.5 flex items-center gap-2 text-[11px] text-[var(--color-fg-muted)]"
      >
        <Compass className="size-3.5" /> Drag to orbit · Scroll to zoom
      </motion.div>

      {/* Bottom: animation control bar */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.4 }}
        className="absolute bottom-5 left-1/2 -translate-x-1/2 glass rounded-2xl px-3 py-2.5 flex items-center gap-3 min-w-[460px] max-w-[90%]"
      >
        <button
          onClick={() => set("openProgress", 0)}
          className="size-9 grid place-items-center rounded-lg btn-ghost"
          title="Close fully (deploy wall)"
        >
          <ChevronsRightLeft className="size-4" />
        </button>

        <button
          onClick={() => set("isAnimating", !isAnimating)}
          className="size-10 grid place-items-center rounded-xl btn-primary"
          title={isAnimating ? "Pause" : "Auto-cycle"}
        >
          <AnimatePresence mode="wait" initial={false}>
            {isAnimating ? (
              <motion.span
                key="pause"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.6, opacity: 0 }}
                transition={{ duration: 0.12 }}
              >
                <Pause className="size-4" />
              </motion.span>
            ) : (
              <motion.span
                key="play"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.6, opacity: 0 }}
                transition={{ duration: 0.12 }}
              >
                <Play className="size-4" />
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        <button
          onClick={() => set("openProgress", 1)}
          className="size-9 grid place-items-center rounded-lg btn-ghost"
          title="Open fully (stack)"
        >
          <ChevronsLeftRight className="size-4" />
        </button>

        <div className="flex-1 mx-2">
          <div className="flex items-baseline justify-between mb-1">
            <span className="text-[10px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)]">
              Wall State
            </span>
            <span className="font-mono text-[11px]">
              {Math.round(openProgress * 100)}%{" "}
              <span className="text-[var(--color-fg-dim)]">
                {openProgress < 0.05
                  ? "Closed"
                  : openProgress > 0.95
                    ? "Stacked"
                    : "Transit"}
              </span>
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.001}
            value={openProgress}
            onChange={(e) => {
              set("isAnimating", false);
              set("openProgress", parseFloat(e.target.value));
            }}
            className="w-full accent-[var(--color-accent)]"
          />
        </div>

        <button
          onClick={() => {
            const el = document.documentElement;
            if (!document.fullscreenElement) el.requestFullscreen?.();
            else document.exitFullscreen?.();
          }}
          className="size-9 grid place-items-center rounded-lg btn-ghost"
          title="Fullscreen"
        >
          <Maximize className="size-4" />
        </button>
      </motion.div>
    </div>
  );
}
