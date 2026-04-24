"use client";

import { useConfigurator } from "@/lib/store";
import * as THREE from "three";
import { useMemo } from "react";

export function Room() {
  const room = useConfigurator((s) => s.room);

  const { w, d, h } = useMemo(
    () => ({ w: room.widthFt, d: room.depthFt, h: room.heightFt }),
    [room.widthFt, room.depthFt, room.heightFt],
  );

  // Floor — light wood/concrete look.
  const floorMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#a4937c",
        roughness: 0.78,
        metalness: 0.05,
      }),
    [],
  );

  // Side walls — warm off-white plaster.
  const wallMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#e7e2da",
        roughness: 0.92,
        metalness: 0.0,
        side: THREE.FrontSide,
      }),
    [],
  );

  // Ceiling — slightly cooler, less reflective.
  const ceilMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#dcd9d2",
        roughness: 0.95,
        metalness: 0.0,
      }),
    [],
  );

  // Baseboard accent.
  const baseMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#4a4036",
        roughness: 0.6,
        metalness: 0.1,
      }),
    [],
  );

  return (
    <group>
      {/* Floor */}
      <mesh
        receiveShadow
        position={[0, 0, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        material={floorMat}
      >
        <planeGeometry args={[w + 16, d + 16]} />
      </mesh>

      {/* Floor plank pattern overlay */}
      <mesh
        position={[0, 0.005, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[w, d]} />
        <meshStandardMaterial
          color="#b39e84"
          roughness={0.7}
          metalness={0.05}
          transparent
          opacity={0.85}
        />
      </mesh>

      {/* Back wall */}
      <mesh
        receiveShadow
        position={[0, h / 2, -d / 2]}
        material={wallMat}
      >
        <planeGeometry args={[w, h]} />
      </mesh>

      {/* Front wall (clipped — open viewing) */}
      <mesh
        position={[0, h / 2, d / 2]}
        rotation={[0, Math.PI, 0]}
        material={wallMat}
      >
        <planeGeometry args={[w, h]} />
      </mesh>

      {/* Left wall */}
      <mesh
        receiveShadow
        position={[-w / 2, h / 2, 0]}
        rotation={[0, Math.PI / 2, 0]}
        material={wallMat}
      >
        <planeGeometry args={[d, h]} />
      </mesh>

      {/* Right wall */}
      <mesh
        receiveShadow
        position={[w / 2, h / 2, 0]}
        rotation={[0, -Math.PI / 2, 0]}
        material={wallMat}
      >
        <planeGeometry args={[d, h]} />
      </mesh>

      {/* Ceiling */}
      <mesh
        receiveShadow
        position={[0, h, 0]}
        rotation={[Math.PI / 2, 0, 0]}
        material={ceilMat}
      >
        <planeGeometry args={[w, d]} />
      </mesh>

      {/* Baseboards */}
      <mesh position={[0, 0.25, -d / 2 + 0.02]} material={baseMat} castShadow>
        <boxGeometry args={[w, 0.5, 0.04]} />
      </mesh>
      <mesh position={[-w / 2 + 0.02, 0.25, 0]} material={baseMat} castShadow>
        <boxGeometry args={[0.04, 0.5, d]} />
      </mesh>
      <mesh position={[w / 2 - 0.02, 0.25, 0]} material={baseMat} castShadow>
        <boxGeometry args={[0.04, 0.5, d]} />
      </mesh>

      {/* Soft ceiling cove light */}
      <pointLight
        position={[0, h - 0.4, 0]}
        intensity={0.6}
        distance={Math.max(w, d) * 1.2}
        color="#fff1d6"
      />
    </group>
  );
}
