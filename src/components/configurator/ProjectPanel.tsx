"use client";

import { useConfigurator, getActiveWall } from "@/lib/store";
import { motion, AnimatePresence } from "framer-motion";
import {
  Copy,
  FolderOpen,
  Layers3,
  Plus,
  Trash2,
  Pencil,
  Building2,
} from "lucide-react";
import { MODELS } from "@/lib/moderco";
import { useState } from "react";

export function ProjectPanel() {
  const project = useConfigurator((s) => s.project);
  const activeId = project.activeWallId;
  const setActive = useConfigurator((s) => s.setActiveWall);
  const add = useConfigurator((s) => s.addWall);
  const dup = useConfigurator((s) => s.duplicateWall);
  const remove = useConfigurator((s) => s.removeWall);
  const rename = useConfigurator((s) => s.renameWall);
  const setMeta = useConfigurator((s) => s.setProjectMeta);
  const setUI = useConfigurator((s) => s.setUI);

  const [editing, setEditing] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");

  return (
    <div className="space-y-5">
      {/* Project meta */}
      <div className="space-y-2.5">
        <Field label="Project Name" icon={<Building2 className="size-3.5" />}>
          <input
            value={project.name}
            onChange={(e) => setMeta({ name: e.target.value })}
            className="w-full bg-transparent text-[13.5px] font-semibold focus:outline-none"
          />
        </Field>
        <Field label="Client">
          <input
            value={project.client}
            onChange={(e) => setMeta({ client: e.target.value })}
            className="w-full bg-transparent text-[13px] focus:outline-none"
          />
        </Field>
        <Field label="Location">
          <input
            value={project.location}
            placeholder="City, region"
            onChange={(e) => setMeta({ location: e.target.value })}
            className="w-full bg-transparent text-[13px] focus:outline-none placeholder:text-[var(--color-fg-dim)]"
          />
        </Field>
      </div>

      {/* Walls list */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--color-fg-muted)] font-semibold flex items-center gap-1.5">
            <Layers3 className="size-3.5" /> Walls in project
          </h3>
          <button
            onClick={() => add()}
            className="btn-ghost h-7 px-2 rounded-md text-[11.5px] flex items-center gap-1"
          >
            <Plus className="size-3" /> Add
          </button>
        </div>

        <div className="space-y-1.5">
          <AnimatePresence initial={false}>
            {project.walls.map((wall) => {
              const model = MODELS[wall.modelId];
              const isActive = wall.id === activeId;
              const isEditing = editing === wall.id;

              return (
                <motion.div
                  key={wall.id}
                  layout
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.18 }}
                  onClick={() => !isEditing && setActive(wall.id)}
                  className={`group relative cursor-pointer rounded-lg border transition-all px-3 py-2.5 ${
                    isActive
                      ? "border-[var(--color-accent)] bg-[color-mix(in_oklch,var(--color-accent)_8%,transparent)]"
                      : "border-[var(--color-border)] bg-[var(--color-surface)]/60 hover:border-[var(--color-border-strong)]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className="size-2 rounded-full shrink-0"
                      style={{
                        background: isActive ? "var(--color-accent)" : "var(--color-fg-dim)",
                        boxShadow: isActive ? "0 0 8px var(--color-accent)" : undefined,
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      {isEditing ? (
                        <input
                          autoFocus
                          value={draftName}
                          onChange={(e) => setDraftName(e.target.value)}
                          onBlur={() => {
                            if (draftName.trim()) rename(wall.id, draftName.trim());
                            setEditing(null);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              if (draftName.trim()) rename(wall.id, draftName.trim());
                              setEditing(null);
                            }
                            if (e.key === "Escape") setEditing(null);
                          }}
                          className="w-full bg-[var(--color-surface-2)] rounded px-2 py-0.5 text-[12.5px] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
                        />
                      ) : (
                        <div className="text-[12.5px] font-medium truncate">{wall.name}</div>
                      )}
                      <div className="text-[10.5px] text-[var(--color-fg-dim)] truncate">
                        {model.name} · {wall.room.widthFt}′ × {wall.room.heightFt}′
                      </div>
                    </div>

                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <IconButton
                        title="Rename"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDraftName(wall.name);
                          setEditing(wall.id);
                        }}
                      >
                        <Pencil className="size-3" />
                      </IconButton>
                      <IconButton
                        title="Duplicate"
                        onClick={(e) => {
                          e.stopPropagation();
                          dup(wall.id);
                        }}
                      >
                        <Copy className="size-3" />
                      </IconButton>
                      <IconButton
                        title="Delete"
                        onClick={(e) => {
                          e.stopPropagation();
                          remove(wall.id);
                        }}
                      >
                        <Trash2 className="size-3" />
                      </IconButton>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      <button
        onClick={() => setUI("projectsManagerOpen", true)}
        className="btn-ghost w-full h-9 rounded-lg flex items-center justify-center gap-2 text-[12.5px]"
      >
        <FolderOpen className="size-3.5" /> Open Projects Manager
      </button>
    </div>
  );
}

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-[0.14em] text-[var(--color-fg-dim)] mb-1">
        {icon} {label}
      </div>
      <div className="px-2.5 py-1.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]/60 focus-within:border-[var(--color-accent)] transition-colors">
        {children}
      </div>
    </label>
  );
}

function IconButton({
  children,
  onClick,
  title,
}: {
  children: React.ReactNode;
  onClick: (e: React.MouseEvent) => void;
  title: string;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="size-6 grid place-items-center rounded-md text-[var(--color-fg-dim)] hover:text-[var(--color-fg)] hover:bg-[var(--color-surface-2)] transition-colors"
    >
      {children}
    </button>
  );
}

// helper to silence lint for unused getActiveWall import in some builds
void getActiveWall;
