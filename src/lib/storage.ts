"use client";

import type { Project } from "./store";

const KEY = "moderco-studio:projects:v1";
const ACTIVE_KEY = "moderco-studio:active:v1";

export interface StoredProject {
  id: string;
  name: string;
  client: string;
  updatedAt: number;
  data: Project;
}

function safeRead<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function safeWrite(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

export function listProjects(): StoredProject[] {
  return safeRead<StoredProject[]>(KEY, []).sort(
    (a, b) => b.updatedAt - a.updatedAt,
  );
}

export function saveProject(p: Project) {
  const all = listProjects();
  const idx = all.findIndex((x) => x.id === p.id);
  const entry: StoredProject = {
    id: p.id,
    name: p.name,
    client: p.client,
    updatedAt: Date.now(),
    data: { ...p, updatedAt: Date.now() },
  };
  if (idx >= 0) all[idx] = entry;
  else all.unshift(entry);
  safeWrite(KEY, all);
  safeWrite(ACTIVE_KEY, p.id);
  return entry;
}

export function deleteProject(id: string) {
  const all = listProjects().filter((p) => p.id !== id);
  safeWrite(KEY, all);
}

export function loadProject(id: string): Project | null {
  const all = listProjects();
  return all.find((p) => p.id === id)?.data ?? null;
}

export function getLastActiveId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACTIVE_KEY);
}

export function exportProjectJSON(p: Project): string {
  return JSON.stringify(p, null, 2);
}

export function downloadProject(p: Project) {
  const blob = new Blob([exportProjectJSON(p)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${p.name.replace(/[^\w-]+/g, "_")}.moderco.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function importProjectJSON(text: string): Project | null {
  try {
    const obj = JSON.parse(text);
    if (
      obj &&
      typeof obj === "object" &&
      typeof obj.id === "string" &&
      Array.isArray(obj.walls)
    ) {
      return obj as Project;
    }
    return null;
  } catch {
    return null;
  }
}
