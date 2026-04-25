"use client";

import { useFrame } from "@react-three/fiber";
import { getActiveWall, useConfigurator } from "@/lib/store";
import { FAMILIES, MODELS } from "@/lib/moderco";
import { useMemo, useRef } from "react";
import * as THREE from "three";

interface PanelLayout {
  index: number;
  closedX: number;
  stackedX: number;
  stackedRotY: number;
  stackedZ: number;
}

const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export function PanelTrain() {
  const wall = useConfigurator(getActiveWall);
  const updateActiveWall = useConfigurator((s) => s.updateActiveWall);
  const model = MODELS[wall.modelId];
  const family = FAMILIES[model.family];

  const room = wall.room;
  const stack = wall.stack;
  const openProgress = wall.openProgress;
  const finish = wall.finish;
  const panelWidthIn = wall.panelWidthIn;

  const panelHeight = Math.min(room.heightFt, model.maxHeightIn / 12);
  const panelWidthFt = panelWidthIn / 12;
  const panelThicknessFt = model.thicknessIn / 12;
  const isContinuous = model.configuration === "continuously-hinged";

  const layouts: PanelLayout[] = useMemo(() => {
    const widthFt = room.widthFt;
    const count = Math.ceil(widthFt / panelWidthFt);
    const arr: PanelLayout[] = [];
    const stackSign =
      stack === "right" || stack === "right-pocket"
        ? 1
        : stack === "left" || stack === "left-pocket"
          ? -1
          : 0;

    if (stack === "center") {
      for (let i = 0; i < count; i++) {
        const closedX = -widthFt / 2 + (i + 0.5) * panelWidthFt;
        const goesRight = i >= count / 2;
        const localIdx = goesRight ? i - Math.floor(count / 2) : Math.ceil(count / 2) - 1 - i;
        const sign = goesRight ? 1 : -1;
        const stackedX = sign * (widthFt / 2 + 0.4 + localIdx * panelThicknessFt);
        arr.push({
          index: i,
          closedX,
          stackedX,
          stackedRotY: sign * (Math.PI / 2),
          stackedZ: -0.05 - localIdx * 0.012,
        });
      }
      return arr;
    }

    for (let i = 0; i < count; i++) {
      const closedX = -widthFt / 2 + (i + 0.5) * panelWidthFt;
      const localIdx = stackSign > 0 ? count - 1 - i : i;
      const stackedX = stackSign * (widthFt / 2 + 0.4 + localIdx * panelThicknessFt);
      arr.push({
        index: i,
        closedX,
        stackedX,
        stackedRotY: stackSign * (Math.PI / 2),
        stackedZ: -0.05 - localIdx * 0.012,
      });
    }
    return arr;
  }, [room.widthFt, panelWidthFt, panelThicknessFt, stack]);

  const material = useMemo(() => {
    const accent = new THREE.Color(family.accent);
    if (model.isGlass || ["Clear", "Frosted", "Tinted", "Custom Print"].includes(finish)) {
      return new THREE.MeshPhysicalMaterial({
        color: finish === "Tinted" ? "#7c8a99" : finish === "Frosted" ? "#dde7ec" : "#cfe2ec",
        roughness: finish === "Frosted" ? 0.5 : 0.05,
        metalness: 0.0,
        transmission: finish === "Clear" ? 0.92 : finish === "Frosted" ? 0.55 : 0.7,
        thickness: 0.4,
        ior: 1.45,
        transparent: true,
        opacity: finish === "Clear" ? 0.55 : 0.85,
      });
    }
    if (finish === "Wood Veneer") {
      return new THREE.MeshStandardMaterial({
        color: "#7d5a3a",
        roughness: 0.55,
        metalness: 0.05,
      });
    }
    if (finish === "Marker board") {
      return new THREE.MeshStandardMaterial({
        color: "#f5f6f4",
        roughness: 0.18,
        metalness: 0.05,
      });
    }
    if (finish === "Plastic Laminate") {
      return new THREE.MeshStandardMaterial({
        color: "#d8d2c7",
        roughness: 0.35,
        metalness: 0.15,
      });
    }
    if (finish === "Steel" || finish === "Uncovered Steel") {
      return new THREE.MeshStandardMaterial({
        color: "#9aa1a8",
        roughness: 0.42,
        metalness: 0.7,
      });
    }
    if (finish === "Carpet" || finish === "Tack board") {
      return new THREE.MeshStandardMaterial({
        color: accent.clone().multiplyScalar(0.85),
        roughness: 0.95,
        metalness: 0.0,
      });
    }
    return new THREE.MeshStandardMaterial({
      color: accent,
      roughness: 0.78,
      metalness: 0.05,
    });
  }, [family.accent, finish, model.isGlass]);

  const trimMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#272a30",
        roughness: 0.4,
        metalness: 0.7,
      }),
    [],
  );

  const hingeMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#b6bcc4",
        roughness: 0.32,
        metalness: 0.85,
      }),
    [],
  );

  const groupRef = useRef<THREE.Group>(null);
  const animProgress = useRef(openProgress);

  useFrame((_, dt) => {
    animProgress.current = THREE.MathUtils.damp(
      animProgress.current,
      openProgress,
      6,
      dt,
    );
    if (Math.abs(animProgress.current - openProgress) > 0.001) {
      // keep store in sync for animation cycle (writes without re-render thrash because zustand)
    }

    if (!groupRef.current) return;

    groupRef.current.children.forEach((child, i) => {
      const layout = layouts[i];
      if (!layout) return;

      // Continuous hinged: all panels move together as a chain.
      const stagger = isContinuous ? 0 : 0.35;
      const startOffset = (i / Math.max(1, layouts.length - 1)) * stagger;
      const local = THREE.MathUtils.clamp(
        (animProgress.current - startOffset) / (1 - stagger),
        0,
        1,
      );
      const localT = easeInOutCubic(local);

      const x = THREE.MathUtils.lerp(layout.closedX, layout.stackedX, localT);
      const z = THREE.MathUtils.lerp(0, layout.stackedZ, localT);
      const rotY = THREE.MathUtils.lerp(0, layout.stackedRotY, localT);

      child.position.x = x;
      child.position.z = z;
      child.rotation.y = rotY;

      const transit = 4 * local * (1 - local);
      child.position.y = panelHeight / 2 + transit * 0.025;

      const mesh = child.children[0] as THREE.Mesh | undefined;
      if (mesh) {
        const m = mesh.material as THREE.MeshStandardMaterial;
        if (m.emissive) {
          const target = transit > 0.02 ? 0.04 : 0;
          m.emissive = new THREE.Color(family.accent);
          m.emissiveIntensity = THREE.MathUtils.damp(
            m.emissiveIntensity ?? 0,
            target,
            5,
            dt,
          );
        }
      }
    });
  });

  // Push the smoothed value back to the store so PDF snapshots/state reflect target.
  void updateActiveWall;

  return (
    <group ref={groupRef}>
      {layouts.map((layout) => {
        const isLeader = layout.index === 0;
        const isTrailer = layout.index === layouts.length - 1;
        return (
          <group key={layout.index} position={[layout.closedX, panelHeight / 2, 0]}>
            {/* Main panel face */}
            <mesh castShadow receiveShadow material={material}>
              <boxGeometry
                args={[panelWidthFt - 0.02, panelHeight - 0.04, panelThicknessFt]}
              />
            </mesh>

            {/* Top trim */}
            <mesh position={[0, panelHeight / 2 - 0.02, 0]} material={trimMat} castShadow>
              <boxGeometry args={[panelWidthFt - 0.02, 0.06, panelThicknessFt + 0.005]} />
            </mesh>

            {/* Bottom seal/sweep */}
            <mesh position={[0, -panelHeight / 2 + 0.04, 0]} material={trimMat} castShadow>
              <boxGeometry args={[panelWidthFt - 0.02, 0.08, panelThicknessFt + 0.01]} />
            </mesh>

            {/* Edge reveals */}
            <mesh position={[panelWidthFt / 2 - 0.012, 0, 0]} material={trimMat}>
              <boxGeometry args={[0.012, panelHeight - 0.06, panelThicknessFt + 0.002]} />
            </mesh>
            <mesh position={[-panelWidthFt / 2 + 0.012, 0, 0]} material={trimMat}>
              <boxGeometry args={[0.012, panelHeight - 0.06, panelThicknessFt + 0.002]} />
            </mesh>

            {/* Hinge plates (between panels) — skip on the very last panel */}
            {!isTrailer && (
              <>
                <mesh
                  position={[panelWidthFt / 2 - 0.005, panelHeight / 4, panelThicknessFt / 2 + 0.006]}
                  material={hingeMat}
                  castShadow
                >
                  <boxGeometry args={[0.025, 0.18, 0.05]} />
                </mesh>
                <mesh
                  position={[panelWidthFt / 2 - 0.005, -panelHeight / 4, panelThicknessFt / 2 + 0.006]}
                  material={hingeMat}
                  castShadow
                >
                  <boxGeometry args={[0.025, 0.18, 0.05]} />
                </mesh>
              </>
            )}

            {/* Carrier puck above panel (visible when stacked, hidden up the track normally) */}
            <mesh
              position={[0, panelHeight / 2 + 0.18, 0]}
              material={hingeMat}
              castShadow
            >
              <cylinderGeometry args={[0.06, 0.06, 0.18, 16]} />
            </mesh>

            {/* Pull handle for leader/trailer panels */}
            {(isLeader || isTrailer) && (
              <>
                <mesh
                  position={[
                    isLeader ? -panelWidthFt / 2 + 0.18 : panelWidthFt / 2 - 0.18,
                    0,
                    panelThicknessFt / 2 + 0.012,
                  ]}
                  material={trimMat}
                  castShadow
                >
                  <boxGeometry args={[0.05, 1.2, 0.04]} />
                </mesh>
                {/* Lock cylinder above handle */}
                <mesh
                  position={[
                    isLeader ? -panelWidthFt / 2 + 0.18 : panelWidthFt / 2 - 0.18,
                    0.7,
                    panelThicknessFt / 2 + 0.018,
                  ]}
                  material={hingeMat}
                >
                  <cylinderGeometry args={[0.025, 0.025, 0.04, 16]} />
                </mesh>
              </>
            )}

            {/* Glass interlayer line for glass panels */}
            {model.isGlass && (
              <mesh position={[0, 0, 0]}>
                <boxGeometry args={[panelWidthFt - 0.04, panelHeight - 0.06, 0.01]} />
                <meshStandardMaterial color="#5b6a78" transparent opacity={0.18} />
              </mesh>
            )}
          </group>
        );
      })}
    </group>
  );
}
