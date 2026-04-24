"use client";

import { useConfigurator } from "@/lib/store";
import { computeTakeoff } from "@/lib/takeoff";
import { SERIES } from "@/lib/moderco";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import {
  Boxes,
  ClipboardList,
  Coins,
  FileDown,
  Hammer,
  Ruler,
  ShieldCheck,
  Volume2,
  Weight,
} from "lucide-react";

export function TakeoffPanel() {
  const state = useConfigurator();
  const t = computeTakeoff(state);
  const series = SERIES[state.series];

  return (
    <aside className="surface flex flex-col rounded-xl overflow-hidden h-full max-h-[80vh] lg:max-h-none">
      <div className="px-4 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-fg-dim)]">
            Live Takeoff
          </div>
          <div className="text-sm font-semibold flex items-center gap-2">
            <ClipboardList className="size-3.5" /> Bill of Materials
          </div>
        </div>
        <button className="btn-ghost h-8 px-3 rounded-lg text-[12px] flex items-center gap-1.5">
          <FileDown className="size-3.5" /> Export
        </button>
      </div>

      {/* Summary cards */}
      <div className="p-4 grid grid-cols-2 gap-2.5">
        <SummaryCard
          icon={<Boxes className="size-3.5" />}
          label="Panels"
          value={formatNumber(t.panelCount)}
          sub={`${t.panelWidthIn}″ × ${t.panelHeightFt.toFixed(1)}′`}
        />
        <SummaryCard
          icon={<Ruler className="size-3.5" />}
          label="Track"
          value={`${t.trackLengthFt.toFixed(1)}′`}
          sub={`${t.carrierCount} carriers`}
        />
        <SummaryCard
          icon={<Volume2 className="size-3.5" />}
          label="STC"
          value={`${t.stcRange[0]}–${t.stcRange[1]}`}
          sub={series.family}
        />
        <SummaryCard
          icon={<Weight className="size-3.5" />}
          label="Weight"
          value={`${formatNumber(t.estimatedWeightLb)} lb`}
          sub={`${formatNumber(t.totalAreaSqft)} sq.ft`}
        />
      </div>

      {/* BOM Lines */}
      <div className="px-4 pb-2">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)] mb-2">
          Line Items
        </div>
        <div className="space-y-1.5">
          <LineItem
            icon={<Boxes className="size-3.5" />}
            label={`${series.name} panels (${state.finish})`}
            qty={`${t.totalAreaSqft.toFixed(0)} sq.ft`}
            amount={t.cost.panels}
          />
          <LineItem
            icon={<Ruler className="size-3.5" />}
            label="Suspended track"
            qty={`${t.trackLengthFt.toFixed(1)} ft`}
            amount={t.cost.track}
          />
          <LineItem
            icon={<Hammer className="size-3.5" />}
            label="Carriers"
            qty={`${t.carrierCount} ea`}
            amount={t.cost.carriers}
          />
          <LineItem
            icon={<ShieldCheck className="size-3.5" />}
            label="Acoustic seals & sweeps"
            qty={`${t.panelCount} ea`}
            amount={t.cost.seals}
          />
          <LineItem
            icon={<Hammer className="size-3.5" />}
            label="Hardware pack"
            qty="1 ea"
            amount={t.cost.hardware}
          />
          {t.cost.operationUplift > 0 && (
            <LineItem
              icon={<Coins className="size-3.5" />}
              label={`${state.operation === "automatic" ? "Automatic" : "Power-Assist"} operation uplift`}
              qty="—"
              amount={t.cost.operationUplift}
              accent
            />
          )}
        </div>
      </div>

      {/* Total */}
      <div className="mt-auto px-4 py-4 border-t border-[var(--color-border)] bg-[color-mix(in_oklch,var(--color-surface)_60%,transparent)]">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[11px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)]">
            Subtotal
          </span>
          <span className="font-mono text-[13px] text-[var(--color-fg-muted)]">
            {formatCurrency(t.cost.subtotal)}
          </span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-[12px] uppercase tracking-[0.16em] font-semibold">
            Estimated Total
          </span>
          <AnimatePresence mode="popLayout">
            <motion.span
              key={Math.round(t.cost.total)}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.2 }}
              className="font-mono text-2xl font-semibold gradient-text"
            >
              {formatCurrency(t.cost.total)}
            </motion.span>
          </AnimatePresence>
        </div>
        <p className="mt-2 text-[10.5px] text-[var(--color-fg-dim)] leading-relaxed">
          Order-of-magnitude estimate based on Moderco product literature. Final
          quotation requires site survey and engineering review.
        </p>
      </div>
    </aside>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.25 }}
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/60 p-2.5"
    >
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--color-fg-dim)]">
        {icon}
        {label}
      </div>
      <div className="mt-1 font-mono text-[15px] font-semibold">{value}</div>
      <div className="text-[10.5px] text-[var(--color-fg-dim)] mt-0.5">{sub}</div>
    </motion.div>
  );
}

function LineItem({
  icon,
  label,
  qty,
  amount,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  qty: string;
  amount: number;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center gap-3 px-2.5 py-2 rounded-lg hover:bg-[color-mix(in_oklch,var(--color-surface-2)_70%,transparent)] transition-colors">
      <span
        className={`grid place-items-center size-7 rounded-md ${
          accent
            ? "bg-[color-mix(in_oklch,var(--color-accent)_18%,transparent)] text-[var(--color-accent)]"
            : "bg-[var(--color-surface-2)] text-[var(--color-fg-muted)]"
        }`}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] truncate">{label}</div>
        <div className="text-[10.5px] text-[var(--color-fg-dim)]">{qty}</div>
      </div>
      <div className="font-mono text-[12.5px]">{formatCurrency(amount)}</div>
    </div>
  );
}
