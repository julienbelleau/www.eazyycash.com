"use client";

import { create } from "zustand";
import {
  DEFAULT_PANEL_WIDTH_IN,
  Operation,
  PanelConfig,
  SeriesId,
  StackType,
} from "./moderco";

export interface RoomDimensions {
  widthFt: number; // along the wall axis (track length)
  depthFt: number; // perpendicular
  heightFt: number; // ceiling height
}

export interface ConfiguratorState {
  // Project
  projectName: string;
  client: string;

  // Geometry
  room: RoomDimensions;

  // System
  series: SeriesId;
  panelWidthIn: number;
  config: PanelConfig;
  stack: StackType;
  operation: Operation;
  finish: string;

  // View / interaction
  openProgress: number; // 0 closed → 1 fully stacked
  isAnimating: boolean;
  showDimensions: boolean;
  showGrid: boolean;
  cameraPreset: "iso" | "front" | "top" | "stack";

  // actions
  set<K extends keyof ConfiguratorState>(key: K, value: ConfiguratorState[K]): void;
  setRoom(partial: Partial<RoomDimensions>): void;
  toggleAnimate(): void;
  reset(): void;
}

const DEFAULTS: Omit<ConfiguratorState, "set" | "setRoom" | "toggleAnimate" | "reset"> = {
  projectName: "Grand Ballroom — Phase 02",
  client: "Riverside Convention Center",
  room: { widthFt: 48, depthFt: 36, heightFt: 14 },
  series: "922",
  panelWidthIn: DEFAULT_PANEL_WIDTH_IN,
  config: "paired",
  stack: "left",
  operation: "manual",
  finish: "Fabric",
  openProgress: 1,
  isAnimating: false,
  showDimensions: true,
  showGrid: true,
  cameraPreset: "iso",
};

export const useConfigurator = create<ConfiguratorState>((set) => ({
  ...DEFAULTS,
  set: (key, value) => set({ [key]: value } as Partial<ConfiguratorState>),
  setRoom: (partial) =>
    set((state) => ({ room: { ...state.room, ...partial } })),
  toggleAnimate: () => set((state) => ({ isAnimating: !state.isAnimating })),
  reset: () => set(DEFAULTS),
}));
