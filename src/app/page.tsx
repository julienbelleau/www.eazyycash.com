"use client";

import { ConfigSidebar } from "@/components/configurator/ConfigSidebar";
import { Navbar } from "@/components/configurator/Navbar";
import { TakeoffPanel } from "@/components/configurator/TakeoffPanel";
import { Viewport } from "@/components/configurator/Viewport";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 grid gap-3 p-3 grid-cols-1 grid-rows-[auto_1fr_auto] lg:grid-cols-[340px_minmax(0,1fr)_360px] lg:grid-rows-1">
        <ConfigSidebar />
        <div className="min-h-[55vh] lg:min-h-0 flex">
          <Viewport />
        </div>
        <TakeoffPanel />
      </main>
    </div>
  );
}
