"use client";

import { Html, Line } from "@react-three/drei";
import { getActiveWall, useConfigurator } from "@/lib/store";
import { inchesToFeetInches } from "@/lib/utils";

export function DimensionLabels() {
  const wall = useConfigurator(getActiveWall);
  const showDimensions = useConfigurator((s) => s.showDimensions);

  if (!showDimensions) return null;

  const w = wall.room.widthFt;
  const d = wall.room.depthFt;
  const h = wall.room.heightFt;
  const yLine = 0.05;
  const offset = 0.7;

  return (
    <group>
      <Line
        points={[
          [-w / 2, yLine, d / 2 + offset],
          [w / 2, yLine, d / 2 + offset],
        ]}
        color="#f1c27d"
        lineWidth={1.5}
      />
      <Line points={[[-w / 2, yLine, d / 2 + offset - 0.15], [-w / 2, yLine, d / 2 + offset + 0.15]]} color="#f1c27d" lineWidth={1.5} />
      <Line points={[[w / 2, yLine, d / 2 + offset - 0.15], [w / 2, yLine, d / 2 + offset + 0.15]]} color="#f1c27d" lineWidth={1.5} />
      <Html position={[0, yLine, d / 2 + offset + 0.6]} center distanceFactor={14}>
        <div className="px-2 py-0.5 rounded-md bg-amber-300/90 text-zinc-900 font-medium text-[12px] tracking-tight whitespace-nowrap shadow-md">
          W {inchesToFeetInches(w * 12)}
        </div>
      </Html>

      <Line points={[[w / 2 + offset, yLine, -d / 2], [w / 2 + offset, yLine, d / 2]]} color="#9bd1ff" lineWidth={1.5} />
      <Html position={[w / 2 + offset + 0.6, yLine, 0]} center distanceFactor={14}>
        <div className="px-2 py-0.5 rounded-md bg-sky-300/90 text-zinc-900 font-medium text-[12px] tracking-tight whitespace-nowrap shadow-md">
          D {inchesToFeetInches(d * 12)}
        </div>
      </Html>

      <Line points={[[-w / 2 - offset, 0, -d / 2], [-w / 2 - offset, h, -d / 2]]} color="#c4f08e" lineWidth={1.5} />
      <Html position={[-w / 2 - offset - 0.4, h / 2, -d / 2]} center distanceFactor={14}>
        <div className="px-2 py-0.5 rounded-md bg-lime-300/90 text-zinc-900 font-medium text-[12px] tracking-tight whitespace-nowrap shadow-md">
          H {inchesToFeetInches(h * 12)}
        </div>
      </Html>
    </group>
  );
}
