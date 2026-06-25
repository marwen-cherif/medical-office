import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Deux issues à l'enregistrement, pour les fenêtres de **création** d'acte / de plan :
 * action principale « Enregistrer » (type=submit → enregistrer seulement, défaut inchangé) +
 * « Enregistrer + générer la note » qui enchaîne vers la modale de génération. Le choix
 * « imprimer ou non » se fait dans cette modale de note (elle a déjà ses boutons « Générer »
 * et « Générer et imprimer »), inutile de le dupliquer ici. Ne pas afficher en édition.
 */
export function SaveWithNoteButton({
  disabled,
  onGenerate,
}: {
  disabled?: boolean;
  /** « Enregistrer + générer la note » : crée le(s) acte(s) puis ouvre la modale de note. */
  onGenerate: () => void;
}) {
  return (
    <>
      <Button type="submit" disabled={disabled}>
        Enregistrer
      </Button>
      <Button type="button" variant="secondary" disabled={disabled} onClick={onGenerate}>
        <FileText className="size-4" /> Enregistrer + générer la note
      </Button>
    </>
  );
}
