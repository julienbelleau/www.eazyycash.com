// Moderco operable partition catalog — based on publicly available data from
// moderco.com (Excel 700, Signature 800, Crystal/Vision glass walls).
// Values are intended for layout estimation; final quotes require Moderco engineering review.
//
// Sources:
//   https://www.moderco.com/products/operable-partition/
//   https://www.moderco.com/products/operable-partition/signature-800/
//   https://www.moderco.com/products/operable-partition/excel-700/

export type FamilyId = "excel-700" | "signature-800" | "crystal" | "vision";

export type ModelId =
  | "excel-731"
  | "excel-732"
  | "excel-733-e"
  | "excel-733-eg"
  | "sig-841"
  | "sig-842"
  | "sig-843-e"
  | "crystal"
  | "vision-single"
  | "vision-paired";

export interface Family {
  id: FamilyId;
  name: string;
  blurb: string;
  accent: string;
}

export const FAMILIES: Record<FamilyId, Family> = {
  "excel-700": {
    id: "excel-700",
    name: "Excel 700",
    blurb: "Manually & electrically operated, 3″ panel, value-engineered.",
    accent: "oklch(0.78 0.16 75)",
  },
  "signature-800": {
    id: "signature-800",
    name: "Signature 800",
    blurb: "World-class 4″ acoustical partition — most versatile assembly.",
    accent: "oklch(0.72 0.16 50)",
  },
  crystal: {
    id: "crystal",
    name: "Crystal",
    blurb: "Double-glazed full-height acoustic glass wall, STC 44.",
    accent: "oklch(0.84 0.08 200)",
  },
  vision: {
    id: "vision",
    name: "Vision",
    blurb: "Open-plan glass partition — natural light with division.",
    accent: "oklch(0.86 0.06 215)",
  },
};

export type Configuration = "individual" | "paired" | "continuously-hinged";
export type Operation = "manual" | "electric";

export interface ModelSpec {
  id: ModelId;
  family: FamilyId;
  name: string;
  shortName: string;
  configuration: Configuration;
  operation: Operation;
  thicknessIn: number;
  stcRange: [number, number];
  weightPsfRange: [number, number];
  maxHeightIn: number; // inches
  panelWidthRangeIn: [number, number];
  closure: string;
  trackOptions: string[];
  sealOptions: string[];
  finishes: string[];
  description: string;
  isGlass?: boolean;
}

