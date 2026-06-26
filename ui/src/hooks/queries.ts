/**
 * Hooks TanStack Query / mutations par ressource de la façade Paramétrage.
 *
 * Chaque hook délègue au client typé (lib/api.ts) ; les mutations invalident les
 * clés concernées pour rafraîchir les listes. Le cache TanStack Query absorbe la
 * latence HTTP localhost (cf. design R3).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, streamJob, downloadFile, type JobEvent } from "@/lib/api";
import { backend } from "@/lib/bridge";
import type { ActeImport, ActeIn, Field, MailTemplateIn } from "@/api/types";

export const keys = {
  templates: ["templates"] as const,
  templateFields: (name: string) => ["templates", name, "fields"] as const,
  templatePlaceholders: (name: string) => ["templates", name, "placeholders"] as const,
  categories: ["categories"] as const,
  mailTemplates: ["mail-templates"] as const,
  printers: ["printers"] as const,
  printTypes: ["settings", "print-types"] as const,
  actes: (search: string, includeInactive: boolean, categorie?: string) =>
    ["actes", { search, includeInactive, categorie: categorie ?? null }] as const,
  acteCategories: (includeInactive: boolean) =>
    ["actes", "categories", { includeInactive }] as const,
};

// --- templates ---------------------------------------------------------------

export function useTemplates() {
  return useQuery({
    queryKey: keys.templates,
    queryFn: async () => unwrap(await client.GET("/api/templates")),
  });
}

export function useTemplatePlaceholders(name: string | null) {
  return useQuery({
    enabled: !!name,
    queryKey: keys.templatePlaceholders(name ?? ""),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/templates/{name}/placeholders", {
          params: { path: { name: name! } },
        }),
      ),
  });
}

export function useTemplateFields(name: string | null) {
  return useQuery({
    enabled: !!name,
    queryKey: keys.templateFields(name ?? ""),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/templates/{name}/fields", {
          params: { path: { name: name! } },
        }),
      ),
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(await client.POST("/api/templates", { body: { name } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.templates }),
  });
}

export function useRenameTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ name, newName }: { name: string; newName: string }) =>
      unwrap(
        await client.POST("/api/templates/{name}/rename", {
          params: { path: { name } },
          body: { new_name: newName },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.templates }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(await client.DELETE("/api/templates/{name}", { params: { path: { name } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.templates }),
  });
}

export function useOpenInWord() {
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(
        await client.POST("/api/templates/{name}/open-in-word", {
          params: { path: { name } },
        }),
      ),
  });
}

export function useSetTemplateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ name, categorie }: { name: string; categorie: string | null }) =>
      unwrap(
        await client.PUT("/api/templates/{name}/category", {
          params: { path: { name } },
          body: { categorie },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.templates });
      qc.invalidateQueries({ queryKey: keys.categories });
    },
  });
}

export function useSetTemplateFields() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ name, fields }: { name: string; fields: Field[] }) =>
      unwrap(
        await client.PUT("/api/templates/{name}/fields", {
          params: { path: { name } },
          body: fields,
        }),
      ),
    onSuccess: (_d, v) =>
      qc.invalidateQueries({ queryKey: keys.templateFields(v.name) }),
  });
}

// --- categories --------------------------------------------------------------

export function useCategories() {
  return useQuery({
    queryKey: keys.categories,
    queryFn: async () => unwrap(await client.GET("/api/categories")),
  });
}

// --- mail templates ----------------------------------------------------------

export function useMailTemplates() {
  return useQuery({
    queryKey: keys.mailTemplates,
    queryFn: async () => unwrap(await client.GET("/api/mail-templates")),
  });
}

export function useCreateMailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: MailTemplateIn) =>
      unwrap(await client.POST("/api/mail-templates", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.mailTemplates }),
  });
}

export function useUpdateMailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: MailTemplateIn }) =>
      unwrap(
        await client.PUT("/api/mail-templates/{tid}", {
          params: { path: { tid: id } },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.mailTemplates }),
  });
}

export function useDeleteMailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/mail-templates/{tid}", { params: { path: { tid: id } } }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.mailTemplates }),
  });
}

export function useSetDefaultMailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.POST("/api/mail-templates/{tid}/default", {
          params: { path: { tid: id } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.mailTemplates }),
  });
}

// --- printers + settings -----------------------------------------------------

export function usePrinters() {
  return useQuery({
    queryKey: keys.printers,
    queryFn: async () => unwrap(await client.GET("/api/printers")),
  });
}

export function useSetPrinter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (printer_name: string) =>
      unwrap(await client.PUT("/api/settings/printer", { body: { printer_name } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.printers }),
  });
}

export function usePrintConfig(docType: string | null) {
  return useQuery({
    enabled: !!docType,
    queryKey: ["settings", "print", docType],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/settings/print/{doc_type}", {
          params: { path: { doc_type: docType! } },
        }),
      ),
  });
}

export function useSetPrintConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      docType,
      paper,
      color,
    }: {
      docType: string;
      paper: string | null;
      color: string | null;
    }) =>
      unwrap(
        await client.PUT("/api/settings/print/{doc_type}", {
          params: { path: { doc_type: docType } },
          body: { paper, color },
        }),
      ),
    onSuccess: (_d, v) =>
      qc.invalidateQueries({ queryKey: ["settings", "print", v.docType] }),
  });
}

/** Lance un test d'impression (202 + job) puis suit la progression en SSE. */
export function useTestPrinter() {
  return useMutation({
    mutationFn: async ({
      printerName,
      onEvent,
    }: {
      printerName: string;
      onEvent: (e: JobEvent) => void;
    }) => {
      const accepted = unwrap(
        await client.POST("/api/printers/test", { body: { printer_name: printerName } }),
      );
      await streamJob(accepted.job_id, onEvent);
    },
  });
}

