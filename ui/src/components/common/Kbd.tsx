import { Fragment } from "react";
import { cn } from "@/lib/utils";
import { comboToKeys } from "@/lib/shortcuts";

/** Rendu d'une touche unique, style « capuchon de clavier ». */
export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-[5px] border border-line",
        "bg-bg px-1.5 font-sans text-[11px] font-semibold leading-none text-muted",
        "shadow-[inset_0_-1px_0_var(--color-line)]",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

/**
 * Rendu d'une combinaison de raccourci (ex. `keys="alt+n"` → `Alt` `N`).
 * Les jetons sont séparés par un fin `+`.
 */
export function ShortcutKeys({ keys, className }: { keys: string; className?: string }) {
  const tokens = comboToKeys(keys);
  return (
    <span className={cn("inline-flex items-center gap-0.5 align-middle", className)}>
      {tokens.map((t, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="text-[10px] text-muted/60">+</span>}
          <Kbd>{t}</Kbd>
        </Fragment>
      ))}
    </span>
  );
}
