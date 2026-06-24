import { useState } from "react";
import {
  Activity,
  Banknote,
  FileStack,
  FileText,
  Hourglass,
  Send,
  TrendingDown,
  TrendingUp,
  UserPlus,
  Users,
  UserX,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { DateRangeFilter } from "@/components/common/DateRangeFilter";
import { humanizeError } from "@/lib/errors";
import { fmtEuro, humanize, isoToFrDateTime, monthRange } from "@/lib/format";
import { useDashboard } from "@/hooks/dashboard";
import type { DocTypeCount, Kpis } from "@/api/types";

/** Tuile KPI : libellé discret, valeur en avant, icône lucide. */
function KpiTile({
  label,
  value,
  icon: Icon,
  valueClass,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  valueClass?: string;
}) {
  return (
    <div className="rounded-[var(--radius)] border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted">{label}</p>
        <Icon className="size-4 shrink-0 text-navy" />
      </div>
      <p className={`mt-2 text-xl font-semibold tabular-nums ${valueClass ?? "text-ink"}`}>
        {value}
      </p>
    </div>
  );
}

/** Petit anneau SVG (donut) à deux segments, sans librairie de graphes. */
function Donut({
  a,
  b,
  colorA,
  colorB,
}: {
  a: number;
  b: number;
  colorA: string;
  colorB: string;
}) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const total = a + b;
  const fracA = total > 0 ? a / total : 0;
  const lenA = c * fracA;
  return (
    <svg viewBox="0 0 120 120" className="size-28 shrink-0 -rotate-90">
      <circle cx="60" cy="60" r={r} fill="none" stroke="var(--color-line)" strokeWidth="14" />
      {total > 0 && (
        <>
          <circle
            cx="60"
            cy="60"
            r={r}
            fill="none"
            stroke={colorB}
            strokeWidth="14"
            strokeDasharray={`${c} ${c}`}
          />
          <circle
            cx="60"
            cy="60"
            r={r}
            fill="none"
            stroke={colorA}
            strokeWidth="14"
            strokeDasharray={`${lenA} ${c - lenA}`}
            strokeLinecap="butt"
          />
        </>
      )}
    </svg>
  );
}

/** Ligne de légende d'un donut : pastille + libellé + montant + part. */
function LegendRow({
  color,
  label,
  amount,
  total,
}: {
  color: string;
  label: string;
  amount: number;
  total: number;
}) {
  const pct = total > 0 ? Math.round((amount / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-muted">{label}</span>
      <span className="ml-auto tabular-nums text-ink">{fmtEuro(amount)}</span>
      <span className="w-10 text-right tabular-nums text-xs text-muted">{pct}%</span>
    </div>
  );
}

/** Carte « balance » : un donut à deux parts + légende. */
function BalanceCard({
  title,
  donut,
  children,
}: {
  title: string;
  donut: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius)] border border-line bg-white p-5">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <div className="mt-3 flex items-center gap-5">
        {donut}
        <div className="flex-1 space-y-2">{children}</div>
      </div>
    </div>
  );
}

const NAVY = "var(--color-navy)";
const GREEN = "var(--color-green)";
const TEAL = "var(--color-teal-dark)";
const AMBER = "var(--color-amber)";

