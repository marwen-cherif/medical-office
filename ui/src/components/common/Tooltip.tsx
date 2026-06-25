import { cn } from "@/lib/utils";
import { ShortcutKeys } from "@/components/common/Kbd";

type Side = "top" | "bottom" | "left" | "right";

const SIDE_POS: Record<Side, string> = {
  top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
  left: "right-full top-1/2 mr-1.5 -translate-y-1/2",
  right: "left-full top-1/2 ml-1.5 -translate-y-1/2",
};

/**
 * Infobulle **sans dépendance** s'affichant au survol **et au focus clavier**
 * (`group-hover` + `group-focus-within`) — donc accessible au clavier, contrairement
 * à l'attribut `title` natif. Affiche un libellé et, optionnellement, le raccourci.
 *
 * À utiliser sur des éléments dont l'ancêtre n'a pas d'`overflow-hidden` (barres
 * d'actions, en-têtes) : l'infobulle déborde de son conteneur.
 */
export function Tooltip({
  label,
  shortcut,
  side = "bottom",
  children,
  className,
}: {
  label: React.ReactNode;
  /** Combinaison à afficher en `<Kbd>` (ex. `"alt+n"`). */
  shortcut?: string;
  side?: Side;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("group/tt relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 flex items-center gap-1.5 whitespace-nowrap rounded-[6px]",
          "bg-ink px-2 py-1 text-xs font-medium text-white shadow-md",
          "opacity-0 transition-opacity duration-100",
          "group-hover/tt:opacity-100 group-focus-within/tt:opacity-100",
          SIDE_POS[side],
        )}
      >
        <span>{label}</span>
        {shortcut && (
          <ShortcutKeys
            keys={shortcut}
            className="[&_kbd]:border-white/25 [&_kbd]:bg-white/10 [&_kbd]:text-white [&_kbd]:shadow-none"
          />
        )}
      </span>
    </span>
  );
}
