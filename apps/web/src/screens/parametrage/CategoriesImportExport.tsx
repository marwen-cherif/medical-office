import { useRef, useState, type ChangeEvent } from 'react';
import { toast } from 'sonner';
import { Download, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { humanizeError } from '@/lib/errors';
import { useExportCategories, useImportCategories } from '@/hooks/queries';
import type { CategoryImport } from '@/api/types';

/**
 * Boutons « Exporter / Importer » des catégories de documents (.xlsx) + compte-rendu
 * d'import.
 */
export function CategoriesImportExport() {
  const exportCategories = useExportCategories();
  const importCategories = useImportCategories();
  const fileRef = useRef<HTMLInputElement>(null);
  const [report, setReport] = useState<CategoryImport | null>(null);

  function onExport() {
    exportCategories.mutate(undefined, {
      onSuccess: (r) =>
        toast.success(`Catégories exportées (${r.count} catégorie(s)). Le fichier s'ouvre dans Excel.`, {
          description: r.path,
        }),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // permet de réimporter le même fichier de suite
    if (!file) return;
    importCategories.mutate(file, {
      onSuccess: (r) => {
        setReport(r);
        toast.success(
          `Import terminé : ${r.created} créé(s), ${r.updated} mis à jour` +
            (r.skipped ? `, ${r.skipped} ignoré(s)` : '') +
            '.'
        );
      },
      onError: (err) => toast.error(humanizeError(err)),
    });
  }

  return (
    <>
      <input ref={fileRef} type="file" accept=".xlsx" className="hidden" onChange={onFile} />
      <Button variant="secondary" onClick={onExport} disabled={exportCategories.isPending}>
        <Download className="size-4" /> Exporter catégories
      </Button>
      <Button
        variant="secondary"
        onClick={() => fileRef.current?.click()}
        disabled={importCategories.isPending}
      >
        <Upload className="size-4" /> Importer catégories
      </Button>

      <Sheet open={!!report} onOpenChange={(o) => !o && setReport(null)}>
        <SheetContent>
          <div className="flex h-full flex-col">
            <SheetHeader>
              <SheetTitle>Compte-rendu de l'import</SheetTitle>
            </SheetHeader>
            <SheetBody>
              {report && (
                <div className="space-y-3 text-sm">
                  <ul className="space-y-1 text-ink">
                    <li>
                      Catégories créées : <strong>{report.created}</strong>
                    </li>
                    <li>
                      Catégories mises à jour : <strong>{report.updated}</strong>
                    </li>
                    <li>
                      Lignes ignorées : <strong>{report.skipped}</strong>
                    </li>
                  </ul>
                  {report.errors.length > 0 && (
                    <div className="space-y-1">
                      <p className="font-medium text-red">Lignes non importées :</p>
                      <ul className="max-h-48 space-y-1 overflow-auto rounded-[var(--radius)] border border-line bg-white p-2 text-xs text-muted">
                        {report.errors.map((msg, i) => (
                          <li key={i}>{msg}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </SheetBody>
            <SheetFooter>
              <Button onClick={() => setReport(null)}>Fermer</Button>
            </SheetFooter>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