export function TableauDeBord() {
  const [range, setRange] = useState(() => monthRange());
  const q = useDashboard(range.from, range.to);

  const kpis: Kpis | undefined = q.data?.kpis;
  const docs: DocTypeCount[] = q.data?.documents_by_type ?? [];
  const activity = q.data?.recent_activity ?? [];

  return (
    <div className="mx-auto max-w-6xl p-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Tableau de bord</h1>
          <p className="mt-1 text-sm text-muted">
            Vue d'ensemble de l'activité et des finances sur la période choisie.
          </p>
        </div>
        <DateRangeFilter
          from={range.from}
          to={range.to}
          onChange={(r) => setRange(r)}
        />
      </header>

      {q.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {q.isError && <p className="text-sm text-red">{humanizeError(q.error)}</p>}

      {kpis && (
        <div className="space-y-6">
          {/* Grille de KPI */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiTile label="CA encaissé" value={fmtEuro(kpis.ca_encaisse)} icon={Banknote} />
            <KpiTile
              label="Encours à recouvrer"
              value={fmtEuro(kpis.encours)}
              icon={Wallet}
            />
            <KpiTile
              label="Solde net"
              value={fmtEuro(kpis.solde_net)}
              icon={kpis.solde_net >= 0 ? TrendingUp : TrendingDown}
              valueClass={kpis.solde_net >= 0 ? "text-green" : "text-red"}
            />
            <KpiTile
              label="Dépenses payées"
              value={fmtEuro(kpis.depenses_reglees)}
              icon={TrendingDown}
            />
            <KpiTile
              label="Dette fournisseurs"
              value={fmtEuro(kpis.dette_fournisseurs)}
              icon={TrendingDown}
            />
            <KpiTile
              label="Paiements encaissés"
              value={String(kpis.nb_paiements_encaisses)}
              icon={Banknote}
            />
            <KpiTile
              label="Documents créés"
              value={String(kpis.nb_documents)}
              icon={FileStack}
            />
            <KpiTile label="Brouillons" value={String(kpis.nb_brouillons)} icon={FileText} />
            <KpiTile label="Envoyés" value={String(kpis.nb_envoyes)} icon={Send} />
            <KpiTile
              label="Nouveaux patients"
              value={String(kpis.nb_nouveaux_patients)}
              icon={UserPlus}
            />
            <KpiTile label="Total patients" value={String(kpis.nb_patients)} icon={Users} />
            <KpiTile
              label="Avec impayés"
              value={String(kpis.nb_patients_impayes)}
              icon={UserX}
              valueClass={kpis.nb_patients_impayes > 0 ? "text-amber" : "text-ink"}
            />
          </div>

          {/* Cartes balance (donuts) */}
          <div className="grid gap-3 lg:grid-cols-2">
            <BalanceCard
              title="Trésorerie"
              donut={
                <Donut a={kpis.ca_encaisse} b={kpis.encours} colorA={GREEN} colorB={AMBER} />
              }
            >
              <LegendRow
                color={GREEN}
                label="Encaissé"
                amount={kpis.ca_encaisse}
                total={kpis.ca_encaisse + kpis.encours}
              />
              <LegendRow
                color={AMBER}
                label="À recouvrer"
                amount={kpis.encours}
                total={kpis.ca_encaisse + kpis.encours}
              />
            </BalanceCard>

            <BalanceCard
              title="Entrées / Sorties"
              donut={
                <Donut
                  a={kpis.ca_encaisse}
                  b={kpis.depenses_reglees}
                  colorA={NAVY}
                  colorB={TEAL}
                />
              }
            >
              <LegendRow
                color={NAVY}
                label="Entrées"
                amount={kpis.ca_encaisse}
                total={kpis.ca_encaisse + kpis.depenses_reglees}
              />
              <LegendRow
                color={TEAL}
                label="Sorties"
                amount={kpis.depenses_reglees}
                total={kpis.ca_encaisse + kpis.depenses_reglees}
              />
              <div className="mt-1 flex items-center justify-between border-t border-line pt-2 text-sm">
                <span className="text-muted">Solde net</span>
                <span
                  className={`tabular-nums font-semibold ${
                    kpis.solde_net >= 0 ? "text-green" : "text-red"
                  }`}
                >
                  {fmtEuro(kpis.solde_net)}
                </span>
              </div>
            </BalanceCard>
          </div>

          {/* Répartition des documents + Activité récente */}
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-[var(--radius)] border border-line bg-white p-5">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
                <FileStack className="size-4 text-navy" />
                Répartition des documents
              </h2>
              {docs.length === 0 ? (
                <p className="text-sm text-muted">Aucun document sur la période.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {docs.map((d) => (
                    <li
                      key={d.type}
                      className="flex items-center justify-between py-2 text-sm"
                    >
                      <span className="text-ink">{humanize(d.type)}</span>
                      <span className="tabular-nums font-medium text-ink">{d.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-[var(--radius)] border border-line bg-white p-5">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
                <Activity className="size-4 text-navy" />
                Activité récente
              </h2>
              {activity.length === 0 ? (
                <p className="text-sm text-muted">Aucune activité.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {activity.map((a, i) => (
                    <li key={i} className="py-2">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-sm text-ink">{humanize(a.action)}</span>
                        <span className="shrink-0 text-xs text-muted">
                          {isoToFrDateTime(a.ts)}
                        </span>
                      </div>
                      {summarizeDetail(a.detail) && (
                        <p className="mt-0.5 truncate text-xs text-muted">
                          {summarizeDetail(a.detail)}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {q.data && (
        <p className="mt-6 inline-flex items-center gap-1.5 text-xs text-muted">
          <Hourglass className="size-3.5" />
          Période du {range.from} au {range.to}.
        </p>
      )}
    </div>
  );
}

/** Résumé court et discret d'un `detail` d'audit (objet non nul uniquement). */
function summarizeDetail(detail: unknown): string {
  if (!detail || typeof detail !== "object") return "";
  const entries = Object.entries(detail as Record<string, unknown>)
    .filter(([, v]) => v !== null && v !== undefined && typeof v !== "object")
    .slice(0, 3)
    .map(([k, v]) => `${humanize(k)} : ${String(v)}`);
  if (entries.length > 0) return entries.join(" · ");
  const json = JSON.stringify(detail);
  return json.length > 120 ? `${json.slice(0, 117)}…` : json;
}
