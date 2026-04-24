"use client";

import * as RSlider from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

interface SliderProps {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  className?: string;
}

export function Slider({ value, onChange, min, max, step = 1, className }: SliderProps) {
  return (
    <RSlider.Root
      value={[value]}
      onValueChange={(v) => onChange(v[0])}
      min={min}
      max={max}
      step={step}
      className={cn("relative flex h-5 w-full items-center select-none", className)}
    >
      <RSlider.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-[var(--color-surface-2)]">
        <RSlider.Range className="absolute h-full bg-gradient-to-r from-[var(--color-accent-2)] to-[var(--color-accent)]" />
      </RSlider.Track>
      <RSlider.Thumb
        aria-label="Slider"
        className="block size-4 rounded-full border border-[var(--color-border-strong)] bg-[var(--color-fg)] shadow-md transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
      />
    </RSlider.Root>
  );
}
