"use client";

import { useConfigurator, getActiveWall } from "@/lib/store";
import {
  FAMILIES,
  FAMILY_LIST,
  MODELS,
  MODELS_BY_FAMILY,
  STACK_TYPES,
} from "@/lib/moderco";
import { Section } from "@/components/ui/Section";
import { Slider } from "@/components/ui/Slider";
import { Pill } from "@/components/ui/Pill";
import { Switch } from "@/components/ui/Switch";
import {
  Box,
  Boxes,
  Cog,
  Eye,
  Layers,
  Maximize2,
  Move3d,
  Palette,
  Ruler,
  Settings2,
  Volume2,
  Wand2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { ProjectPanel } from "./ProjectPanel";

export function ConfigSidebar() {
  const state = useConfigurator();
  const wall = getActiveWall(state);
  const model = MODELS[wall.modelId];
  const family = FAMILIES[model.family];

  const [tab, setTab] = useState<"project" | "wall">("project");

  return (
    <aside className="surface flex flex-col rounded-xl overflow-hidden h-full max-h-[80vh] lg:max-h-none">
      {/* Tabs */}
      <div className="px-3 pt-3 border-b border-[var(--color-border)]">
        <div className="flex bg-[var(--color-bg-2)] rounded-lg p-1">
          {(["project", "wall"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 h-8 rounded-md text-[12px] font-medium transition-all ${
                tab === t
                  ? "bg-[var(--color-surface-2)] text-[var(--color-fg)] shadow-sm"
                  : "text-[var(--color-fg-dim)] hover:text-[var(--color-fg-muted)]"
              }`}
            >
              {t === "project" ? "Project" : "Active Wall"}
            </button>
          ))}
        </div>
        <div className="px-1 py-2.5 text-[10px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)] truncate">
          {tab === "project"
            ? `${state.project.walls.length} wall${state.project.walls.length === 1 ? "" : "s"}`
            : `${wall.name} · ${model.name}`}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <AnimatePresence mode="wait">
          {tab === "project" ? (
            <motion.div
              key="project"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              transition={{ duration: 0.15 }}
            >
              <ProjectPanel />
            </motion.div>
          ) : (
            <motion.div
              key="wall"
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              className="space-y-7"
            >
              {/* Family */}
              <Section title="Product Family" icon={<Boxes className="size-3.5" />} hint={family.name}>
                <div className="grid grid-cols-2 gap-2">
                  {FAMILY_LIST.map((f) => (
                    <motion.button
                      key={f.id}
                      type="button"
                      onClick={() => {
                        const first = MODELS_BY_FAMILY[f.id][0];
                        state.updateActiveWall("modelId", first.id);
                        state.updateActiveWall("finish", first.finishes[0]);
                        state.updateActiveWall("trackOption", first.trackOptions[0]);
                        state.updateActiveWall("sealOption", first.sealOptions[0]);
                      }}
                      whileHover={{ y: -2 }}
                      whileTap={{ scale: 0.98 }}
                      className={`relative rounded-lg border text-left p-2.5 transition-all ${
                        model.family === f.id
                          ? "border-[var(--color-accent)] bg-[color-mix(in_oklch,var(--color-accent)_8%,transparent)]"
                          : "border-[var(--color-border)] bg-[var(--color-surface)]/60 hover:border-[var(--color-border-strong)]"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span
                          className="size-2 rounded-full"
                          style={{ background: f.accent, boxShadow: `0 0 8px ${f.accent}` }}
                        />
                        <span className="text-[12px] font-semibold">{f.name}</span>
                      </div>
                      <div className="mt-1 text-[10px] text-[var(--color-fg-dim)] line-clamp-2">
                        {f.blurb}
                      </div>
                    </motion.button>
                  ))}
                </div>
              </Section>

              {/* Model */}
              <Section title="Model" icon={<Layers className="size-3.5" />}>
                <div className="flex flex-wrap gap-1.5">
                  {MODELS_BY_FAMILY[model.family].map((m) => (
                    <Pill
                      key={m.id}
                      active={wall.modelId === m.id}
                      onClick={() => {
                        state.updateActiveWall("modelId", m.id);
                        if (!m.finishes.includes(wall.finish))
                          state.updateActiveWall("finish", m.finishes[0]);
                        if (!m.trackOptions.includes(wall.trackOption))
                          state.updateActiveWall("trackOption", m.trackOptions[0]);
                        if (!m.sealOptions.includes(wall.sealOption))
                          state.updateActiveWall("sealOption", m.sealOptions[0]);
                      }}
                    >
                      {m.shortName}
                    </Pill>
                  ))}
                </div>
                <p className="mt-3 text-[11.5px] leading-relaxed text-[var(--color-fg-dim)]">
                  {model.description}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Stat label="STC" value={`${model.stcRange[0]}–${model.stcRange[1]}`} icon={<Volume2 className="size-3" />} />
                  <Stat label="Thickness" value={`${model.thicknessIn}″`} icon={<Box className="size-3" />} />
                  <Stat label="Max height" value={`${(model.maxHeightIn / 12).toFixed(1)}′`} />
                  <Stat label="Weight" value={`${model.weightPsfRange[0]}-${model.weightPsfRange[1]} psf`} />
                </div>
              </Section>

              {/* Room dimensions */}
              <Section title="Room" icon={<Ruler className="size-3.5" />}>
                <div className="space-y-4">
                  <DimensionRow
                    label="Opening Width"
                    value={wall.room.widthFt}
                    min={10}
                    max={120}
                    suffix="ft"
                    onChange={(v) => state.updateActiveRoom({ widthFt: v })}
                  />
                  <DimensionRow
                    label="Room Depth"
                    value={wall.room.depthFt}
                    min={12}
                    max={120}
                    suffix="ft"
                    onChange={(v) => state.updateActiveRoom({ depthFt: v })}
                  />
                  <DimensionRow
                    label="Ceiling Height"
                    value={wall.room.heightFt}
                    min={8}
                    max={Math.floor(model.maxHeightIn / 12)}
                    suffix="ft"
                    onChange={(v) => state.updateActiveRoom({ heightFt: v })}
                  />
                </div>
              </Section>

              {/* Panel width */}
              <Section title="Panel Width" icon={<Box className="size-3.5" />}>
                <div className="flex items-baseline justify-between mb-2">
                  <span className="text-[11.5px] text-[var(--color-fg-dim)]">
                    {model.panelWidthRangeIn[0]}″ – {model.panelWidthRangeIn[1]}″
                  </span>
                  <span className="font-mono text-sm">{wall.panelWidthIn}″</span>
                </div>
                <Slider
                  min={Math.floor(model.panelWidthRangeIn[0])}
                  max={Math.floor(model.panelWidthRangeIn[1])}
                  step={1}
                  value={Math.min(
                    Math.max(wall.panelWidthIn, Math.floor(model.panelWidthRangeIn[0])),
                    Math.floor(model.panelWidthRangeIn[1]),
                  )}
                  onChange={(v) => state.updateActiveWall("panelWidthIn", v)}
                />
              </Section>

              {/* Stack */}
              <Section title="Stack Direction" icon={<Move3d className="size-3.5" />}>
                <div className="flex flex-wrap gap-2">
                  {STACK_TYPES.map((s) => (
                    <Pill
                      key={s.id}
                      active={wall.stack === s.id}
                      onClick={() => state.updateActiveWall("stack", s.id)}
                    >
                      {s.label}
                    </Pill>
                  ))}
                </div>
              </Section>

              {/* Track */}
              <Section title="Track" icon={<Settings2 className="size-3.5" />}>
                <div className="flex flex-wrap gap-2">
                  {model.trackOptions.map((t) => (
                    <Pill
                      key={t}
                      active={wall.trackOption === t}
                      onClick={() => state.updateActiveWall("trackOption", t)}
                    >
                      {t}
                    </Pill>
                  ))}
                </div>
              </Section>

              {/* Seals */}
              <Section title="Seals" icon={<Cog className="size-3.5" />}>
                <div className="flex flex-wrap gap-2">
                  {model.sealOptions.map((s) => (
                    <Pill
                      key={s}
                      active={wall.sealOption === s}
                      onClick={() => state.updateActiveWall("sealOption", s)}
                    >
                      {s}
                    </Pill>
                  ))}
                </div>
              </Section>

              {/* Finish */}
              <Section title="Finish" icon={<Palette className="size-3.5" />}>
                <div className="flex flex-wrap gap-2">
                  {model.finishes.map((f) => (
                    <Pill
                      key={f}
                      active={wall.finish === f}
                      onClick={() => state.updateActiveWall("finish", f)}
                    >
                      {f}
                    </Pill>
                  ))}
                </div>
              </Section>

              {/* Viewport toggles */}
              <Section title="Viewport" icon={<Eye className="size-3.5" />}>
                <div className="space-y-3">
                  <ToggleRow
                    label="Dimensions overlay"
                    value={state.showDimensions}
                    onChange={(v) => state.setUI("showDimensions", v)}
                  />
                  <ToggleRow
                    label="Floor grid"
                    value={state.showGrid}
                    onChange={(v) => state.setUI("showGrid", v)}
                  />
                  <div className="pt-2">
                    <div className="text-[11px] uppercase tracking-wider text-[var(--color-fg-dim)] mb-2">
                      Camera preset
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(["iso", "front", "top", "stack"] as const).map((p) => (
                        <Pill
                          key={p}
                          active={state.cameraPreset === p}
                          onClick={() => state.setUI("cameraPreset", p)}
                        >
                          {p === "iso" ? (
                            <Maximize2 className="size-3 inline -mt-0.5 mr-1" />
                          ) : null}
                          {p[0].toUpperCase() + p.slice(1)}
                        </Pill>
                      ))}
                    </div>
                  </div>
                </div>
              </Section>

              <div className="h-1" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="border-t border-[var(--color-border)] px-4 py-3 flex items-center gap-2">
        <span className="dot" />
        <span className="text-[11px] text-[var(--color-fg-muted)]">
          Live preview · {model.shortName}
        </span>
        <Wand2 className="ml-auto size-3.5 text-[var(--color-fg-dim)]" />
      </div>
    </aside>
  );
}

function DimensionRow({
  label,
  value,
  min,
  max,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  suffix: string;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[12px] text-[var(--color-fg-muted)]">{label}</span>
        <span className="font-mono text-[13px]">
          {value} <span className="text-[var(--color-fg-dim)] text-[11px]">{suffix}</span>
        </span>
      </div>
      <Slider
        min={min}
        max={max}
        step={1}
        value={Math.min(Math.max(value, min), max)}
        onChange={onChange}
      />
    </div>
  );
}

function ToggleRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[12.5px]">{label}</span>
      <Switch checked={value} onCheckedChange={onChange} />
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]/60 px-2 py-1.5">
      <div className="flex items-center gap-1 text-[9.5px] uppercase tracking-wider text-[var(--color-fg-dim)]">
        {icon}
        {label}
      </div>
      <div className="font-mono text-[12.5px]">{value}</div>
    </div>
  );
}
