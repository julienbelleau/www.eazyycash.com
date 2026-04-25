"use client";

import { create } from "zustand";
import { nanoid } from "nanoid";
import { ModelId, MODELS, StackType } from "./moderco";

export interface RoomDimensions {
  widthFt: number;
  depthFt: number;
  heightFt: number;
}

export type ViewMode = "3d" | "2d" | "split";

export interface Wall {
  id: string;
  name: string;
  modelId: ModelId;
  panelWidthIn: number;
  stack: StackType;
  finish: string;
  trackOption: string;
  sealOption: string;
  room: RoomDimensions;
  // animation/preview state — local to wall
  openProgress: number; // 0 closed → 1 stacked
}

export interface Project {
  id: string;
  name: string;
  client: string;
  location: string;
  createdAt: number;
  updatedAt: number;
  walls: Wall[];
  activeWallId: string;
}

export interface ConfiguratorState {
  project: Project;

  // Global UI
  viewMode: ViewMode;
  isAnimating: boolean;
  showDimensions: boolean;
  showGrid: boolean;
  cameraPreset: "iso" | "front" | "top" | "stack";
  projectsManagerOpen: boolean;

  // actions
  setProjectMeta(partial: Partial<Pick<Project, "name" | "client" | "location">>): void;
  setActiveWall(id: string): void;
  addWall(): string;
  duplicateWall(id: string): string;
  removeWall(id: string): void;
  renameWall(id: string, name: string): void;
  updateActiveWall<K extends keyof Wall>(key: K, value: Wall[K]): void;
  updateActiveRoom(partial: Partial<RoomDimensions>): void;

  setViewMode(mode: ViewMode): void;
  setUI<K extends "isAnimating" | "showDimensions" | "showGrid" | "cameraPreset" | "projectsManagerOpen">(
    key: K,
    value: ConfiguratorState[K],
  ): void;

  loadProject(p: Project): void;
  newProject(name?: string): void;
  resetActiveWallProgress(): void;
}

function makeWall(modelId: ModelId, name: string): Wall {
  const m = MODELS[modelId];
  return {
    id: nanoid(8),
    name,
    modelId,
    panelWidthIn: Math.round(
      (m.panelWidthRangeIn[0] + m.panelWidthRangeIn[1]) / 2,
    ),
    stack: "left",
    finish: m.finishes[0],
    trackOption: m.trackOptions[0],
    sealOption: m.sealOptions[0],
    room: {
      widthFt: 48,
      depthFt: 36,
      heightFt: Math.min(14, Math.floor(m.maxHeightIn / 12)),
    },
    openProgress: 1,
  };
}

function makeProject(name = "Untitled Project"): Project {
  const now = Date.now();
  const wall = makeWall("sig-842", "Main Wall");
  return {
    id: nanoid(10),
    name,
    client: "New Client",
    location: "",
    createdAt: now,
    updatedAt: now,
    walls: [wall],
    activeWallId: wall.id,
  };
}

const DEFAULT_PROJECT = makeProject("Grand Ballroom — Phase 02");
DEFAULT_PROJECT.client = "Riverside Convention Center";
DEFAULT_PROJECT.location = "Boucherville, QC";

export const useConfigurator = create<ConfiguratorState>((set, get) => ({
  project: DEFAULT_PROJECT,
  viewMode: "3d",
  isAnimating: false,
  showDimensions: true,
  showGrid: true,
  cameraPreset: "iso",
  projectsManagerOpen: false,

  setProjectMeta: (partial) =>
    set((s) => ({
      project: { ...s.project, ...partial, updatedAt: Date.now() },
    })),

  setActiveWall: (id) =>
    set((s) => ({ project: { ...s.project, activeWallId: id } })),

  addWall: () => {
    const wall = makeWall("sig-842", `Wall ${get().project.walls.length + 1}`);
    set((s) => ({
      project: {
        ...s.project,
        walls: [...s.project.walls, wall],
        activeWallId: wall.id,
        updatedAt: Date.now(),
      },
    }));
    return wall.id;
  },

  duplicateWall: (id) => {
    const src = get().project.walls.find((w) => w.id === id);
    if (!src) return id;
    const copy: Wall = { ...src, id: nanoid(8), name: `${src.name} copy` };
    set((s) => ({
      project: {
        ...s.project,
        walls: [...s.project.walls, copy],
        activeWallId: copy.id,
        updatedAt: Date.now(),
      },
    }));
    return copy.id;
  },

  removeWall: (id) => {
    set((s) => {
      const remaining = s.project.walls.filter((w) => w.id !== id);
      if (remaining.length === 0) {
        const w = makeWall("sig-842", "Main Wall");
        return {
          project: {
            ...s.project,
            walls: [w],
            activeWallId: w.id,
            updatedAt: Date.now(),
          },
        };
      }
      const activeId =
        s.project.activeWallId === id ? remaining[0].id : s.project.activeWallId;
      return {
        project: {
          ...s.project,
          walls: remaining,
          activeWallId: activeId,
          updatedAt: Date.now(),
        },
      };
    });
  },

  renameWall: (id, name) =>
    set((s) => ({
      project: {
        ...s.project,
        walls: s.project.walls.map((w) => (w.id === id ? { ...w, name } : w)),
        updatedAt: Date.now(),
      },
    })),

  updateActiveWall: (key, value) =>
    set((s) => ({
      project: {
        ...s.project,
        walls: s.project.walls.map((w) =>
          w.id === s.project.activeWallId ? { ...w, [key]: value } : w,
        ),
        updatedAt: Date.now(),
      },
    })),

  updateActiveRoom: (partial) =>
    set((s) => ({
      project: {
        ...s.project,
        walls: s.project.walls.map((w) =>
          w.id === s.project.activeWallId
            ? { ...w, room: { ...w.room, ...partial } }
            : w,
        ),
        updatedAt: Date.now(),
      },
    })),

  setViewMode: (mode) => set({ viewMode: mode }),
  setUI: (key, value) => set({ [key]: value } as Partial<ConfiguratorState>),

  loadProject: (p) => set({ project: p }),
  newProject: (name) => set({ project: makeProject(name) }),
  resetActiveWallProgress: () =>
    set((s) => ({
      project: {
        ...s.project,
        walls: s.project.walls.map((w) =>
          w.id === s.project.activeWallId ? { ...w, openProgress: 1 } : w,
        ),
      },
    })),
}));

export function getActiveWall(state: ConfiguratorState): Wall {
  return (
    state.project.walls.find((w) => w.id === state.project.activeWallId) ??
    state.project.walls[0]
  );
}
