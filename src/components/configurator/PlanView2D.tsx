"use client";

import { getActiveWall, useConfigurator } from "@/lib/store";
import { FAMILIES, MODELS } from "@/lib/moderco";
import { computeWallTakeoff } from "@/lib/takeoff";
import { motion } from "framer-motion";
import { useMemo, useRef, useState, useEffect } from "react";

export function PlanView2D() {
  const wall = useConfigurator(getActiveWall);
  const showDimensions = useConfigurator((s) => s.showDimensions);
  const showGrid = useConfigurator((s) => s.showGrid);

  const model = MODELS[wall.modelId];
  const family = FAMILIES[model.family];
  const t = computeWallTakeoff(wall);

  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 500 });

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const r = entry.contentRect;
      setSize({ w: r.width, h: r.height });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const PAD = 60;
  const roomW = wall.room.widthFt;
  const roomD = wall.room.depthFt;
  const trackRunFt = roomW + 6; // include stack runout

  // scale to fit
  const scaleW = (size.w - PAD * 2) / trackRunFt;
  const scaleH = (size.h - PAD * 2) / (roomD + 4);
  const scale = Math.max(0.5, Math.min(scaleW, scaleH));

  const ftToPx = (ft: number) => ft * scale;
  const cx = size.w / 2;
  const cy = size.h / 2;

  // panels in plan
  const panels = useMemo(() => {
    const count = t.panelCount;
    const panelWidthFt = wall.panelWidthIn / 12;
    const panelThicknessFt = model.thicknessIn / 12;
    const stackSign =
      wall.stack === "right" || wall.stack === "right-pocket"
        ? 1
        : wall.stack === "left" || wall.stack === "left-pocket"
          ? -1
          : 0;

    const arr = [];
    for (let i = 0; i < count; i++) {
      const closedX = -roomW / 2 + (i + 0.5) * panelWidthFt;
      let stackedX: number, rot: number;

      if (wall.stack === "center") {
        const goesRight = i >= count / 2;
        const localIdx = goesRight ? i - Math.floor(count / 2) : Math.ceil(count / 2) - 1 - i;
        const sign = goesRight ? 1 : -1;
        stackedX = sign * (roomW / 2 + 0.4 + localIdx * panelThicknessFt);
        rot = sign * 90;
      } else {
        const localIdx = stackSign > 0 ? count - 1 - i : i;
        stackedX = stackSign * (roomW / 2 + 0.4 + localIdx * panelThicknessFt);
        rot = stackSign * 90;
      }

      const startOffset = (i / Math.max(1, count - 1)) * 0.35;
      const local = Math.max(0, Math.min(1, (wall.openProgress - startOffset) / 0.65));
      const localT = local < 0.5 ? 4 * local ** 3 : 1 - Math.pow(-2 * local + 2, 3) / 2;
      const x = closedX * (1 - localT) + stackedX * localT;
      const r = rot * localT;

      arr.push({ index: i, x, rot: r, panelWidthFt, panelThicknessFt });
    }
    return arr;
  }, [t.panelCount, wall.panelWidthIn, wall.stack, wall.openProgress, model.thicknessIn, roomW]);

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden bg-[#10141b]">
      {/* Decorative grid */}
      {showGrid && (
        <svg className="absolute inset-0 size-full opacity-40 pointer-events-none">
          <defs>
            <pattern id="grid-sm" width={ftToPx(1)} height={ftToPx(1)} patternUnits="userSpaceOnUse">
              <path d={`M ${ftToPx(1)} 0 L 0 0 0 ${ftToPx(1)}`} fill="none" stroke="#2b313b" strokeWidth="0.5" />
            </pattern>
            <pattern id="grid-lg" width={ftToPx(5)} height={ftToPx(5)} patternUnits="userSpaceOnUse">
              <rect width={ftToPx(5)} height={ftToPx(5)} fill="url(#grid-sm)" />
              <path d={`M ${ftToPx(5)} 0 L 0 0 0 ${ftToPx(5)}`} fill="none" stroke="#3a4150" strokeWidth="0.8" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid-lg)" />
        </svg>
      )}

      <svg className="absolute inset-0 size-full" viewBox={`0 0 ${size.w} ${size.h}`}>
        <defs>
          <linearGradient id="roomFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2a313b" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#1a1f27" stopOpacity="0.7" />
          </linearGradient>
          <linearGradient id="panelGrad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor={family.accent} stopOpacity="0.95" />
            <stop offset="100%" stopColor={family.accent} stopOpacity="0.65" />
          </linearGradient>
        </defs>

        {/* Room rectangle */}
        <rect
          x={cx - ftToPx(roomW) / 2}
          y={cy - ftToPx(roomD) / 2}
          width={ftToPx(roomW)}
          height={ftToPx(roomD)}
          fill="url(#roomFill)"
          stroke="#4a5260"
          strokeWidth="1.5"
          rx="2"
        />

        {/* Track centerline (thicker) */}
        <line
          x1={cx - ftToPx(trackRunFt) / 2}
          x2={cx + ftToPx(trackRunFt) / 2}
          y1={cy}
          y2={cy}
          stroke="#cfd2d6"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <line
          x1={cx - ftToPx(trackRunFt) / 2}
          x2={cx + ftToPx(trackRunFt) / 2}
          y1={cy}
          y2={cy}
          stroke="#3a4150"
          strokeWidth="1"
          strokeDasharray="4 3"
        />

        {/* Stack pocket indicators */}
        {(wall.stack === "left-pocket" || wall.stack === "right-pocket") && (
          <rect
            x={
              wall.stack === "left-pocket"
                ? cx - ftToPx(roomW) / 2 - ftToPx(t.stackDepthFt) - 4
                : cx + ftToPx(roomW) / 2 + 4
            }
            y={cy - ftToPx(2)}
            width={ftToPx(t.stackDepthFt)}
            height={ftToPx(4)}
            fill="#1a1f27"
            stroke="#5a6273"
            strokeWidth="1"
            strokeDasharray="3 2"
            rx="1"
          />
        )}

        {/* Panels (top-down rectangles) */}
        {panels.map((p) => {
          const widthPx = ftToPx(p.panelWidthFt);
          const depthPx = ftToPx(p.panelThicknessFt) * 1.6 + 3; // slightly bigger for visibility
          const xPx = cx + ftToPx(p.x) - widthPx / 2;
          const yPx = cy - depthPx / 2;
          return (
            <motion.rect
              key={p.index}
              initial={false}
              animate={{ x: xPx, y: yPx, rotate: p.rot }}
              transition={{ type: "spring", stiffness: 90, damping: 20 }}
              width={widthPx}
              height={depthPx}
              fill="url(#panelGrad)"
              stroke="#1a1d22"
              strokeWidth="0.8"
              rx="1"
              style={{ originX: `${xPx + widthPx / 2}px`, originY: `${yPx + depthPx / 2}px` }}
            />
          );
        })}

        {/* Hatching to indicate the closed wall opening */}
        <line
          x1={cx - ftToPx(roomW) / 2}
          x2={cx + ftToPx(roomW) / 2}
          y1={cy + ftToPx(0.4)}
          y2={cy + ftToPx(0.4)}
          stroke="#5a6273"
          strokeWidth="0.6"
          strokeDasharray="3 2"
          opacity={0.6}
        />

        {/* Dimensions overlay */}
        {showDimensions && (
          <g>
            {/* Width dim */}
            <line
              x1={cx - ftToPx(roomW) / 2}
              x2={cx + ftToPx(roomW) / 2}
              y1={cy - ftToPx(roomD) / 2 - 28}
              y2={cy - ftToPx(roomD) / 2 - 28}
              stroke="#f1c27d"
              strokeWidth="1.2"
            />
            <line x1={cx - ftToPx(roomW) / 2} x2={cx - ftToPx(roomW) / 2} y1={cy - ftToPx(roomD) / 2 - 32} y2={cy - ftToPx(roomD) / 2 - 24} stroke="#f1c27d" strokeWidth="1.2" />
            <line x1={cx + ftToPx(roomW) / 2} x2={cx + ftToPx(roomW) / 2} y1={cy - ftToPx(roomD) / 2 - 32} y2={cy - ftToPx(roomD) / 2 - 24} stroke="#f1c27d" strokeWidth="1.2" />
            <text
              x={cx}
              y={cy - ftToPx(roomD) / 2 - 36}
              textAnchor="middle"
              fill="#f1c27d"
              fontSize="11"
              fontFamily="ui-monospace, monospace"
            >
              {roomW}′-0″
            </text>

            {/* Depth dim */}
            <line
              x1={cx + ftToPx(roomW) / 2 + 28}
              x2={cx + ftToPx(roomW) / 2 + 28}
              y1={cy - ftToPx(roomD) / 2}
              y2={cy + ftToPx(roomD) / 2}
              stroke="#9bd1ff"
              strokeWidth="1.2"
            />
            <text
              x={cx + ftToPx(roomW) / 2 + 38}
              y={cy + 4}
              fill="#9bd1ff"
              fontSize="11"
              fontFamily="ui-monospace, monospace"
            >
              {roomD}′-0″
            </text>

            {/* Track length annotation */}
            <text
              x={cx}
              y={cy + ftToPx(roomD) / 2 + 24}
              textAnchor="middle"
              fill="#c4f08e"
              fontSize="10"
              fontFamily="ui-monospace, monospace"
            >
              Track {t.trackLengthFt.toFixed(1)}′ · {t.panelCount} panels @ {wall.panelWidthIn}″
            </text>
          </g>
        )}

        {/* North arrow + scale */}
        <g transform={`translate(${size.w - 80}, ${size.h - 70})`}>
          <circle r="22" fill="#1a1f27" stroke="#3a4150" strokeWidth="1" />
          <path d="M0,-14 L4,4 L0,1 L-4,4 Z" fill="#f1c27d" />
          <text x="0" y="18" textAnchor="middle" fill="#aab" fontSize="9" fontFamily="ui-monospace, monospace">N</text>
        </g>
        <text x="20" y={size.h - 18} fill="#777f8c" fontSize="10" fontFamily="ui-monospace, monospace">
          1″ ≈ {(1 / scale).toFixed(2)}′
        </text>
      </svg>
    </div>
  );
}