export const MODELS: Record<ModelId, ModelSpec> = {
  // --- Excel 700 series ---
  "excel-731": {
    id: "excel-731",
    family: "excel-700",
    name: "Excel 731",
    shortName: "731",
    configuration: "individual",
    operation: "manual",
    thicknessIn: 3,
    stcRange: [43, 49],
    weightPsfRange: [5.5, 10.9],
    maxHeightIn: 30 * 12 + 3,
    panelWidthRangeIn: [24, 48.5],
    closure: "Telescopic / hinged",
    trackOptions: ["#23-T", "#33-T", "#72"],
    sealOptions: ["FA"],
    finishes: ["Vinyl", "Fabric", "Marker board", "Uncovered Steel", "Custom"],
    description:
      "Single-panel manually operated wall — best for individual room dividing with remote/side stack.",
  },
  "excel-732": {
    id: "excel-732",
    family: "excel-700",
    name: "Excel 732",
    shortName: "732",
    configuration: "paired",
    operation: "manual",
    thicknessIn: 3,
    stcRange: [43, 49],
    weightPsfRange: [4.1, 5.1],
    maxHeightIn: 22 * 12 + 3,
    panelWidthRangeIn: [24, 49.25],
    closure: "Wall jamb or pocket door",
    trackOptions: ["#45-T", "#72"],
    sealOptions: ["FV"],
    finishes: ["Vinyl", "Carpet"],
    description:
      "Paired-panel manual wall, lightweight — fast deployment with center closure.",
  },
  "excel-733-e": {
    id: "excel-733-e",
    family: "excel-700",
    name: "Excel 733-E",
    shortName: "733-E",
    configuration: "continuously-hinged",
    operation: "electric",
    thicknessIn: 3,
    stcRange: [48, 52],
    weightPsfRange: [7.5, 8.5],
    maxHeightIn: 22 * 12 + 3,
    panelWidthRangeIn: [24, 48],
    closure: "Center continuous hinge",
    trackOptions: ["#80"],
    sealOptions: ["FA"],
    finishes: ["Vinyl", "Fabric", "Marker board", "Custom"],
    description:
      "Continuously hinged electric wall — single-button deployment for multi-purpose spaces.",
  },
  "excel-733-eg": {
    id: "excel-733-eg",
    family: "excel-700",
    name: "Excel 733-EG",
    shortName: "733-EG",
    configuration: "continuously-hinged",
    operation: "electric",
    thicknessIn: 3,
    stcRange: [48, 52],
    weightPsfRange: [7.5, 8.5],
    maxHeightIn: 33 * 12 + 3,
    panelWidthRangeIn: [24, 48],
    closure: "Center continuous hinge",
    trackOptions: ["#80"],
    sealOptions: ["FA"],
    finishes: ["Vinyl", "Fabric", "Tack board", "Custom"],
    description:
      "Gymnasium divider — heavy-duty electric continuously hinged, designed for tall openings.",
  },

  // --- Signature 800 series ---
  "sig-841": {
    id: "sig-841",
    family: "signature-800",
    name: "Signature 841",
    shortName: "841",
    configuration: "individual",
    operation: "manual",
    thicknessIn: 4,
    stcRange: [50, 55],
    weightPsfRange: [6, 9.5],
    maxHeightIn: 33 * 12 + 3,
    panelWidthRangeIn: [24, 48.5],
    closure: "Remote / side / pocket",
    trackOptions: ["#23-T", "#33-T", "#45-T", "#55-T", "#72"],
    sealOptions: ["FA", "FM-1", "FM-2", "FM-3", "FM-4", "MM-1", "MM-55", "AA-1.5", "FF", "FP"],
    finishes: ["Vinyl", "Fabric", "Carpet", "Plastic Laminate", "Wood Veneer", "Steel", "Marker board", "Tack board", "Custom"],
    description:
      "Flagship 4″ individual-panel system. Highest STC and tallest opening height for premium ballrooms and conference centers.",
  },
  "sig-842": {
    id: "sig-842",
    family: "signature-800",
    name: "Signature 842",
    shortName: "842",
    configuration: "paired",
    operation: "manual",
    thicknessIn: 4,
    stcRange: [50, 55],
    weightPsfRange: [6, 9.5],
    maxHeightIn: 22 * 12 + 3,
    panelWidthRangeIn: [24, 48.5],
    closure: "Center wall jamb or pocket",
    trackOptions: ["#33-T", "#45-T", "#55-T", "#72"],
    sealOptions: ["FA", "FM-1", "FM-2", "MM-1", "FF"],
    finishes: ["Vinyl", "Fabric", "Carpet", "Plastic Laminate", "Wood Veneer", "Marker board", "Custom"],
    description:
      "Paired-panel 4″ acoustical wall — workhorse for hotels, conference centers and ballrooms.",
  },
  "sig-843-e": {
    id: "sig-843-e",
    family: "signature-800",
    name: "Signature 843-E",
    shortName: "843-E",
    configuration: "continuously-hinged",
    operation: "electric",
    thicknessIn: 4,
    stcRange: [48, 53],
    weightPsfRange: [6, 8.5],
    maxHeightIn: 22 * 12 + 3,
    panelWidthRangeIn: [24, 48.5],
    closure: "Center continuous hinge — electric",
    trackOptions: ["#55-T", "#72"],
    sealOptions: ["FA", "FM-1", "FM-2"],
    finishes: ["Vinyl", "Fabric", "Wood Veneer", "Marker board", "Custom"],
    description:
      "Electric continuously hinged 4″ premium system — push-button deploy for hospitality.",
  },

  // --- Crystal / Vision glass ---
  crystal: {
    id: "crystal",
    family: "crystal",
    name: "Crystal",
    shortName: "Crystal",
    configuration: "paired",
    operation: "manual",
    thicknessIn: 4,
    stcRange: [42, 44],
    weightPsfRange: [11, 13],
    maxHeightIn: 14 * 12,
    panelWidthRangeIn: [30, 48],
    closure: "Center wall jamb",
    trackOptions: ["#55-T", "#72"],
    sealOptions: ["FA", "FF"],
    finishes: ["Clear", "Frosted", "Tinted", "Custom Print"],
    description:
      "Double-glazed full-height acoustic glass wall — STC 44, steel reinforced structural frame.",
    isGlass: true,
  },
  "vision-single": {
    id: "vision-single",
    family: "vision",
    name: "Vision Single",
    shortName: "Vision-S",
    configuration: "individual",
    operation: "manual",
    thicknessIn: 2.5,
    stcRange: [36, 40],
    weightPsfRange: [9, 11],
    maxHeightIn: 12 * 12,
    panelWidthRangeIn: [30, 48],
    closure: "Side / pocket",
    trackOptions: ["#23-T", "#33-T"],
    sealOptions: ["FA"],
    finishes: ["Clear", "Frosted", "Tinted"],
    description:
      "Single-panel glass operable wall — division with maximum daylight in open-plan offices.",
    isGlass: true,
  },
  "vision-paired": {
    id: "vision-paired",
    family: "vision",
    name: "Vision Paired",
    shortName: "Vision-P",
    configuration: "paired",
    operation: "manual",
    thicknessIn: 2.5,
    stcRange: [36, 40],
    weightPsfRange: [9, 11],
    maxHeightIn: 12 * 12,
    panelWidthRangeIn: [30, 48],
    closure: "Center jamb",
    trackOptions: ["#33-T", "#45-T"],
    sealOptions: ["FA"],
    finishes: ["Clear", "Frosted", "Tinted"],
    description:
      "Paired glass operable wall — fast center-closure stacking with daylight.",
    isGlass: true,
  },
};

