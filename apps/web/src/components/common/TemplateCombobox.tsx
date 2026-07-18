import * as React from 'react';
import * as Lucide from 'lucide-react';
import { Check, ChevronDown, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCategories } from '@/hooks/queries';
import type { GenTemplate } from '@/api/types';

type LucideIconType = React.ComponentType<{ className?: string }>;

// Helper to dynamically retrieve and format a Lucide icon by its string name.
export function CategoryIcon({ name, className }: { name?: string | null; className?: string }) {
  if (!name) return null;

  const lucideMap = Lucide as unknown as Record<string, LucideIconType>;

  // Try exact match first
  if (name in lucideMap) {
    const IconComponent = lucideMap[name];
    return <IconComponent className={className} />;
  }

  // Try converting kebab-case, snake_case or spaced strings to PascalCase
  const pascalName = name
    .split(/[-_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join('');

  if (pascalName in lucideMap) {
    const IconComponent = lucideMap[pascalName];
    return <IconComponent className={className} />;
  }

  // Try case-insensitive matching
  const nameLower = name.toLowerCase();
  const foundKey = Object.keys(lucideMap).find((key) => key.toLowerCase() === nameLower);
  if (foundKey) {
    const IconComponent = lucideMap[foundKey];
    return <IconComponent className={className} />;
  }

  return null;
}

/** Case and accent folding helper for searching. */
function fold(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}

interface TemplateComboboxProps {
  templates: GenTemplate[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
  searchPlaceholder?: string;
}

export function TemplateCombobox({
  templates,
  value,
  onChange,
  disabled,
  className,
  placeholder = 'Choisir un modèle…',
  searchPlaceholder = 'Rechercher un modèle…',
}: TemplateComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState('');
  const [active, setActive] = React.useState(0);

  const rootRef = React.useRef<HTMLDivElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const listboxId = React.useId();

  const categories = useCategories();

  const selectedTemplate = React.useMemo(() => {
    return (templates ?? []).find((t) => t.name === value) ?? null;
  }, [templates, value]);

  const hasValue = value != null && value !== '';
  const triggerLabel = selectedTemplate ? selectedTemplate.label : '';

  // Filter templates & group them by category
  const grouped = React.useMemo(() => {
    const q = fold(query.trim());
    const filtered = (templates ?? []).filter((t) => {
      const matchLabel = fold(t.label).includes(q);
      const matchCat = t.categorie ? fold(t.categorie).includes(q) : false;
      return matchLabel || matchCat;
    });

    const groupsMap = new Map<string, GenTemplate[]>();
    for (const t of filtered) {
      const key = t.categorie || 'Sans catégorie';
      if (!groupsMap.has(key)) {
        groupsMap.set(key, []);
      }
      groupsMap.get(key)!.push(t);
    }

    // Sort groups: "Sans catégorie" goes last, others are sorted by their database sort_order or alphabetically
    return Array.from(groupsMap.entries()).sort((a, b) => {
      if (a[0] === 'Sans catégorie') return 1;
      if (b[0] === 'Sans catégorie') return -1;

      const catA = categories.data?.find((c) => c.nom === a[0]);
      const catB = categories.data?.find((c) => c.nom === b[0]);
      const orderA = catA?.sort_order ?? 999;
      const orderB = catB?.sort_order ?? 999;

      if (orderA !== orderB) return orderA - orderB;
      return a[0].localeCompare(b[0], 'fr');
    });
  }, [templates, query, categories]);

  // Flattened matching templates to map to active index for keyboard navigation
  const selectableItems = React.useMemo(() => {
    return grouped.flatMap(([, items]) => items);
  }, [grouped]);

  // Focus the input when dropdown opens
  React.useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  // Handle outside clicks to close the dropdown
  React.useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('pointerdown', onPointerDown, true);
    return () => document.removeEventListener('pointerdown', onPointerDown, true);
  }, [open]);

  // Scroll active item into view
  React.useEffect(() => {
    if (!open || !scrollRef.current) return;
    const activeEl = scrollRef.current.querySelector('[data-active="true"]');
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }, [active, open]);

  function commit(name: string) {
    if (!name) return;
    onChange(name);
    setOpen(false);
  }

  function moveActive(dir: 1 | -1) {
    if (!selectableItems.length) return;
    setActive((prev) => (prev + dir + selectableItems.length) % selectableItems.length);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      moveActive(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      moveActive(-1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setActive(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setActive(selectableItems.length - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectableItems[active]) {
        commit(selectableItems[active].name);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => {
          if (!disabled) {
            setOpen((o) => {
              const next = !o;
              if (next) {
                setQuery('');
                const idx = value ? selectableItems.findIndex((t) => t.name === value) : 0;
                setActive(idx < 0 ? 0 : idx);
              }
              return next;
            });
          }
        }}
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 rounded-[var(--radius)] border border-line bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-navy/40 disabled:opacity-50',
          className
        )}
      >
        <span className={cn('line-clamp-1 text-left', hasValue ? 'text-ink' : 'text-muted')}>
          {triggerLabel || placeholder}
        </span>
        <ChevronDown className="size-4 shrink-0 opacity-60" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 flex flex-col rounded-[var(--radius)] border border-line bg-white p-2 shadow-lg max-h-80">
          {/* Search box */}
          <div className="mb-1.5 flex items-center gap-2 border-b border-line px-1 pb-2">
            <Search className="size-4 shrink-0 text-muted" />
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-expanded
              aria-autocomplete="list"
              aria-controls={listboxId}
              aria-activedescendant={
                selectableItems.length ? `${listboxId}-opt-${active}` : undefined
              }
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
                if (scrollRef.current) scrollRef.current.scrollTop = 0;
              }}
              onKeyDown={onKeyDown}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-muted"
            />
            {query && (
              <button
                type="button"
                aria-label="Effacer la recherche"
                onClick={() => {
                  setQuery('');
                  setActive(0);
                  if (scrollRef.current) scrollRef.current.scrollTop = 0;
                }}
                className="rounded p-0.5 text-muted hover:text-ink"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>

          {/* Grouped list */}
          <div
            ref={scrollRef}
            role="listbox"
            id={listboxId}
            className="overflow-y-auto overflow-x-hidden flex-1 space-y-3 pr-1"
          >
            {grouped.length === 0 ? (
              <div className="px-2 py-6 text-center text-sm text-muted">Aucun modèle trouvé.</div>
            ) : (
              grouped.map(([catName, items]) => {
                const catObj = categories.data?.find((c) => c.nom === catName);
                const color = catObj?.couleur || '#94a3b8';
                const iconName = catObj?.icone;

                return (
                  <div key={catName} className="space-y-1">
                    {/* Category Header */}
                    <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-bold tracking-wider text-muted/80 uppercase bg-bg/30 rounded-sm animate-none">
                      <span
                        className="size-1.5 rounded-full shrink-0"
                        style={{
                          backgroundColor: catName === 'Sans catégorie' ? '#cbd5e1' : color,
                        }}
                      />
                      {iconName && (
                        <CategoryIcon name={iconName} className="size-3 text-muted shrink-0" />
                      )}
                      <span className="truncate">{catName}</span>
                    </div>

                    {/* Category Items */}
                    <ul className="space-y-0.5 list-none p-0 m-0">
                      {items.map((t) => {
                        const isSelected = t.name === value;
                        const itemIndex = selectableItems.findIndex((x) => x.name === t.name);
                        const isActive = itemIndex === active;

                        return (
                          <li
                            key={t.name}
                            id={`${listboxId}-opt-${itemIndex}`}
                            role="option"
                            aria-selected={isSelected}
                            onMouseEnter={() => setActive(itemIndex)}
                            onMouseDown={(ev) => {
                              ev.preventDefault();
                              commit(t.name);
                            }}
                            data-active={isActive ? 'true' : 'false'}
                            className={cn(
                              'flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm transition-colors',
                              isSelected ? 'text-ink font-medium' : 'text-ink',
                              isActive ? 'bg-bg text-ink' : ''
                            )}
                          >
                            <span className="flex size-4 shrink-0 items-center justify-center">
                              {isSelected && <Check className="size-4 text-navy" />}
                            </span>
                            <span className="truncate flex-1">{t.label}</span>
                            {t.is_multiligne && (
                              <span className="text-[10px] bg-navy/10 text-navy px-1.5 py-0.5 rounded font-medium shrink-0">
                                Multi-lignes
                              </span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
