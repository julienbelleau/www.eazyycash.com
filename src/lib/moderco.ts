// Moderco operable partition catalog (representative engineering data).
// Numbers are based on publicly available product literature and are intended
// for layout/takeoff estimation in this configurator.

export type SeriesId =
  | "911"
  | "922"
  | "933"
  | "lexicon-1A"
  | "lexicon-1B"
  | "encore";

export interface Series {
  id: SeriesId;
  name: string;
  family: "Acoustical" | "Lexicon" | "Glass";
  stcRange: [number, number];
  panelThicknessIn: number; // panel thickness
  weightPsf: number; // pounds per square foot
  maxHeightIn: number; // ft × 12
  description: string;
  accent: string; // ui accent
  finishes: string[];
}

export const SERIES: Record<SeriesId, Series> = {
  "911": {
    id: "911",
    name: "Series 911",
    family: "Acoustical",
    stcRange: [45, 50],
    panelThicknessIn: 3,
    weightPsf: 7.5,
    maxHeightIn: 14 * 12,
    description:
      "Entry-level acoustic operable partition. Ideal for classrooms and meeting rooms.",
    accent: "oklch(0.78 0.16 75)",
    finishes: ["Vinyl", "Fabric", "Markerboard", "HPL"],
  },
  "922": {
    id: "922",
    name: "Series 922",
    family: "Acoustical",
    stcRange: [50, 53],
    panelThicknessIn: 3.5,
    weightPsf: 9,
    maxHeightIn: 18 * 12,
    description:
      "Workhorse acoustical wall for hotels, conference centers and ballrooms.",
    accent: "oklch(0.74 0.16 60)",
    finishes: ["Vinyl", "Fabric", "Veneer", "HPL", "Tackable"],
  },
  "933": {
    id: "933",
    name: "Series 933",
    family: "Acoustical",
    stcRange: [54, 56],
    panelThicknessIn: 4,
    weightPsf: 11,
    maxHeightIn: 24 * 12,
    description:
      "High-STC division for ballrooms and performance spaces requiring premium isolation.",
    accent: "oklch(0.7 0.16 45)",
    finishes: ["Fabric", "Veneer", "Custom Millwork", "Stretched Fabric"],
  },
  "lexicon-1A": {
    id: "lexicon-1A",
    name: "Lexicon 1A",
    family: "Lexicon",
    stcRange: [38, 42],
    panelThicknessIn: 2.75,
    weightPsf: 6,
    maxHeightIn: 12 * 12,
    description:
      "Continuously hinged accordion-style partition. Quick close, single-track.",
    accent: "oklch(0.78 0.14 200)",
    finishes: ["Vinyl", "Fabric", "Markerboard"],
  },
  "lexicon-1B": {
    id: "lexicon-1B",
    name: "Lexicon 1B",
    family: "Lexicon",
    stcRange: [42, 46],
    panelThicknessIn: 3,
    weightPsf: 7,
    maxHeightIn: 14 * 12,
    description:
      "Continuously hinged premium acoustic — fast deployment, excellent ratings.",
    accent: "oklch(0.74 0.14 215)",
    finishes: ["Vinyl", "Fabric", "Markerboard", "HPL"],
  },
  encore: {
    id: "encore",
    name: "Encore Glass",
    family: "Glass",
    stcRange: [36, 40],
    panelThicknessIn: 2.5,
    weightPsf: 12,
    maxHeightIn: 12 * 12,
    description:
      "Frameless glass operable wall — natural light with flexible division.",
    accent: "oklch(0.86 0.07 200)",
    finishes: ["Clear", "Frosted", "Tinted", "Custom Print"],
  },
};

export const SERIES_LIST: Series[] = Object.values(SERIES);

// --- Panel widths (typical Moderco range, in inches) ---
export const MIN_PANEL_WIDTH_IN = 24;
export const MAX_PANEL_WIDTH_IN = 48;
export const DEFAULT_PANEL_WIDTH_IN = 42;

// --- Configurations ---
export type PanelConfig = "paired" | "individual" | "continuously-hinged";

export const CONFIGS: { id: PanelConfig; label: string; description: string }[] =
  [
    {
      id: "paired",
      label: "Paired",
      description: "Hinged pairs — fewer carriers, fast stacking.",
    },
    {
      id: "individual",
      label: "Individual",
      description: "Each panel on its own carrier — flexible layouts.",
    },
    {
      id: "continuously-hinged",
      label: "Continuously Hinged",
      description: "Accordion-style continuous hinge (Lexicon).",
    },
  ];

// --- Stack types ---
export type StackType = "left" | "right" | "center" | "left-pocket" | "right-pocket";

export const STACK_TYPES: { id: StackType; label: string }[] = [
  { id: "left", label: "Left Stack" },
  { id: "right", label: "Right Stack" },
  { id: "center", label: "Center Split" },
  { id: "left-pocket", label: "Left Pocket" },
  { id: "right-pocket", label: "Right Pocket" },
];

// --- Track / hardware ---
export const TRACK_PRICE_PER_FT = 78; // $/ft of suspended track
export const PANEL_PRICE_PER_SQFT = 95; // base $/sqft, multiplier per series below
export const SERIES_PRICE_MULTIPLIER: Record<SeriesId, number> = {
  "911": 1.0,
  "922": 1.18,
  "933": 1.42,
  "lexicon-1A": 0.9,
  "lexicon-1B": 1.08,
  encore: 1.85,
};

export const CARRIER_PRICE = 280; // per carrier
export const SEAL_PRICE_PER_PANEL = 120; // per-panel seals + sweeps
export const HARDWARE_PACK_PER_SYSTEM = 1850; // base per system

// --- Operation types ---
export type Operation = "manual" | "power-assist" | "automatic";
export const OPERATION_PRICE_FACTOR: Record<Operation, number> = {
  manual: 1.0,
  "power-assist": 1.18,
  automatic: 1.45,
};
