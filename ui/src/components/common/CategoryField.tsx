import { Combobox, type ComboboxOption } from "@/components/common/Combobox";
import { useCategories } from "@/hooks/queries";
import { SPECIAL_CATEGORIES } from "@/lib/categories";
import { cn } from "@/lib/utils";

/**
 * Champ « catégorie de modèle » : un {@link Combobox} **creatable** (catégories
 * existantes sélectionnables + création de nouvelles à la volée) doublé de **chips de
 * suggestion réservées aux catégories spéciales** (statiques, à logique métier — cf.
 * `SPECIAL_CATEGORIES`). Le « système de suggestion » de l'oracle Flet est ainsi repris
 * **uniquement** pour ces catégories métier, toujours proposées même si aucune
 * catégorie de ce nom n'existe encore en base.
 *
 * Valeur = nom de la catégorie (texte libre). Vide = « sans catégorie ». La création en
 * base est paresseuse côté backend (`set_template_category` → `upsert_category`).
 */
export function CategoryField({
  value,
  onChange,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
}) {
  const categories = useCategories();
  const options: ComboboxOption[] = (categories.data ?? []).map((c) => ({
    value: c.nom,
    label: c.nom,
  }));

  return (
    <div className="space-y-2">
      <Combobox
        id={id}
        value={value}
        onChange={onChange}
        options={options}
        creatable
        allowClear
        placeholder="Sans catégorie"
        searchPlaceholder="Rechercher ou créer une catégorie…"
        emptyText="Tapez pour créer une catégorie."
      />
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted">Suggestions&nbsp;:</span>
        {SPECIAL_CATEGORIES.map((s) => {
          const isActive = value === s.nom;
          return (
            <button
              key={s.nom}
              type="button"
              title={s.hint}
              onClick={() => onChange(s.nom)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
                isActive
                  ? "border-navy bg-navy/10 text-navy"
                  : "border-line text-muted hover:border-navy/40 hover:text-ink",
              )}
            >
              {s.nom}
            </button>
          );
        })}
      </div>
    </div>
  );
}
