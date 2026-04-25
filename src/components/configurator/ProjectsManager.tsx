"use client";

import { useConfigurator } from "@/lib/store";
import {
  deleteProject,
  importProjectJSON,
  listProjects,
  loadProject,
  saveProject,
  StoredProject,
} from "@/lib/storage";
import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  FileJson,
  FilePlus,
  FolderOpen,
  Save,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

export function ProjectsManager() {
  const open = useConfigurator((s) => s.projectsManagerOpen);
  const setUI = useConfigurator((s) => s.setUI);
  const project = useConfigurator((s) => s.project);
  const loadProjectAction = useConfigurator((s) => s.loadProject);
  const newProject = useConfigurator((s) => s.newProject);

  const [refreshKey, setRefreshKey] = useState(0);
  const items: StoredProject[] = useMemo(() => {
    void refreshKey; // bump to force re-fetch from localStorage
    return open ? listProjects() : [];
  }, [open, refreshKey]);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () => setRefreshKey((k) => k + 1);

  const onSaveCurrent = () => {
    saveProject(project);
    refresh();
  };

  const onLoad = (id: string) => {
    const p = loadProject(id);
    if (p) {
      loadProjectAction(p);
      setUI("projectsManagerOpen", false);
    }
  };

  const onDelete = (id: string) => {
    deleteProject(id);
    refresh();
  };

  const onNew = () => {
    newProject(`Untitled ${new Date().toLocaleDateString("en-CA")}`);
    setUI("projectsManagerOpen", false);
  };

  const onImportFile = async (file: File) => {
    const text = await file.text();
    const parsed = importProjectJSON(text);
    if (parsed) {
      loadProjectAction(parsed);
      saveProject(parsed);
      refresh();
      setUI("projectsManagerOpen", false);
    } else {
      alert("Invalid project file.");
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 grid place-items-center p-6 bg-black/60 backdrop-blur-sm"
          onClick={() => setUI("projectsManagerOpen", false)}
        >
          <motion.div
            initial={{ scale: 0.96, y: 8, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.96, y: 8, opacity: 0 }}
            transition={{ type: "spring", stiffness: 280, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl rounded-2xl surface overflow-hidden"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="grid place-items-center size-9 rounded-lg bg-[var(--color-surface-2)] text-[var(--color-accent)]">
                  <FolderOpen className="size-4" />
                </span>
                <div>
                  <div className="text-[15px] font-semibold">Projects</div>
                  <div className="text-[11px] text-[var(--color-fg-dim)]">
                    Saved locally in your browser
                  </div>
                </div>
              </div>
              <button
                onClick={() => setUI("projectsManagerOpen", false)}
                className="size-8 grid place-items-center rounded-lg btn-ghost"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Actions */}
            <div className="px-5 py-3 border-b border-[var(--color-border)] flex flex-wrap items-center gap-2">
              <button onClick={onSaveCurrent} className="btn-primary h-9 px-3 rounded-lg flex items-center gap-1.5 text-[12.5px]">
                <Save className="size-3.5" /> Save Current
              </button>
              <button onClick={onNew} className="btn-ghost h-9 px-3 rounded-lg flex items-center gap-1.5 text-[12.5px]">
                <FilePlus className="size-3.5" /> New Project
              </button>
              <button
                onClick={() => fileRef.current?.click()}
                className="btn-ghost h-9 px-3 rounded-lg flex items-center gap-1.5 text-[12.5px]"
              >
                <Upload className="size-3.5" /> Import JSON
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onImportFile(f);
                  e.currentTarget.value = "";
                }}
              />
            </div>

            {/* List */}
            <div className="max-h-[60vh] overflow-y-auto p-5 space-y-2">
              {items.length === 0 ? (
                <div className="text-center py-12">
                  <FileJson className="size-10 mx-auto text-[var(--color-fg-dim)]" />
                  <div className="mt-3 text-[13px] text-[var(--color-fg-muted)]">
                    No saved projects yet.
                  </div>
                  <div className="text-[11.5px] text-[var(--color-fg-dim)] mt-1">
                    Click <span className="kbd">Save Current</span> to store this project.
                  </div>
                </div>
              ) : (
                items.map((p) => (
                  <motion.div
                    key={p.id}
                    layout
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="flex items-center gap-3 p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/60 hover:border-[var(--color-border-strong)] transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-semibold truncate">{p.name}</div>
                      <div className="text-[11px] text-[var(--color-fg-dim)] flex items-center gap-2 mt-0.5">
                        <span>{p.client}</span>
                        <span>·</span>
                        <Calendar className="size-3" />
                        <span>{new Date(p.updatedAt).toLocaleString()}</span>
                        <span>·</span>
                        <span>{p.data.walls.length} wall{p.data.walls.length === 1 ? "" : "s"}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => onLoad(p.id)}
                      className="btn-primary h-8 px-3 rounded-lg text-[12px]"
                    >
                      Load
                    </button>
                    <button
                      onClick={() => onDelete(p.id)}
                      className="size-8 grid place-items-center rounded-lg btn-ghost text-[var(--color-danger)]"
                      title="Delete"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </motion.div>
                ))
              )}
            </div>

            <div className="px-5 py-3 border-t border-[var(--color-border)] text-[10.5px] text-[var(--color-fg-dim)]">
              Projects are stored in browser localStorage. Use Import/Export JSON to move
              between devices, or hook a backend to sync across users.
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
