"use client";

import { useConfigurator, getActiveWall } from "@/lib/store";
import { useMemo } from "react";

export function Track() {
  const wall = useConfigurator(getActiveWall);
  const room = wall.room;
  const stack = wall.stack;

  const trackY = room.heightFt - 0.18;
  const stackRun = 4;
  const length = room.widthFt + stackRun + 1.5;

  const offset = useMemo(() => {
    if (stack === "right" || stack === "right-pocket") return -stackRun / 2;
    if (stack === "left" || stack === "left-pocket") return stackRun / 2;
    return 0;
  }, [stack]);

  return (
    <group position={[offset, trackY, 0]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[length, 0.18, 0.55]} />
        <meshStandardMaterial color="#cfd2d6" metalness={0.85} roughness={0.28} />
      </mesh>
      <mesh position={[0, -0.09, 0]} castShadow>
        <boxGeometry args={[length, 0.04, 0.18]} />
        <meshStandardMaterial color="#1a1d22" roughness={0.4} metalness={0.2} />
      </mesh>
      {Array.from({ length: Math.ceil(length / 4) + 1 }).map((_, i) => {
        const x = -length / 2 + i * 4;
        return (
          <mesh key={i} position={[x, 0.6, 0]} castShadow>
            <cylinderGeometry args={[0.035, 0.035, 1.2, 12]} />
            <meshStandardMaterial color="#9ea3ab" metalness={0.8} roughness={0.4} />
          </mesh>
        );
      })}
      <mesh position={[-length / 2, 0, 0]}>
        <boxGeometry args={[0.04, 0.22, 0.6]} />
        <meshStandardMaterial color="#6c7079" metalness={0.6} roughness={0.4} />
      </mesh>
      <mesh position={[length / 2, 0, 0]}>
        <boxGeometry args={[0.04, 0.22, 0.6]} />
        <meshStandardMaterial color="#6c7079" metalness={0.6} roughness={0.4} />
      </mesh>
    </group>
  );
}