// --- actes -------------------------------------------------------------------

export function useActes(
  search: string,
  includeInactive: boolean,
  categorie?: string,
) {
  return useQuery({
    queryKey: keys.actes(search, includeInactive, categorie),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/actes", {
          params: {
            query: {
              search,
              include_inactive: includeInactive,
              // `categorie` absent => toutes catégories ; sentinelle « (sans) »
              // gérée côté serveur (actes sans catégorie).
              ...(categorie ? { categorie } : {}),
            },
          },
        }),
      ),
  });
}

// Catégories distinctes du référentiel : alimente le filtre déroulant et les
// suggestions de saisie. Invalidé avec les actes (clé préfixée « actes »).
export function useActeCategories(includeInactive = false) {
  return useQuery({
    queryKey: keys.acteCategories(includeInactive),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/actes/categories", {
          params: { query: { include_inactive: includeInactive } },
        }),
      ),
  });
}

export function useCreateActe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ActeIn) => unwrap(await client.POST("/api/actes", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["actes"] }),
  });
}

export function useUpdateActe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ActeIn }) =>
      unwrap(
        await client.PUT("/api/actes/{acte_id}", {
          params: { path: { acte_id: id } },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["actes"] }),
  });
}

export function useSetActeActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, actif }: { id: number; actif: boolean }) =>
      unwrap(
        await client.POST("/api/actes/{acte_id}/active", {
          params: { path: { acte_id: id } },
          body: { actif },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["actes"] }),
  });
}

/** Exporte le référentiel d'actes en .xlsx (téléchargement authentifié). */
export function useExportActes() {
  return useMutation({
    mutationFn: async (includeInactive: boolean) =>
      downloadFile("/api/actes/export", "referentiel_actes.xlsx", {
        include_inactive: includeInactive,
      }),
  });
}

/**
 * Importe un .xlsx du référentiel (upload multipart — fetch direct, comme
 * useImportFacture). Renvoie le compte-rendu (créés / mis à jour / ignorés +
 * lignes en erreur) et invalide la liste des actes.
 */
export function useImportActes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<ActeImport> => {
      const fd = new FormData();
      fd.append("file", file);
      const resp = await fetch(`${backend.baseUrl}/api/actes/import`, {
        method: "POST",
        headers: { Authorization: `Bearer ${backend.token}` },
        body: fd,
      });
      if (!resp.ok) throw await resp.json();
      return resp.json() as Promise<ActeImport>;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["actes"] }),
  });
}
