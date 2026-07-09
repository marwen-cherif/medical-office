import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Wallet,
  Briefcase,
  Truck,
  Settings,
  Keyboard,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useShortcut, useShortcutsContext } from "@/lib/shortcuts";
import { ShortcutKeys } from "@/components/common/Kbd";

type NavItem = { to: string; label: string; icon: LucideIcon; enabled: boolean };

// Reprend la navigation (et l'ordre) de l'app Flet : Tableau, Patients,
// Prestataires, Finances, Travaux, Paramétrage. Chaque entrée reçoit le
// raccourci `Alt+<rang>` (Alt+1 = premier item, etc.), reconnu via `event.code`
// (Digit1…) donc utilisable sans `Maj` sur clavier AZERTY.
const ITEMS: NavItem[] = [
  { to: "/tableau-de-bord", label: "Tableau de bord", icon: LayoutDashboard, enabled: true },
  { to: "/patients", label: "Patients", icon: Users, enabled: true },
  { to: "/prestataires", label: "Prestataires", icon: Truck, enabled: true },
  { to: "/finances", label: "Finances", icon: Wallet, enabled: true },
  { to: "/travaux", label: "Travaux", icon: Briefcase, enabled: true },
  { to: "/parametrage", label: "Paramétrage", icon: Settings, enabled: true },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { openHelp } = useShortcutsContext();

  // Navigation globale : Alt+1 … Alt+6 vers chaque section.
  useShortcut(
    ITEMS.filter((it) => it.enabled).map((it, i) => ({
      keys: `alt+${i + 1}`,
      description: it.label,
      group: "Navigation",
      order: i,
      handler: () => navigate(it.to),
    })),
  );

  // Ouvrir la carte des raccourcis. `?` fonctionne quelle que soit la disposition
  // (on matche le caractère produit). `F1` en complément.
  useShortcut([
    { keys: "?", description: "Afficher les raccourcis clavier", group: "Général", order: 0, handler: openHelp },
    // F1 : alias universel d'aide, fonctionnel mais masqué de la carte (évite le doublon).
    { keys: "f1", description: "Afficher les raccourcis clavier", group: "Général", order: 1, hidden: true, handler: openHelp },
  ]);

  return (
    <div className="flex h-full">
      <nav className="flex w-56 shrink-0 flex-col border-r border-line bg-white">
        <div className="flex items-center gap-2 px-4 py-5">
          <div className="flex size-9 items-center justify-center rounded-[var(--radius)] bg-navy text-sm font-bold text-white">
            CG
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-ink">Cabinet CRM</div>
            <div className="text-xs text-muted">Dr Aslem Gouiaa</div>
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-1 px-2">
          {ITEMS.map((item, i) => {
            const Icon = item.icon;
            if (!item.enabled) {
              return (
                <span
                  key={item.to}
                  title="À venir (incrément ultérieur)"
                  className="flex cursor-not-allowed items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm text-muted/50"
                >
                  <Icon className="size-4" />
                  {item.label}
                </span>
              );
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm font-medium transition-colors",
                    isActive ? "bg-navy text-white" : "text-ink hover:bg-bg",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className="size-4 shrink-0" />
                    <span className="flex-1">{item.label}</span>
                    {/* Indice de raccourci toujours visible (Alt+rang). */}
                    <ShortcutKeys
                      keys={`alt+${i + 1}`}
                      className={cn(
                        "opacity-70 transition-opacity group-hover:opacity-100",
                        isActive && "[&_kbd]:border-white/30 [&_kbd]:bg-white/15 [&_kbd]:text-white",
                      )}
                    />
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
        <div className="px-2 pb-2">
          <button
            type="button"
            onClick={openHelp}
            title="Afficher les raccourcis clavier"
            className="flex w-full items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm font-medium text-ink transition-colors hover:bg-bg"
          >
            <Keyboard className="size-4 shrink-0" />
            <span className="flex-1 text-left">Raccourcis</span>
            <ShortcutKeys keys="?" className="opacity-70" />
          </button>
          <div className="px-3 pt-2 text-xs text-muted/70">React · sidecar FastAPI</div>
        </div>
      </nav>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
