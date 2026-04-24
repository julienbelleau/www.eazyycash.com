"use client";

import { Canvas } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  Grid,
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei";
import { Suspense, useEffect, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { useConfigurator } from "@/lib/store";
import { Room } from "./Room";
import { Track } from "./Track";
import { PanelTrain } from "./PanelTrain";
import { DimensionLabels } from "./DimensionLabels";
import { CameraRig } from "./CameraRig";

export function Scene() {
  const showGrid = useConfigurator((s) => s.showGrid);
  const controlsRef = useRef<OrbitControlsImpl | null>(null);

  useEffect(() => {
    // Faster initial damping settle.
    controlsRef.current?.update();
  }, []);

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      gl={{
        antialias: true,
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 1.05,
      }}
      className="!h-full !w-full"
    >
      <color attach="background" args={["#0e1116"]} />
      <fog attach="fog" args={["#0e1116", 40, 110]} />

      <PerspectiveCamera makeDefault fov={38} position={[22, 14, 28]} />
      <CameraRig controlsRef={controlsRef} />

      <Suspense fallback={null}>
        <Environment preset="warehouse" environmentIntensity={0.55} />

        {/* Key light */}
        <directionalLight
          position={[14, 18, 10]}
          intensity={1.6}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-left={-30}
          shadow-camera-right={30}
          shadow-camera-top={30}
          shadow-camera-bottom={-30}
          shadow-bias={-0.0002}
        />
        <directionalLight position={[-10, 8, -8]} intensity={0.35} color="#9bb6ff" />
        <ambientLight intensity={0.25} />

        <Room />
        <Track />
        <PanelTrain />
        <DimensionLabels />

        {showGrid && (
          <Grid
            position={[0, 0.01, 0]}
            args={[80, 80]}
            cellSize={1}
            cellThickness={0.6}
            cellColor="#2b313b"
            sectionSize={5}
            sectionThickness={1.1}
            sectionColor="#3a4150"
            fadeDistance={60}
            fadeStrength={1.4}
            infiniteGrid
          />
        )}

        <ContactShadows
          position={[0, 0.001, 0]}
          opacity={0.55}
          scale={60}
          blur={2.4}
          far={20}
          resolution={1024}
          color="#000000"
        />
      </Suspense>

      <OrbitControls
        ref={controlsRef}
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={6}
        maxDistance={70}
        maxPolarAngle={Math.PI / 2 - 0.05}
        target={[0, 4, 0]}
      />
    </Canvas>
  );
}
