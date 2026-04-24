"use client";

import * as RSwitch from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  className?: string;
  id?: string;
}

export function Switch({ checked, onCheckedChange, className, id }: SwitchProps) {
  return (
    <RSwitch.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      className={cn(
        "relative h-5 w-9 rounded-full transition-colors",
        "data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-[var(--color-accent-2)] data-[state=checked]:to-[var(--color-accent)]",
        "data-[state=unchecked]:bg-[var(--color-surface-2)] border border-[var(--color-border)]",
        className,
      )}
    >
      <RSwitch.Thumb className="block size-4 translate-x-0.5 rounded-full bg-white shadow-md transition-transform data-[state=checked]:translate-x-[18px]" />
    </RSwitch.Root>
  );
}
