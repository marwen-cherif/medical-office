import { useMemo } from "react";
import { Keyboard } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ShortcutKeys } from "@/components/common/Kbd";
import { useShortcutsContext, type ShortcutDef } from "@/lib/shortcuts";

// Groupes prioritaires en tête de carte ; les autres suivent dans l'ordre d'apparition.
const GROUP_ORDER = ["Navigation", "Général"];

function sortedGroups(shortcuts: ShortcutDef[]): [string, ShortcutDef[]][] {
  const map = new Map<string, ShortcutDef[]>();
  for (const s of shortcuts) {
    if (s.hidden) continue; // alias masqués (ex. F1)
    if (!map.has(s.group)) map.set(s.group, []);
    map.get(s.group)!.push(s);
  }
  return [...map.entries()].sort(([a], [b]) => {
    const ia = GROUP_ORDER.indexOf(a);
    const ib = GROUP_ORDER.indexOf(b);
    if (ia !== -1 || ib !== -1) return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    return 0; // conserve l'ordre d'insertion (≈ ordre d'enregistrement)
  });
}

/**
 * Carte globale des raccourcis clavier. Affiche tous les raccourcis **actuellement
 * actifs** (globaux + ceux de l'écran courant), regroupés. Ouverte via `?` ou le
 * bouton « Raccourcis » de la barre latérale ; fermée par Échap (géré par Radix).
 */
export function ShortcutsHelpDialog() {
  const { shortcuts, helpOpen, closeHelp } = useShortcutsContext();
  const groups = useMemo(() => sortedGroups(shortcuts), [shortcuts]);

  return (
    <Dialog open={helpOpen} onOpenChange={(o) => !o && closeHelp()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="size-5 text-navy" /> Raccourcis clavier
          </DialogTitle>
          <DialogDescription>
            Toutes les actions sont accessibles au clavier. Appuyez sur{" "}
            <ShortcutKeys keys="?" /> à tout moment pour rouvrir cette carte.
          </DialogDescription>
        </DialogHeader>

        <div className="grid max-h-[60vh] gap-x-8 gap-y-5 overflow-auto pr-1 sm:grid-cols-2">
          {groups.map(([group, items]) => (
            <section key={group} className="space-y-1.5">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-navy">{group}</h3>
              <ul className="space-y-1">
                {items.map((s, i) => (
                  <li
                    key={`${s.keys}-${i}`}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span className={s.enabled === false ? "text-muted/50" : "text-ink"}>
                      {s.description}
                    </span>
                    <ShortcutKeys
                      keys={s.keys}
                      className={s.enabled === false ? "opacity-40" : undefined}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {groups.length === 0 && (
            <p className="text-sm text-muted">Aucun raccourci disponible sur cet écran.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
