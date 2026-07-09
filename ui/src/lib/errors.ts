/**
 * Traduction des codes d'erreur structurés du backend (cf. crm/server.py) en
 * messages français présentés à l'utilisateur (tâche 3.5).
 */

export type ApiErrorBody = { error: { code: string; message: string } };

const FR: Record<string, string> = {
  WORD_UNAVAILABLE:
    "Microsoft Word est indisponible. Vérifiez qu'il est installé et fermez les fenêtres ouvertes.",
  PRINTER_NOT_FOUND: "Imprimante introuvable. Vérifiez qu'elle est connectée et installée.",
  PRINT_FAILED: "L'impression a échoué.",
  TEMPLATE_INVALID: "Le modèle est illisible ou mal formé.",
  TEMPLATE_EXISTS: "Un modèle portant ce nom existe déjà.",
  SCHEMA_TOO_NEW:
    "La base de données provient d'une version plus récente de l'application. Mettez l'application à jour.",
  VALIDATION_ERROR: "Les informations saisies sont invalides.",
  NOT_FOUND: "Élément introuvable.",
  UNAUTHORIZED: "Session non autorisée. Relancez l'application.",
  NOT_READY: "Le service n'est pas encore prêt. Réessayez dans un instant.",
};

/** Message FR pour un code donné (repli sur le message brut du backend). */
export function messageForCode(code: string, fallback?: string): string {
  return FR[code] ?? fallback ?? "Une erreur est survenue.";
}

/** Extrait un message lisible d'une erreur quelconque (réponse API ou exception). */
export function humanizeError(err: unknown): string {
  if (err && typeof err === "object" && "error" in err) {
    const body = err as ApiErrorBody;
    if (body.error?.code) return messageForCode(body.error.code, body.error.message);
  }
  if (err instanceof Error) return err.message;
  return "Une erreur est survenue.";
}
