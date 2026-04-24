import {
  CARRIER_PRICE,
  HARDWARE_PACK_PER_SYSTEM,
  OPERATION_PRICE_FACTOR,
  PANEL_PRICE_PER_SQFT,
  SEAL_PRICE_PER_PANEL,
  SERIES,
  SERIES_PRICE_MULTIPLIER,
  TRACK_PRICE_PER_FT,
} from "./moderco";
import type { ConfiguratorState } from "./store";

export interface Takeoff {
  panelCount: number;
  panelWidthIn: number;
  panelHeightFt: number;
  trackLengthFt: number;
  carrierCount: number;
  totalAreaSqft: number;
  estimatedWeightLb: number;
  stcRange: [number, number];
  stackDepthFt: number;
  finish: string;
  cost: {
    panels: number;
    track: number;
    carriers: number;
    seals: number;
    hardware: number;
    operationUplift: number;
    subtotal: number;
    total: number;
  };
}

export function computeTakeoff(state: ConfiguratorState): Takeoff {
  const series = SERIES[state.series];
  const widthIn = state.room.widthFt * 12;
  const heightFt = Math.min(state.room.heightFt, series.maxHeightIn / 12);

  // Panel count: how many panels of width to span the opening.
  const rawCount = widthIn / state.panelWidthIn;
  let panelCount = Math.ceil(rawCount);
  // Paired configs need an even number; continuously hinged is one continuous train.
  if (state.config === "paired" && panelCount % 2 === 1) panelCount += 1;

  // Stack: track length includes a stack pocket on selected side(s).
  const panelThicknessFt = series.panelThicknessIn / 12;
  const stackThicknessFt = panelCount * panelThicknessFt;
  const stackDepthFt = stackThicknessFt + 1.0; // pocket clearance

  // Carriers: paired = 1 per pair, individual = 1 per panel, hinged = 2 (lead + trail).
  const carrierCount =
    state.config === "paired"
      ? Math.ceil(panelCount / 2)
      : state.config === "continuously-hinged"
        ? 2
        : panelCount;

  // Track length = opening + stack runout (depends on stack style).
  const stackRunFt =
    state.stack === "center" ? stackThicknessFt / 2 : stackThicknessFt;
  const trackLengthFt = state.room.widthFt + stackRunFt + 1.5;

  // Area + weight.
  const totalAreaSqft = state.room.widthFt * heightFt;
  const estimatedWeightLb = totalAreaSqft * series.weightPsf;

  // Costs.
  const seriesMult = SERIES_PRICE_MULTIPLIER[state.series];
  const opMult = OPERATION_PRICE_FACTOR[state.operation];

  const panelCost = totalAreaSqft * PANEL_PRICE_PER_SQFT * seriesMult;
  const trackCost = trackLengthFt * TRACK_PRICE_PER_FT;
  const carrierCost = carrierCount * CARRIER_PRICE;
  const sealCost = panelCount * SEAL_PRICE_PER_PANEL;
  const hardwareCost = HARDWARE_PACK_PER_SYSTEM;
  const subtotal = panelCost + trackCost + carrierCost + sealCost + hardwareCost;
  const operationUplift = subtotal * (opMult - 1);
  const total = subtotal + operationUplift;

  return {
    panelCount,
    panelWidthIn: state.panelWidthIn,
    panelHeightFt: heightFt,
    trackLengthFt,
    carrierCount,
    totalAreaSqft,
    estimatedWeightLb,
    stcRange: series.stcRange,
    stackDepthFt,
    finish: state.finish,
    cost: {
      panels: panelCost,
      track: trackCost,
      carriers: carrierCost,
      seals: sealCost,
      hardware: hardwareCost,
      operationUplift,
      subtotal,
      total,
    },
  };
}
