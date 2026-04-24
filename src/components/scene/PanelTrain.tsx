"use client";

import { useFrame } from "@react-three/fiber";
import { useConfigurator } from "@/lib/store";
import { SERIES } from "@/lib/moderco";
import { useMemo, useRef } from "react";
import * as THREE from "three";

interface PanelLayout {
  index: number;
  // closed (deployed) X position (panel centered on this X)
  closedX: number;
  // stacked X position
  stackedX: number;
  // when stacked, panel rotates 90° to align perpendicular
  stackedRotY: number;
  // small Z offset when stacked, panels fan slightly
  stackedZ: number;
}

const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export function PanelTrain() {
  const { room, series, panelWidthIn, stack, openProgress, finish } = useConfigurator(
    (s) => ({
      room: s.room,
      series: s.series,
      panelWidthIn: s.panelWidthIn,
      stack: s.stack,
      openProgress: s.openProgress,
      finish: s.finish,
    }),
  );

  const seriesData = SERIES[series];
  const panelHeight = Math.min(room.heightFt, seriesData.maxHeightIn / 12);
  const panelWidthFt = panelWidthIn / 12;
  const panelThicknessFt = seriesData.panelThicknessIn / 12;

  const layouts: PanelLayout[] = useMemo(() => {
    const widthFt = room.widthFt;
    const count = Math.ceil(widthFt / panelWidthFt);

    const arr: PanelLayout[] = [];

    // Reference: stack pocket position relative to opening center.
    const stackSign =
      stack === "right" || stack === "right-pocket"
        ? 1
        : stack === "left" || stack === "left-pocket"
          ? -1
          : 0;

    if (stack === "center") {
      // Two stacks fan to opposite sides from middle.
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
      // Order in stack: panels nearest to stack pocket go in last.
      const localIdx = stackSign > 0 ? count - 1 - i : i;
      const stackedX =
        stackSign * (widthFt / 2 + 0.4 + localIdx * panelThicknessFt);
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

  // Smoothed animation progress, lerps toward openProgress.
  const animProgress = useRef(openProgress);

  // Material once.
  const material = useMemo(() => {
    const accent = new THREE.Color(seriesData.accent);
    // Different finishes -> different material treatments.
    if (finish === "Veneer" || finish === "Custom Millwork") {
      return new THREE.MeshStandardMaterial({
        color: "#7d5a3a",
        roughness: 0.55,
        metalness: 0.05,
      });
    }
    if (finish === "Markerboard") {
      return new THREE.MeshStandardMaterial({
        color: "#f5f6f4",
        roughness: 0.18,
        metalness: 0.05,
      });
    }
    if (finish === "HPL") {
      return new THREE.MeshStandardMaterial({
        color: "#d8d2c7",
        roughness: 0.35,
        metalness: 0.15,
      });
    }
    if (finish === "Clear" || finish === "Frosted" || finish === "Tinted") {
      return new THREE.MeshPhysicalMaterial({
        color: finish === "Tinted" ? "#7c8a99" : "#cfe2ec",
        roughness: finish === "Frosted" ? 0.35 : 0.05,
        metalness: 0.0,
        transmission: finish === "Clear" ? 0.92 : 0.65,
        thickness: 0.4,
        ior: 1.45,
        transparent: true,
        opacity: finish === "Clear" ? 0.55 : 0.85,
      });
    }
    // Fabric / Vinyl / default — slightly tinted by series accent.
    return new THREE.MeshStandardMaterial({
      color: accent,
      roughness: 0.78,
      metalness: 0.05,
    });
  }, [seriesData.accent, finish]);

  const trimMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#272a30",
        roughness: 0.45,
        metalness: 0.6,
      }),
    [],
  );

  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, dt) => {
    // Smooth lerp to target openProgress for buttery animation.
    animProgress.current = THREE.MathUtils.damp(
      animProgress.current,
      openProgress,
      6,
      dt,
    );

    if (!groupRef.current) return;
    const t = easeInOutCubic(animProgress.current);

    groupRef.current.children.forEach((child, i) => {
      const layout = layouts[i];
      if (!layout) return;

      // Stagger panels: nearest-to-stack moves first.
      const staggerCount = layouts.length;
      const startOffset = (i / Math.max(1, staggerCount - 1)) * 0.35;
      const local = THREE.MathUtils.clamp(
        (animProgress.current - startOffset) / (1 - 0.35),
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

      // Tiny vertical bob during transit for life.
      const transit = 4 * local * (1 - local);
      child.position.y = panelHeight / 2 + transit * 0.025;

      // Slight emissive when moving.
      const moving = transit > 0.02;
      const mesh = child.children[0] as THREE.Mesh | undefined;
      if (mesh && (mesh.material as THREE.MeshStandardMaterial).emissive) {
        const m = mesh.material as THREE.MeshStandardMaterial;
        const target = moving ? 0.04 : 0;
        m.emissive = new THREE.Color(seriesData.accent);
        m.emissiveIntensity = THREE.MathUtils.damp(
          m.emissiveIntensity ?? 0,
          target,
          5,
          dt,
        );
      }
      // unused param handled in the closure; keep t referenced for ESLint.
      void t;
    });
  });

  return (
    <group ref={groupRef}>
      {layouts.map((layout) => (
        <group
          key={layout.index}
          position={[layout.closedX, panelHeight / 2, 0]}
        >
          {/* Main panel face */}
          <mesh castShadow receiveShadow material={material}>
            <boxGeometry
              args={[panelWidthFt - 0.02, panelHeight - 0.04, panelThicknessFt]}
            />
          </mesh>

          {/* Top trim */}
          <mesh
            position={[0, panelHeight / 2 - 0.02, 0]}
            material={trimMat}
            castShadow
          >
            <boxGeometry
              args={[panelWidthFt - 0.02, 0.06, panelThicknessFt + 0.005]}
            />
          </mesh>

          {/* Bottom seal/sweep */}
          <mesh
            position={[0, -panelHeight / 2 + 0.04, 0]}
            material={trimMat}
            castShadow
          >
            <boxGeometry
              args={[panelWidthFt - 0.02, 0.08, panelThicknessFt + 0.01]}
            />
          </mesh>

          {/* Edge reveals (vertical seams) */}
          <mesh
            position={[panelWidthFt / 2 - 0.012, 0, 0]}
            material={trimMat}
          >
            <boxGeometry args={[0.012, panelHeight - 0.06, panelThicknessFt + 0.002]} />
          </mesh>
          <mesh
            position={[-panelWidthFt / 2 + 0.012, 0, 0]}
            material={trimMat}
          >
            <boxGeometry args={[0.012, panelHeight - 0.06, panelThicknessFt + 0.002]} />
          </mesh>

          {/* Pull handle (offset from edge) — only first/last visually */}
          {(layout.index === 0 || layout.index === layouts.length - 1) && (
            <mesh
              position={[
                layout.index === 0 ? -panelWidthFt / 2 + 0.18 : panelWidthFt / 2 - 0.18,
                0,
                panelThicknessFt / 2 + 0.012,
              ]}
              material={trimMat}
              castShadow
            >
              <boxGeometry args={[0.05, 1.2, 0.04]} />
            </mesh>
          )}
        </group>
      ))}
    </group>
  );
}
