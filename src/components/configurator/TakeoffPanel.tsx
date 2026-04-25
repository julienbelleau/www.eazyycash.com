"use client";

import { getActiveWall, useConfigurator } from "@/lib/store";
import { computeProjectTakeoff } from "@/lib/takeoff";
import { MODELS } from "@/lib/moderco";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import {
  Boxes,
  ClipboardList,
  Coins,
  FileDown,
  Hammer,
  PackageOpen,
  Ruler,
  ShieldCheck,
  Sigma,
  Volume2,
  Weight,
} from "lucide-react";
import { useState } from "react";
import { generateQuotePdf } from "@/lib/pdf";
import { downloadProject } from "@/lib/storage";

export function TakeoffPanel() {
  const project = useConfigurator((s) => s.project);
  const wall = useConfigurator(getActiveWall);
  const setActive = useConfigurator((s) => s.setActiveWall);
  const takeoff = computeProjectTakeoff(project);
  const wallT = takeoff.walls.find((w) => w.wallId === wall.id) ?? takeoff.walls[0];
  const model = MODELS[wall.modelId];

  const [exporting, setExporting] = useState(false);
  const [scope, setScope] = useState<"wall" | "project">("project");

  const onExportPdf = async () => {
    setExporting(true);
    try {
      const captureFn = (
        window as unknown as { __captureViewportSnapshot?: () => string | null }
      ).__captureViewportSnapshot;
      const snapshot = captureFn?.() ?? null;
      const snapshots = snapshot ? [{ wallId: wall.id, dataUrl: snapshot }] : [];
      const doc = generateQuotePdf({ project, snapshots });
      doc.save(`${project.name.replace(/[^\w-]+/g, "_")}_quote.pdf`);
    } finally {
      setExporting(false);
    }
  };

  const onExportJson = () => downloadProject(project);

  return (
    <aside className="surface flex flex-col rounded-xl overflow-hidden h-full max-h-[80vh] lg:max-h-none">
      <div className="px-4 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-fg-dim)]">
            Live Takeoff
          </div>
          <div className="text-sm font-semibold flex items-center gap-2">
            <ClipboardList className="size-3.5" />
            {scope === "project" ? "Project Total" : "Active Wall"}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onExportJson}
            className="btn-ghost h-8 px-2.5 rounded-lg text-[11.5px] flex items-center gap-1.5"
            title="Export project as JSON"
          >
            <PackageOpen className="size-3.5" /> JSON
          </button>
          <button
            onClick={onExportPdf}
            disabled={exporting}
            className="btn-primary h-8 px-2.5 rounded-lg text-[11.5px] flex items-center gap-1.5"
            title="Export quote as PDF"
          >
            <FileDown className="size-3.5" />
            {exporting ? "..." : "PDF"}
          </button>
        </div>
      </div>

      {/* Scope tabs */}
      <div className="px-3 pt-3 pb-2">
        <div className="flex bg-[var(--color-bg-2)] rounded-lg p-1">
          <ScopeTab active={scope === "project"} onClick={() => setScope("project")}>
            <Sigma className="size-3" /> Project ({project.walls.length})
          </ScopeTab>
          <ScopeTab active={scope === "wall"} onClick={() => setScope("wall")}>
            <Boxes className="size-3" /> Wall
          </ScopeTab>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {scope === "project" ? (
          <motion.div
            key="project"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 overflow-y-auto"
          >
            {/* Summary */}
            <div className="p-4 grid grid-cols-2 gap-2.5">
              <SummaryCard
                icon={<Boxes className="size-3.5" />}
                label="Panels"
                value={formatNumber(takeoff.totals.panelCount)}
                sub={`${project.walls.length} wall${project.walls.length === 1 ? "" : "s"}`}
              />
              <SummaryCard
                icon={<Ruler className="size-3.5" />}
                label="Track"
                value={`${takeoff.totals.trackLengthFt.toFixed(0)}′`}
                sub="suspended"
              />
              <SummaryCard
                icon={<Weight className="size-3.5" />}
                label="Weight"
                value={`${formatNumber(takeoff.totals.estimatedWeightLb)} lb`}
                sub={`${formatNumber(takeoff.totals.totalAreaSqft)} sf`}
              />
              <SummaryCard
                icon={<Coins className="size-3.5" />}
                label="Estimate"
                value={formatCurrency(takeoff.totals.cost)}
                sub="Order-of-mag."
              />
            </div>

            {/* Per-wall list */}
            <div className="px-4 pb-4">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)] mb-2">
                Per-wall breakdown
              </div>
              <div className="space-y-1.5">
                {takeoff.walls.map((w) => {
                  const isActive = w.wallId === wall.id;
                  return (
                    <button
                      key={w.wallId}
                      onClick={() => setActive(w.wallId)}
                      className={`w-full text-left rounded-lg border px-3 py-2 flex items-center gap-3 transition-colors ${
                        isActive
                          ? "border-[var(--color-accent)] bg-[color-mix(in_oklch,var(--color-accent)_8%,transparent)]"
                          : "border-[var(--color-border)] bg-[var(--color-surface)]/60 hover:border-[var(--color-border-strong)]"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-[12.5px] font-medium truncate">{w.wallName}</div>
                        <div className="text-[10.5px] text-[var(--color-fg-dim)] truncate">
                          {w.modelName} · {w.panelCount} panels · {w.trackLengthFt.toFixed(1)}′
                        </div>
                      </div>
                      <div className="font-mono text-[12px] shrink-0">
                        {formatCurrency(w.cost.total)}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="wall"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 overflow-y-auto"
          >
            <div className="p-4 grid grid-cols-2 gap-2.5">
              <SummaryCard
                icon={<Boxes className="size-3.5" />}
                label="Panels"
                value={formatNumber(wallT.panelCount)}
                sub={`${wallT.panelWidthIn}″ × ${wallT.panelHeightFt.toFixed(1)}′`}
              />
              <SummaryCard
                icon={<Ruler className="size-3.5" />}
                label="Track"
                value={`${wallT.trackLengthFt.toFixed(1)}′`}
                sub={`${wallT.trackOption} · ${wallT.carrierCount} carriers`}
              />
              <SummaryCard
                icon={<Volume2 className="size-3.5" />}
                label="STC"
                value={`${wallT.stcRange[0]}–${wallT.stcRange[1]}`}
                sub={model.shortName}
              />
              <SummaryCard
                icon={<Weight className="size-3.5" />}
                label="Weight"
                value={`${formatNumber(wallT.estimatedWeightLb)} lb`}
                sub={`${formatNumber(wallT.totalAreaSqft)} sf`}
              />
            </div>

            <div className="px-4 pb-2">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)] mb-2">
                Line Items
              </div>
              <div className="space-y-1">
                <LineItem icon={<Boxes className="size-3.5" />} label={`${model.name} panels (${wall.finish})`} qty={`${wallT.totalAreaSqft.toFixed(0)} sf`} amount={wallT.cost.panels} />
                <LineItem icon={<Ruler className="size-3.5" />} label={`Track ${wallT.trackOption}`} qty={`${wallT.trackLengthFt.toFixed(1)} ft`} amount={wallT.cost.track} />
                <LineItem icon={<Hammer className="size-3.5" />} label="Carriers" qty={`${wallT.carrierCount} ea`} amount={wallT.cost.carriers} />
                <LineItem icon={<ShieldCheck className="size-3.5" />} label={`Seals (${wall.sealOption})`} qty={`${wallT.panelCount} ea`} amount={wallT.cost.seals} />
                <LineItem icon={<Hammer className="size-3.5" />} label="Hardware pack" qty="1 ea" amount={wallT.cost.hardware} />
                <LineItem icon={<ClipboardList className="size-3.5" />} label="Engineering / shop drawings" qty="1 lot" amount={wallT.cost.engineering} />
                {wallT.cost.operationUplift > 0 && (
                  <LineItem icon={<Coins className="size-3.5" />} label="Electric operation uplift" qty="—" amount={wallT.cost.operationUplift} accent />
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer total */}
      <div className="mt-auto px-4 py-4 border-t border-[var(--color-border)] bg-[color-mix(in_oklch,var(--color-surface)_60%,transparent)]">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[11px] uppercase tracking-[0.16em] text-[var(--color-fg-dim)]">
            {scope === "project" ? "Project subtotal" : "Wall subtotal"}
          </span>
          <span className="font-mono text-[13px] text-[var(--color-fg-muted)]">
            {formatCurrency(scope === "project" ? takeoff.totals.cost : wallT.cost.subtotal)}
          </span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-[12px] uppercase tracking-[0.16em] font-semibold">
            {scope === "project" ? "Project total" : "Wall total"}
          </span>
          <AnimatePresence mode="popLayout">
            <motion.span
              key={`${scope}-${Math.round(scope === "project" ? takeoff.totals.cost : wallT.cost.total)}`}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.2 }}
              className="font-mono text-2xl font-semibold gradient-text"
            >
              {formatCurrency(scope === "project" ? takeoff.totals.cost : wallT.cost.total)}
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

function ScopeTab({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 h-7 rounded-md text-[11.5px] font-medium flex items-center justify-center gap-1 transition-all ${
        active ? "bg-[var(--color-surface-2)] text-[var(--color-fg)]" : "text-[var(--color-fg-dim)] hover:text-[var(--color-fg-muted)]"
      }`}
    >
      {children}
    </button>
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
      <div className="text-[10.5px] text-[var(--color-fg-dim)] mt-0.5 truncate">{sub}</div>
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
