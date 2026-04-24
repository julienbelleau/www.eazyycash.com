"use client";

import { useThree, useFrame } from "@react-three/fiber";
import { useEffect, useRef, MutableRefObject } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { useConfigurator } from "@/lib/store";

const PRESETS = {
  iso: { pos: [22, 14, 28], target: [0, 4, 0] },
  front: { pos: [0, 7, 30], target: [0, 7, 0] },
  top: { pos: [0.001, 38, 0.001], target: [0, 0, 0] },
  stack: { pos: [-18, 8, 14], target: [-12, 4, 0] },
} as const;

export function CameraRig({
  controlsRef,
}: {
  controlsRef: MutableRefObject<OrbitControlsImpl | null>;
}) {
  const camera = useThree((s) => s.camera);
  const preset = useConfigurator((s) => s.cameraPreset);

  const targetPos = useRef(new THREE.Vector3(...PRESETS.iso.pos));
  const targetLook = useRef(new THREE.Vector3(...PRESETS.iso.target));

  useEffect(() => {
    const p = PRESETS[preset];
    targetPos.current.set(...(p.pos as unknown as [number, number, number]));
    targetLook.current.set(...(p.target as unknown as [number, number, number]));
  }, [preset]);

  useFrame((_, dt) => {
    camera.position.lerp(targetPos.current, Math.min(1, dt * 2.6));
    if (controlsRef.current) {
      controlsRef.current.target.lerp(targetLook.current, Math.min(1, dt * 2.6));
      controlsRef.current.update();
    }
  });

  return null;
}
