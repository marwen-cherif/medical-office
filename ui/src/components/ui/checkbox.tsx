import * as React from "react";
import { cn } from "@/lib/utils";

/** Case à cocher native stylée (pas de dépendance Radix supplémentaire). */
export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "onChange"> {
  onCheckedChange?: (checked: boolean) => void;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, onCheckedChange, ...props }, ref) => (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "size-4 shrink-0 cursor-pointer rounded border-line text-navy accent-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40",
        className,
      )}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      {...props}
    />
  ),
);
Checkbox.displayName = "Checkbox";
