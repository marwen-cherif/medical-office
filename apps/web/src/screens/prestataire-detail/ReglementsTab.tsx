import { useState } from 'react';
import { Receipt } from 'lucide-react';
import { Pagination } from '@/components/common/Pagination';
import { humanizeError } from '@/lib/errors';
import { isoToFr, modeLabel } from '@/lib/format';
import { Montant } from '@/components/common/Montant';
import { useProviderReglements } from '@/hooks/prestataires';

export function ReglementsTab({ prestataireId }: { prestataireId: number }) {
  const [page, setPage] = useState(0);
  const q = useProviderReglements(prestataireId, page);

  if (q.isLoading) return <p className="pt-4 text-sm text-muted">Chargement…</p>;
  if (q.isError) return <p className="pt-4 text-sm text-red">{humanizeError(q.error)}</p>;
  const data = q.data!;

  return (
    <div className="space-y-4 pt-4">
      <div className="rounded-[var(--radius)] border border-line bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold text-navy">Règlements fournisseurs</h3>
        {data.items.length === 0 ? (
          <p className="text-sm text-muted">Aucun règlement.</p>
        ) : (
          data.items.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 border-t border-line py-2.5 first:border-t-0"
            >
              <Montant value={r.montant} tone="green" bold className="w-24 text-right" />
              <Receipt className="size-4 text-muted" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-ink">{r.depense_libelle || r.motif || 'Dépense'}</div>
                <div className="text-xs text-muted">
                  {modeLabel(r.mode)}
                  {r.date_reglement ? ` · ${isoToFr(r.date_reglement)}` : ''}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <Pagination total={data.total} page={page} onPage={setPage} />
    </div>
  );
}