export const MODEL_LIST: ModelSpec[] = Object.values(MODELS);
export const FAMILY_LIST: Family[] = Object.values(FAMILIES);

export const MODELS_BY_FAMILY: Record<FamilyId, ModelSpec[]> = {
  "excel-700": MODEL_LIST.filter((m) => m.family === "excel-700"),
  "signature-800": MODEL_LIST.filter((m) => m.family === "signature-800"),
  crystal: MODEL_LIST.filter((m) => m.family === "crystal"),
  vision: MODEL_LIST.filter((m) => m.family === "vision"),
};

// --- Stack types ---
export type StackType = "left" | "right" | "center" | "left-pocket" | "right-pocket";

export const STACK_TYPES: { id: StackType; label: string }[] = [
  { id: "left", label: "Left Stack" },
  { id: "right", label: "Right Stack" },
  { id: "center", label: "Center Split" },
  { id: "left-pocket", label: "Left Pocket" },
  { id: "right-pocket", label: "Right Pocket" },
];

// --- Pricing model (order-of-magnitude estimate) ---
export const TRACK_PRICE_PER_FT: Record<string, number> = {
  "#23-T": 62,
  "#33-T": 78,
  "#45-T": 92,
  "#55-T": 115,
  "#72": 138,
  "#80": 165,
};
export const TRACK_DEFAULT_PRICE_PER_FT = 90;

export const FAMILY_PRICE_PER_SQFT: Record<FamilyId, number> = {
  "excel-700": 88,
  "signature-800": 118,
  crystal: 178,
  vision: 152,
};

export const CONFIG_PRICE_FACTOR: Record<Configuration, number> = {
  individual: 1.08,
  paired: 1.0,
  "continuously-hinged": 1.12,
};

export const OPERATION_PRICE_FACTOR: Record<Operation, number> = {
  manual: 1.0,
  electric: 1.34,
};

export const FINISH_PRICE_FACTOR: Record<string, number> = {
  Vinyl: 1.0,
  Fabric: 1.06,
  Carpet: 1.04,
  "Plastic Laminate": 1.1,
  "Wood Veneer": 1.32,
  "Marker board": 1.18,
  "Tack board": 1.14,
  Steel: 1.08,
  "Uncovered Steel": 0.92,
  Custom: 1.45,
  Clear: 1.0,
  Frosted: 1.18,
  Tinted: 1.22,
  "Custom Print": 1.6,
};

export const CARRIER_PRICE = 295; // per carrier
export const SEAL_PRICE_PER_PANEL = 135; // sweep + top seal
export const HARDWARE_PACK_PER_SYSTEM = 2150;
export const ENGINEERING_FEE = 1850; // per opening
