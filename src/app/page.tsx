"use client";

import { ConfigSidebar } from "@/components/configurator/ConfigSidebar";
import { Navbar } from "@/components/configurator/Navbar";
import { ProjectsManager } from "@/components/configurator/ProjectsManager";
import { TakeoffPanel } from "@/components/configurator/TakeoffPanel";
import { Viewport } from "@/components/configurator/Viewport";
import { useEffect } from "react";
import { useConfigurator } from "@/lib/store";
import { getLastActiveId, loadProject } from "@/lib/storage";

export default function Home() {
  const loadProjectAction = useConfigurator((s) => s.loadProject);

  useEffect(() => {
    const id = getLastActiveId();
    if (id) {
      const p = loadProject(id);
      if (p) loadProjectAction(p);
    }
  }, [loadProjectAction]);

  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 grid gap-3 p-3 grid-cols-1 grid-rows-[auto_1fr_auto] lg:grid-cols-[360px_minmax(0,1fr)_380px] lg:grid-rows-1">
        <ConfigSidebar />
        <div className="min-h-[55vh] lg:min-h-0 flex">
          <Viewport />
        </div>
        <TakeoffPanel />
      </main>
      <ProjectsManager />
    </div>
  );
}
