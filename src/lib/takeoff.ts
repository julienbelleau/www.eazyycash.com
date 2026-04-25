import {
  CARRIER_PRICE,
  CONFIG_PRICE_FACTOR,
  ENGINEERING_FEE,
  FAMILY_PRICE_PER_SQFT,
  FINISH_PRICE_FACTOR,
  HARDWARE_PACK_PER_SYSTEM,
  MODELS,
  OPERATION_PRICE_FACTOR,
  SEAL_PRICE_PER_PANEL,
  TRACK_DEFAULT_PRICE_PER_FT,
  TRACK_PRICE_PER_FT,
} from "./moderco";
import type { Project, Wall } from "./store";

export interface WallTakeoff {
  wallId: string;
  wallName: string;
  modelName: string;
  panelCount: number;
  panelWidthIn: number;
  panelHeightFt: number;
  trackLengthFt: number;
  trackOption: string;
  carrierCount: number;
  totalAreaSqft: number;
  estimatedWeightLb: number;
  weightPsf: number;
  stcRange: [number, number];
  stackDepthFt: number;
  finish: string;
  operation: string;
  cost: {
    panels: number;
    track: number;
    carriers: number;
    seals: number;
    hardware: number;
    engineering: number;
    operationUplift: number;
    subtotal: number;
    total: number;
  };
}

export function computeWallTakeoff(wall: Wall): WallTakeoff {
  const model = MODELS[wall.modelId];
  const widthIn = wall.room.widthFt * 12;
  const heightFt = Math.min(wall.room.heightFt, model.maxHeightIn / 12);
  const panelThicknessFt = model.thicknessIn / 12;

  // panel count
  const rawCount = widthIn / wall.panelWidthIn;
  let panelCount = Math.ceil(rawCount);
  if (model.configuration === "paired" && panelCount % 2 === 1) panelCount += 1;

  // stack runout (visual + track length)
  const stackThicknessFt = panelCount * panelThicknessFt;
  const stackDepthFt = stackThicknessFt + 1.0;
  const stackRunFt =
    wall.stack === "center" ? stackThicknessFt / 2 : stackThicknessFt;
  const trackLengthFt = wall.room.widthFt + stackRunFt + 1.5;

  // carriers
  const carrierCount =
    model.configuration === "paired"
      ? Math.ceil(panelCount / 2)
      : model.configuration === "continuously-hinged"
        ? 2
        : panelCount;

  // area & weight (mid-of-range psf)
  const weightPsf = (model.weightPsfRange[0] + model.weightPsfRange[1]) / 2;
  const totalAreaSqft = wall.room.widthFt * heightFt;
  const estimatedWeightLb = totalAreaSqft * weightPsf;

  // pricing
  const familyPpsf = FAMILY_PRICE_PER_SQFT[model.family];
  const cfgFactor = CONFIG_PRICE_FACTOR[model.configuration];
  const opFactor = OPERATION_PRICE_FACTOR[model.operation];
  const finishFactor = FINISH_PRICE_FACTOR[wall.finish] ?? 1;

  const panelCost = totalAreaSqft * familyPpsf * cfgFactor * finishFactor;
  const trackPpf = TRACK_PRICE_PER_FT[wall.trackOption] ?? TRACK_DEFAULT_PRICE_PER_FT;
  const trackCost = trackLengthFt * trackPpf;
  const carrierCost = carrierCount * CARRIER_PRICE;
  const sealCost = panelCount * SEAL_PRICE_PER_PANEL;
  const hardwareCost = HARDWARE_PACK_PER_SYSTEM;
  const engineeringCost = ENGINEERING_FEE;

  const subtotal =
    panelCost + trackCost + carrierCost + sealCost + hardwareCost + engineeringCost;
  const operationUplift = subtotal * (opFactor - 1);
  const total = subtotal + operationUplift;

  return {
    wallId: wall.id,
    wallName: wall.name,
    modelName: model.name,
    panelCount,
    panelWidthIn: wall.panelWidthIn,
    panelHeightFt: heightFt,
    trackLengthFt,
    trackOption: wall.trackOption,
    carrierCount,
    totalAreaSqft,
    estimatedWeightLb,
    weightPsf,
    stcRange: model.stcRange,
    stackDepthFt,
    finish: wall.finish,
    operation: model.operation,
    cost: {
      panels: panelCost,
      track: trackCost,
      carriers: carrierCost,
      seals: sealCost,
      hardware: hardwareCost,
      engineering: engineeringCost,
      operationUplift,
      subtotal,
      total,
    },
  };
}

export interface ProjectTakeoff {
  walls: WallTakeoff[];
  totals: {
    panelCount: number;
    trackLengthFt: number;
    totalAreaSqft: number;
    estimatedWeightLb: number;
    cost: number;
  };
}

export function computeProjectTakeoff(project: Project): ProjectTakeoff {
  const walls = project.walls.map(computeWallTakeoff);
  const totals = walls.reduce(
    (acc, w) => ({
      panelCount: acc.panelCount + w.panelCount,
      trackLengthFt: acc.trackLengthFt + w.trackLengthFt,
      totalAreaSqft: acc.totalAreaSqft + w.totalAreaSqft,
      estimatedWeightLb: acc.estimatedWeightLb + w.estimatedWeightLb,
      cost: acc.cost + w.cost.total,
    }),
    { panelCount: 0, trackLengthFt: 0, totalAreaSqft: 0, estimatedWeightLb: 0, cost: 0 },
  );
  return { walls, totals };
}
