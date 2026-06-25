import { Fragment } from "react";
import { MoreHorizontal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export type RowAction = {
  /** Clé React stable. */
  key: string;
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  /** `danger` colore l'item en rouge (suppression, annulation…). */
  tone?: "default" | "danger";
  /** Insère un séparateur avant cet item. */
  separatorBefore?: boolean;
};

/**
 * Regroupe les actions d'une ligne (fiche patient) dans un menu déroulant
 * déclenché par un bouton « ⋯ ». Les valeurs falsy sont ignorées, ce qui
 * permet aux appelants de construire la liste conditionnellement :
 *   actions={[canSend && { … }, { … }]}
 */
export function RowActions({
  actions,
  label = "Actions",
}: {
  actions: (RowAction | false | null | undefined)[];
  label?: string;
}) {
  const items = actions.filter((a): a is RowAction => !!a);
  if (items.length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" title={label} aria-label={label}>
          <MoreHorizontal className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {items.map((a) => {
          const Icon = a.icon;
          return (
            <Fragment key={a.key}>
              {a.separatorBefore && <DropdownMenuSeparator />}
              <DropdownMenuItem
                onSelect={() => a.onClick()}
                className={cn(a.tone === "danger" && "text-red focus:bg-red/10")}
              >
                <Icon className="size-4" />
                {a.label}
              </DropdownMenuItem>
            </Fragment>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
