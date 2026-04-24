"use client";

import { useConfigurator } from "@/lib/store";
import {
  CONFIGS,
  MAX_PANEL_WIDTH_IN,
  MIN_PANEL_WIDTH_IN,
  Operation,
  PanelConfig,
  SeriesId,
  SERIES,
  SERIES_LIST,
  STACK_TYPES,
} from "@/lib/moderco";
import { Section } from "@/components/ui/Section";
import { Slider } from "@/components/ui/Slider";
import { Pill } from "@/components/ui/Pill";
import { Switch } from "@/components/ui/Switch";
import {
  Box,
  Cog,
  Eye,
  Layers,
  Maximize2,
  Move3d,
  Palette,
  Ruler,
  Settings2,
  Wand2,
} from "lucide-react";
import { motion } from "framer-motion";

export function ConfigSidebar() {
  const state = useConfigurator();
  const series = SERIES[state.series];

  return (
    <aside className="surface flex flex-col rounded-xl overflow-hidden h-full max-h-[80vh] lg:max-h-none">
      <div className="px-4 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-fg-dim)]">
            Configuration
          </div>
          <div className="text-sm font-semibold">{state.projectName}</div>
        </div>
        <button
          onClick={state.reset}
          className="text-[11px] text-[var(--color-fg-dim)] hover:text-[var(--color-fg)] transition-colors"
        >
          Reset
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-7">
        {/* Series */}
        <Section
          title="Product Series"
          icon={<Layers className="size-3.5" />}
          hint={series.family}
        >
          <div className="grid grid-cols-2 gap-2">
            {SERIES_LIST.map((s) => (
              <motion.button
                key={s.id}
                type="button"
                onClick={() => state.set("series", s.id as SeriesId)}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.98 }}
                className={`relative rounded-lg border text-left p-3 transition-all ${
                  state.series === s.id
                    ? "border-[var(--color-accent)] bg-[color-mix(in_oklch,var(--color-accent)_8%,transparent)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface)]/60 hover:border-[var(--color-border-strong)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="size-2 rounded-full"
                    style={{ background: s.accent, boxShadow: `0 0 8px ${s.accent}` }}
                  />
                  <span className="text-[13px] font-semibold">{s.name}</span>
                </div>
                <div className="mt-1 text-[10px] text-[var(--color-fg-dim)] uppercase tracking-wider">
                  STC {s.stcRange[0]}–{s.stcRange[1]} · {s.weightPsf} psf
                </div>
              </motion.button>
            ))}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-[var(--color-fg-dim)]">
            {series.description}
          </p>
        </Section>

        {/* Room dimensions */}
        <Section title="Room" icon={<Ruler className="size-3.5" />} delay={0.04}>
          <div className="space-y-4">
            <DimensionRow
              label="Width"
              value={state.room.widthFt}
              min={10}
              max={120}
              suffix="ft"
              onChange={(v) => state.setRoom({ widthFt: v })}
            />
            <DimensionRow
              label="Depth"
              value={state.room.depthFt}
              min={12}
              max={120}
              suffix="ft"
              onChange={(v) => state.setRoom({ depthFt: v })}
            />
            <DimensionRow
              label="Ceiling"
              value={state.room.heightFt}
              min={8}
              max={Math.floor(series.maxHeightIn / 12)}
              suffix="ft"
              onChange={(v) => state.setRoom({ heightFt: v })}
            />
          </div>
        </Section>

        {/* Panel width */}
        <Section title="Panel Width" icon={<Box className="size-3.5" />} delay={0.08}>
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-[11.5px] text-[var(--color-fg-dim)]">
              {MIN_PANEL_WIDTH_IN}″ – {MAX_PANEL_WIDTH_IN}″
            </span>
            <span className="font-mono text-sm">{state.panelWidthIn}″</span>
          </div>
          <Slider
            min={MIN_PANEL_WIDTH_IN}
            max={MAX_PANEL_WIDTH_IN}
            step={1}
            value={state.panelWidthIn}
            onChange={(v) => state.set("panelWidthIn", v)}
          />
        </Section>

        {/* Configuration */}
        <Section title="Configuration" icon={<Settings2 className="size-3.5" />} delay={0.12}>
          <div className="flex flex-wrap gap-2">
            {CONFIGS.map((c) => (
              <Pill
                key={c.id}
                active={state.config === c.id}
                onClick={() => state.set("config", c.id as PanelConfig)}
                title={c.description}
              >
                {c.label}
              </Pill>
            ))}
          </div>
        </Section>

        {/* Stack */}
        <Section title="Stack Direction" icon={<Move3d className="size-3.5" />} delay={0.16}>
          <div className="flex flex-wrap gap-2">
            {STACK_TYPES.map((s) => (
              <Pill
                key={s.id}
                active={state.stack === s.id}
                onClick={() => state.set("stack", s.id)}
              >
                {s.label}
              </Pill>
            ))}
          </div>
        </Section>

        {/* Operation */}
        <Section title="Operation" icon={<Cog className="size-3.5" />} delay={0.2}>
          <div className="flex flex-wrap gap-2">
            {(["manual", "power-assist", "automatic"] as Operation[]).map((op) => (
              <Pill
                key={op}
                active={state.operation === op}
                onClick={() => state.set("operation", op)}
              >
                {op === "manual"
                  ? "Manual"
                  : op === "power-assist"
                    ? "Power-Assist"
                    : "Automatic"}
              </Pill>
            ))}
          </div>
        </Section>

        {/* Finish */}
        <Section title="Finish" icon={<Palette className="size-3.5" />} delay={0.24}>
          <div className="flex flex-wrap gap-2">
            {series.finishes.map((f) => (
              <Pill
                key={f}
                active={state.finish === f}
                onClick={() => state.set("finish", f)}
              >
                {f}
              </Pill>
            ))}
          </div>
        </Section>

        {/* View toggles */}
        <Section title="Viewport" icon={<Eye className="size-3.5" />} delay={0.28}>
          <div className="space-y-3">
            <ToggleRow
              label="Dimensions overlay"
              value={state.showDimensions}
              onChange={(v) => state.set("showDimensions", v)}
            />
            <ToggleRow
              label="Floor grid"
              value={state.showGrid}
              onChange={(v) => state.set("showGrid", v)}
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
                    onClick={() => state.set("cameraPreset", p)}
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
      </div>

      {/* Footer with status */}
      <div className="border-t border-[var(--color-border)] px-4 py-3 flex items-center gap-2">
        <span className="dot" />
        <span className="text-[11px] text-[var(--color-fg-muted)]">
          Live preview · {series.name}
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
      <Slider min={min} max={max} step={1} value={value} onChange={onChange} />
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
