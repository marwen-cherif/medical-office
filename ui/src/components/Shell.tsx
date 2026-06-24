import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Wallet,
  Briefcase,
  Truck,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type NavItem = { to: string; label: string; icon: LucideIcon; enabled: boolean };

// Reprend la navigation (et l'ordre) de l'app Flet : Tableau, Patients,
// Prestataires, Finances, Travaux, Paramétrage.
const ITEMS: NavItem[] = [
  { to: "/tableau-de-bord", label: "Tableau de bord", icon: LayoutDashboard, enabled: true },
  { to: "/patients", label: "Patients", icon: Users, enabled: true },
  { to: "/prestataires", label: "Prestataires", icon: Truck, enabled: true },
  { to: "/finances", label: "Finances", icon: Wallet, enabled: true },
  { to: "/travaux", label: "Travaux", icon: Briefcase, enabled: true },
  { to: "/parametrage", label: "Paramétrage", icon: Settings, enabled: true },
];

export function Shell({ children }: { children: React.ReactNode }) {
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
          {ITEMS.map((item) => {
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
                    "flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm font-medium transition-colors",
                    isActive ? "bg-navy text-white" : "text-ink hover:bg-bg",
                  )
                }
              >
                <Icon className="size-4" />
                {item.label}
              </NavLink>
            );
          })}
        </div>
        <div className="px-4 py-3 text-xs text-muted/70">React · sidecar FastAPI</div>
      </nav>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
