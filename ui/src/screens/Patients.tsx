import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pagination } from "@/components/common/Pagination";
import { Tooltip } from "@/components/common/Tooltip";
import { Kbd } from "@/components/common/Kbd";
import { PatientFormDialog } from "@/components/dialogs/PatientFormDialog";
import { humanizeError } from "@/lib/errors";
import { useShortcut } from "@/lib/shortcuts";
import { usePatients } from "@/hooks/patients";
import type { Patient } from "@/api/types";

function initials(p: Patient): string {
  return `${(p.nom?.[0] ?? "").toUpperCase()}${(p.prenom?.[0] ?? "").toUpperCase()}` || "?";
}

export function Patients() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filtre, setFiltre] = useState("tous");
  const [page, setPage] = useState(0);
  const [dialog, setDialog] = useState<Patient | "new" | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const list = usePatients(search, filtre, page);

  useShortcut([
    {
      keys: "alt+n",
      description: "Nouveau patient",
      group: "Patients",
      handler: () => setDialog("new"),
    },
    {
      keys: "/",
      description: "Rechercher",
      group: "Patients",
      handler: () => searchRef.current?.focus(),
    },
  ]);

  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Patients</h1>
          <p className="mt-1 text-sm text-muted">Fiches patients, actes, paiements et documents.</p>
        </div>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            ref={searchRef}
            className="pl-9 pr-9"
            placeholder="Rechercher un patient…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
          <Kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2">/</Kbd>
        </div>
        <Select
          value={filtre}
          onValueChange={(v) => {
            setFiltre(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="tous">Tous les patients</SelectItem>
            <SelectItem value="impayes">Avec impayés</SelectItem>
          </SelectContent>
        </Select>
        <Tooltip label="Nouveau patient" shortcut="alt+n">
          <Button onClick={() => setDialog("new")}>
            <Plus className="size-4" /> Nouveau patient
          </Button>
        </Tooltip>
      </div>

      {list.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {list.isError && <p className="text-sm text-red">{humanizeError(list.error)}</p>}

      <div className="overflow-hidden rounded-[var(--radius)] border border-line bg-white">
        {(list.data?.items ?? []).map((p) => (
          <button
            key={p.id}
            onClick={() => navigate(`/patients/${p.id}`)}
            className="flex w-full items-center gap-3 border-b border-line px-4 py-3 text-left last:border-b-0 hover:bg-bg"
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-teal/30 text-sm font-semibold text-teal-dark">
              {initials(p)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-ink">{p.display}</div>
              <div className="truncate text-sm text-muted">
                {[p.email, p.telephone].filter(Boolean).join(" · ") || "—"}
              </div>
            </div>
            <span className="text-xs text-muted">#{p.id}</span>
            <ChevronRight className="size-4 text-muted" />
          </button>
        ))}
        {list.data?.items.length === 0 && (
          <div className="py-10 text-center text-muted">Aucun patient.</div>
        )}
      </div>

      <div className="mt-4">
        <Pagination total={list.data?.total ?? 0} page={page} onPage={setPage} />
      </div>

      <PatientFormDialog
        target={dialog}
        onClose={() => setDialog(null)}
        onCreated={(p) => navigate(`/patients/${p.id}`)}
      />
    </div>
  );
}
