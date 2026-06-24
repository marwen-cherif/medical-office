"""Interface Flet du mini-CRM Cabinet Dr Aslem Gouiaa.

Lancement : python -m crm  (ou crm_app.py). Le script CLI historique reste
inchange et fonctionnel de son cote.
"""

from __future__ import annotations

import calendar
import json
import math
import re
import sqlite3
import sys
import threading
import time
import types
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import flet as ft
from flet import canvas as cv

from src.doc_filler import classify_placeholders, extract_placeholders

from . import backup, generator, print_settings, printing, repo, templates, version
from .db import SchemaTooNewError, connect
from .repo import Document, Job, Paiement, Patient, TemplateField

# --- Palette (inspiree de perio-dentalclinic.com : marine + turquoise) --------
NAVY = "#10357F"        # bleu marine : accent principal (boutons, texte, icones)
TEAL = "#62EBE2"        # turquoise du cabinet : surbrillances, avatars, voiles
TEAL_DARK = "#0C8B82"   # turquoise lisible pour texte/icones sur fond clair
BG = "#F2F5FA"          # fond froid clair detachant les cartes blanches
SURFACE = "#FFFFFF"
TEXT = "#191919"        # quasi noir du site (titres, corps)
MUTED = "#55585A"       # gris fonce lisible (WCAG AA)
BORDER = "#DCE3EC"      # bordure froide visible
GREEN = "#1E7E45"       # vert fonce (encaisse / envoye)
RED = "#B5271B"         # rouge fonce (erreurs)
AMBER = "#B45309"       # ambre fonce (succes partiel d'un job)


# Cle `meta` memorisant l'imprimante cible choisie dans Parametrage > Imprimante.
PRINTER_KEY = "printer_name"

# Cle `meta` memorisant la categorie de modeles dediee aux NOTES D'HONORAIRES
# (choisie dans Parametrage > Modeles). Le bouton « Note d'honoraires » de la fiche
# patient ne propose que les modeles de cette categorie ; la generation generique
# « Generer un document » l'exclut.
NOTE_CAT_KEY = "note_honoraire_categorie"
# Categorie par defaut si le reglage n'est pas defini : convention « Notes
# d'honoraires ». Ainsi, ranger un modele dans une categorie ainsi nommee suffit,
# sans configuration prealable (le reglage permet d'en choisir une autre).
NOTE_CAT_DEFAULT = "Notes d'honoraires"

# Reglages d'impression par type (format papier / couleur). Libelles d'affichage
# (dropdowns Parametrage) et libelles courts pour l'audit `document_imprime`.
# `None` = « Defaut imprimante » (repli neutre, cf. crm/print_settings.py).
_PAPER_OPTIONS = [(None, "Défaut imprimante"), ("A4", "A4"), ("A5", "A5")]
_COLOR_OPTIONS = [(None, "Défaut imprimante"), ("color", "Couleur"), ("mono", "Noir & blanc")]
_PAPER_AUDIT = {"A4": "A4", "A5": "A5"}
_COLOR_AUDIT = {"color": "Couleur", "mono": "N&B"}


def _print_audit_suffix(paper: str | None, color: str | None) -> str:
    """Suffixe « (A5, N&B) » pour l'audit, ou chaine vide si aucun reglage."""
    parts = [lbl for lbl in (_PAPER_AUDIT.get(paper or ""), _COLOR_AUDIT.get(color or "")) if lbl]
    return f" ({', '.join(parts)})" if parts else ""


def _fmt_prix(value: float | None) -> str:
    """Prix au format francais d'affichage : espace pour les milliers, virgule
    decimale, 2 decimales (ex. 1800 -> « 1 800,00 »).

    Note : `src.doc_filler.format_montant` (utilise dans les modeles Word) emploie
    3 decimales ; ici l'affichage CRM des montants est a 2 decimales (cf. paiements/
    depenses), on garde donc la meme convention pour le referentiel d'actes.
    """
    return f"{(value or 0):,.2f}".replace(",", " ").replace(".", ",")


def _cat_eq(a: str | None, b: str | None) -> bool:
    """Egalite de categorie tolerante (espaces de bord + casse ignores).

    La categorie cible des notes d'honoraires (reglage) et celle portee par un
    modele viennent de saisies libres distinctes : on compare sans se faire piéger
    par « Notes d'honoraires » vs « notes d'honoraires  »."""
    return (a or "").strip().casefold() == (b or "").strip().casefold()


_STATUT_LABELS = {
    "brouillon": ("Brouillon", TEAL_DARK),
    "genere": ("Généré", MUTED),
    "en_attente_envoi": ("En attente d'envoi", NAVY),
    "envoye": ("Envoyé", GREEN),
    "erreur": ("Erreur génération", RED),
    "erreur_envoi": ("Erreur envoi", RED),
}

# Statuts cibles du traitement par lot selon l'action choisie.
_BATCH_STATUTS = {
    "generation": ["brouillon"],
    "envoi": ["en_attente_envoi", "erreur_envoi"],
}

# Couleurs des statuts de job / lignes de job.
_JOB_STATUT_LABELS = {
    "en_cours": ("En cours", NAVY),
    "termine": ("Terminé", GREEN),
    "termine_partiel": ("Succès partiel", AMBER),
    "erreur": ("Erreur", RED),
    "interrompu": ("Interrompu", AMBER),
}
_JOB_ITEM_LABELS = {
    "ok": ("OK", GREEN),
    "skip": ("Ignoré", MUTED),
    "erreur": ("Erreur", RED),
}

# Modes d'encaissement d'un paiement (cle stockee -> libelle affiche).
_MODE_LABELS = {
    "especes": "Espèces",
    "cheque": "Chèque",
    "virement": "Virement",
}

# Statuts d'une depense fournisseur (cle -> libelle + couleur de chip).
_DEPENSE_STATUT_LABELS = {
    "en_attente": ("À régler", NAVY),
    "regle_partiellement": ("Réglé partiellement", AMBER),
    "regle": ("Réglé", GREEN),
}

# Journal d'audit -> présentation de l'onglet Historique de la fiche patient :
# type d'action -> (catégorie de filtre, icône, libellé lisible). La catégorie
# alimente les filtres (Fiche / Plans / Actes / Documents / Règlements) ; un type
# absent retombe sur la catégorie « autre » et _humanize() (anciennes lignes).
_AUDIT_META = {
    "fiche_creee": ("fiche", ft.Icons.PERSON_ADD, "Fiche créée"),
    "fiche_modifiee": ("fiche", ft.Icons.EDIT, "Fiche modifiée"),
    "plan_cree": ("plans", ft.Icons.ADD_CHART, "Plan créé"),
    "plan_modifie": ("plans", ft.Icons.EDIT_NOTE, "Plan modifié"),
    "plan_supprime": ("plans", ft.Icons.DELETE_OUTLINE, "Plan supprimé"),
    "acte_ajoute": ("actes", ft.Icons.ADD, "Acte ajouté"),
    "acte_modifie": ("actes", ft.Icons.EDIT, "Acte modifié"),
    "acte_supprime": ("actes", ft.Icons.DELETE_OUTLINE, "Acte supprimé"),
    "acte_regle": ("reglements", ft.Icons.PAYMENTS, "Acte réglé"),
    "reglement_cascade": ("reglements", ft.Icons.PAYMENTS, "Règlement réparti"),
    "paiement_encaisse": ("reglements", ft.Icons.CHECK_CIRCLE, "Paiement encaissé"),
    "paiement_annule": ("reglements", ft.Icons.CANCEL, "Paiement annulé"),
    "document_genere": ("documents", ft.Icons.DESCRIPTION, "Document généré"),
    "note_honoraires_generee": ("documents", ft.Icons.RECEIPT_LONG,
                                "Note d'honoraires générée"),
    "document_envoye": ("documents", ft.Icons.SEND, "Document envoyé"),
    "document_imprime": ("documents", ft.Icons.PRINT, "Document imprimé"),
    "brouillon_cree": ("documents", ft.Icons.NOTE_ADD, "Brouillon créé"),
    "brouillon_modifie": ("documents", ft.Icons.EDIT, "Brouillon modifié"),
    "brouillon_supprime": ("documents", ft.Icons.DELETE_OUTLINE, "Brouillon supprimé"),
}

# Filtres de l'onglet Historique (clé de catégorie -> libellé du chip).
_AUDIT_FILTERS = (
    ("tous", "Tous"), ("fiche", "Fiche"), ("plans", "Plans"),
    ("actes", "Actes"), ("documents", "Documents"), ("reglements", "Règlements"),
)

# Formats acceptes en saisie manuelle d'une date (le 1er sert aussi a l'affichage).
_DATE_FORMATS_FR = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d")


def _iso_to_fr(iso: str) -> str:
    """Date ISO (AAAA-MM-JJ) -> affichage FR (JJ/MM/AAAA). Tolere une valeur vide."""
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _fr_to_iso(value: str) -> tuple[str | None, bool]:
    """Saisie libre -> (date ISO ou None, valide?).

    Retourne (None, True) pour une saisie vide (champ facultatif), (iso, True)
    pour une date reconnue, (None, False) pour une saisie non vide invalide.
    """
    value = (value or "").strip()
    if not value:
        return None, True
    for fmt in _DATE_FORMATS_FR:
        try:
            return datetime.strptime(value, fmt).date().isoformat(), True
        except ValueError:
            continue
    return None, False


def _mask_date_fr(raw: str) -> str:
    """Formate une saisie au format JJ/MM/AAAA au fil de la frappe.

    Ne garde que les chiffres (max 8) et insere les '/' aux bons endroits :
    « 10101990 » -> « 10/10/1990 », « 1010 » -> « 10/10 ». Les caracteres non
    numeriques sont ignores, ce qui rend la saisie tolerante (le '/' tape a la
    main est reconstruit, les lettres sont rejetees).
    """
    digits = "".join(c for c in (raw or "") if c.isdigit())[:8]
    parts = [digits[:2], digits[2:4], digits[4:8]]
    return "/".join(p for p in parts if p)


def _iter_controls(ctrl):
    """Parcourt recursivement l'arbre d'un controle (content / controls / actions)."""
    if ctrl is None:
        return
    yield ctrl
    content = getattr(ctrl, "content", None)
    if isinstance(content, ft.Control):
        yield from _iter_controls(content)
    for child in (getattr(ctrl, "controls", None) or []):
        yield from _iter_controls(child)
    for child in (getattr(ctrl, "actions", None) or []):
        yield from _iter_controls(child)


def _select_all_on_focus(field: ft.TextField) -> None:
    """Au focus, selectionne tout le texte du champ pour faciliter la re-saisie.

    Pratique quand un champ a une valeur initiale (ex. montant « 0 ») : taper
    remplace directement la valeur au lieu de l'allonger. Compose avec un
    `on_focus` deja defini, le cas echeant.
    """
    prev = field.on_focus

    def _on_focus(e):
        val = field.value or ""
        if val:
            field.selection = ft.TextSelection(base_offset=0, extent_offset=len(val))
            field.update()
        if prev:
            prev(e)

    field.on_focus = _on_focus


def _date_iso(field: ft.TextField) -> str:
    """ISO (AAAA-MM-JJ) depuis un champ date editable FR ; '' si vide ou invalide.

    Pratique pour les filtres periode, ou une saisie partielle/erronee se ramene
    a « aucune borne » sans bloquer la requete.
    """
    iso, _ = _fr_to_iso(field.value)
    return iso or ""

PAGE_SIZE = 12  # nombre de lignes affichees par page dans les listes
MAIL_POLL_SECONDS = 600  # auto-refresh du suivi Mailjet (ouvertures/clics) : 10 min

# Libelles FR du calendrier personnalise (semaine commencant le lundi).
_MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
            "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
_JOURS_FR = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]

# --- Registre des raccourcis clavier (source unique : pilote a la fois le
# dispatch clavier dans _on_key ET le texte des infobulles, pour que la
# legende affichee ne diverge jamais du comportement reel). -------------------
SC_NAV = {0: "Ctrl+1", 1: "Ctrl+2", 2: "Ctrl+3", 3: "Ctrl+4", 4: "Ctrl+5", 5: "Ctrl+6"}
SC_NEW = "Ctrl+N"          # « Nouveau » contextuel selon la vue
SC_EDIT = "Ctrl+M"         # Modifier (fiche patient / prestataire)
SC_SEARCH = "Ctrl+F"       # focus du champ de recherche
SC_IMPORT = "Ctrl+I"       # importer une facture (fiche prestataire)
SC_SAVE = "Ctrl+S"         # enregistrer (brouillon ; parametres imprimante)
SC_PRINT = "Ctrl+P"        # imprimer / generer et imprimer
SC_PREV = "Ctrl+←"         # page precedente
SC_NEXT = "Ctrl+→"         # page suivante
SC_CLOSE = "Échap"         # fermer un dialogue / revenir au detail
SC_SUBMIT = "Ctrl+Entrée"  # valider un dialogue


class CrmApp:
    def __init__(self, page: ft.Page, conn: sqlite3.Connection):
        self.page = page
        self.conn = conn
        self.current_patient: Patient | None = None
        self._busy = False  # garde anti double-clic (generation/envoi)
        self._job_running = False  # garde : un seul job par lot a la fois
        self.current_view = "patients"     # vue active (pilote les raccourcis contextuels)
        self.current_job_id: int | None = None  # job ouvert en vue detail
        self._dialog_submit = None         # callback du bouton primaire du dialogue ouvert
        # Raccourcis additionnels du dialogue ouvert : {lettre majuscule -> callback}
        # (ex. {"P": generer+imprimer, "S": enregistrer brouillon}). Cf. _on_key.
        self._dialog_shortcuts: dict[str, Callable] = {}
        # Actions de la page Parametrage > Imprimante, exposees au clavier
        # (Ctrl+S enregistrer / Ctrl+P test) quand cette page est affichee.
        self._printer_save_action: Callable | None = None
        self._printer_test_action: Callable | None = None
        # Pagination de la fiche patient (documents / paiements), reinitialisee
        # a 0 quand on ouvre un autre patient.
        self.detail_docs_page = 0
        self.detail_paie_page = 0
        # Onglet actif de la fiche patient (0=Plans&actes, 1=Documents,
        # 2=Reglements, 3=Historique) et filtre de l'onglet Historique : conserves
        # entre deux rendus de la MEME fiche (pagination, auto-polling), remis a
        # zero a l'ouverture d'un autre patient.
        self.detail_tab = 0
        self.detail_hist_filter = "tous"

        # --- Recherche, filtres et pagination (etat persistant entre les rendus) ---
        # Patients
        self.search = self._search_field(
            "Rechercher un patient…", lambda e: self._reset_and("patients"))
        self.patients_filter = ft.Dropdown(
            value="tous", width=190, border_radius=10, content_padding=10,
            bgcolor=SURFACE, color=TEXT,
            text_style=ft.TextStyle(color=TEXT),
            border_color=BORDER, focused_border_color=NAVY,
            on_select=lambda e: self._reset_and("patients"),
            options=[
                ft.dropdown.Option(key="tous", text="Tous les patients"),
                ft.dropdown.Option(key="email", text="Avec email"),
                ft.dropdown.Option(key="impayes", text="Avec impayés"),
            ],
        )
        self.patients_page = 0
        # Paiements
        self.paie_search = self._search_field(
            "Rechercher un patient…", lambda e: self._reset_and("paiements"))
        self.paie_statut = ft.Dropdown(
            value="en_attente", width=190, border_radius=10, content_padding=10,
            bgcolor=SURFACE, color=TEXT,
            text_style=ft.TextStyle(color=TEXT),
            border_color=BORDER, focused_border_color=NAVY,
            on_select=lambda e: self._reset_and("paiements"),
            options=[
                ft.dropdown.Option(key="en_attente", text="À recouvrer"),
                ft.dropdown.Option(key="encaisse", text="Encaissés"),
                ft.dropdown.Option(key="tous", text="Tous"),
            ],
        )
        # Filtre periode : pre-rempli sur le mois courant (du 1er au dernier jour).
        _today = date.today()
        _first = _today.replace(day=1)
        _last = date(_today.year, _today.month,
                     calendar.monthrange(_today.year, _today.month)[1])
        _on_dates = lambda: self._reset_and("paiements")
        self.paie_date_range, self.paie_date_from, self.paie_date_to = self._date_range_field(
            _first.isoformat(), _last.isoformat(), on_change=_on_dates)
        self.paie_page = 0
        # Prestataires (annuaire fournisseurs)
        self.pr_search = self._search_field(
            "Rechercher un prestataire…", lambda e: self._reset_and("prestataires"))
        self.pr_page = 0
        self.current_prestataire = None
        self.detail_pr_factures_page = 0
        self.detail_pr_depenses_page = 0
        # Finances : onglet actif du sous-menu (Paiements / Depenses).
        self.finances_tab = "paiements"
        # Depenses (sous-onglet Finances)
        self.dep_search = self._search_field(
            "Rechercher un prestataire…", lambda e: self._reset_and("depenses"))
        self.dep_statut = ft.Dropdown(
            value="tous", width=210, border_radius=10, content_padding=10,
            bgcolor=SURFACE, color=TEXT, text_style=ft.TextStyle(color=TEXT),
            border_color=BORDER, focused_border_color=NAVY,
            on_select=lambda e: self._reset_and("depenses"),
            options=[
                ft.dropdown.Option(key="en_attente", text="À régler"),
                ft.dropdown.Option(key="regle_partiellement", text="Réglé partiellement"),
                ft.dropdown.Option(key="regle", text="Réglé"),
                ft.dropdown.Option(key="tous", text="Tous"),
            ],
        )
        _dep_on = lambda: self._reset_and("depenses")
        self.dep_date_range, self.dep_date_from, self.dep_date_to = self._date_range_field(
            _first.isoformat(), _last.isoformat(), on_change=_dep_on)
        self.dep_page = 0
        # Parametrage : onglet actif du sous-menu (Modeles de documents / Emails).
        self.param_tab = "templates"
        # Modeles de documents
        self.tpl_search = self._search_field(
            "Rechercher un modèle…", lambda e: self._reset_and("templates"))
        self.tpl_page = 0
        # Modeles d'email
        self.mail_search = self._search_field(
            "Rechercher un modèle…", lambda e: self._reset_and("mail"))
        self.mail_page = 0
        # Referentiel d'actes (catalogue tarife)
        self.actes_search = self._search_field(
            "Rechercher un acte…", lambda e: self._reset_and("actes"))
        self.actes_page = 0
        self.actes_inclure_inactifs = False
        # Travaux : onglet actif du sous-menu (Documents / liste des jobs).
        self.travaux_tab = "documents"
        # Sous-vue DOCUMENTS : liste des lignes de documents (jointes au patient).
        self.doc_search = self._search_field(
            "Rechercher un patient…", lambda e: self._reset_and("documents"))
        self.doc_statut = ft.Dropdown(
            value="tous", width=190, border_radius=10, content_padding=10,
            bgcolor=SURFACE, color=TEXT, text_style=ft.TextStyle(color=TEXT),
            border_color=BORDER, focused_border_color=NAVY,
            on_select=lambda e: self._on_doc_statut_change(),
            options=[
                ft.dropdown.Option(key="tous", text="Tous les statuts"),
                ft.dropdown.Option(key="brouillon", text="Brouillon"),
                ft.dropdown.Option(key="genere", text="Généré"),
                ft.dropdown.Option(key="en_attente_envoi", text="En attente d'envoi"),
                ft.dropdown.Option(key="envoye", text="Envoyé"),
                ft.dropdown.Option(key="erreur", text="Erreur génération"),
                ft.dropdown.Option(key="erreur_envoi", text="Erreur envoi"),
            ],
        )
        _docs_on = lambda: self._reset_and("documents")
        self.doc_date_range, self.doc_date_from, self.doc_date_to = self._date_range_field(
            _first.isoformat(), _last.isoformat(), on_change=_docs_on)
        self.doc_page = 0
        self.doc_results = ft.Container()
        self.doc_pager = ft.Container()
        # Traitement par lot (page Documents) : ids de documents coches + barre
        # d'action contextuelle (apparait selon le filtre de statut).
        self.doc_selected: set[int] = set()
        self.doc_batch_bar = ft.Container()
        # Travaux (jobs) : periode pre-remplie sur le mois courant (limite le chargement).
        self.jobs_page = 0
        _jobs_on = lambda: self._reset_and("jobs")
        self.jobs_date_range, self.jobs_date_from, self.jobs_date_to = self._date_range_field(
            _first.isoformat(), _last.isoformat(), on_change=_jobs_on)
        # Tableau de bord : periode pre-remplie sur le mois courant.
        _dash_on = lambda: self._refresh_dashboard()
        self.dash_date_range, self.dash_date_from, self.dash_date_to = self._date_range_field(
            _first.isoformat(), _last.isoformat(), on_change=_dash_on)

        # Conteneurs persistants des parties dynamiques (liste + pagination).
        # On reconstruit le scaffold d'une vue une seule fois ; ensuite, lors
        # d'une recherche, on ne met a jour QUE ces conteneurs pour ne pas
        # re-parenter le champ de recherche (ce qui lui ferait perdre le focus).
        self.patients_results = ft.Container()
        self.patients_pager = ft.Container()
        self.paie_summary = ft.Container()
        self.paie_results = ft.Container()
        self.paie_pager = ft.Container()
        self.tpl_results = ft.Container()
        self.tpl_pager = ft.Container()
        self.mail_results = ft.Container()
        self.mail_pager = ft.Container()
        self.actes_results = ft.Container()
        self.actes_pager = ft.Container()
        self.jobs_results = ft.Container()
        self.jobs_pager = ft.Container()
        self.job_detail_container = ft.Container()
        self.dash_results = ft.Container()
        self.pr_results = ft.Container()
        self.pr_pager = ft.Container()
        self.dep_summary = ft.Container()
        self.dep_results = ft.Container()
        self.dep_pager = ft.Container()

        # Selecteur de fichier (import de factures) : service Flet (page.services).
        # API recente : pick_files() est une coroutine qui renvoie la liste de fichiers.
        self.file_picker = ft.FilePicker()
        try:
            self.page.services.append(self.file_picker)
        except (AttributeError, TypeError):
            self.page.services = [self.file_picker]

        self.body = ft.Container(expand=True, padding=24, bgcolor=BG)
        self.page.on_keyboard_event = self._on_key
        self._build_shell()
        self.show_dashboard()
        self._start_status_poller()  # suivi Mailjet (ouvertures/clics) en arriere-plan

    # --- Coquille / navigation ------------------------------------------------
    def _build_shell(self) -> None:
        def dest(icon_o, icon_f, label):
            return ft.NavigationRailDestination(
                icon=ft.Icon(icon_o, color=MUTED),
                selected_icon=ft.Icon(icon_f, color=NAVY),
                label=label,
            )

        brand = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Image(src=_asset("logo_mark.png"), width=34, height=34,
                                         fit=ft.BoxFit.CONTAIN),
                        bgcolor=SURFACE, width=44, height=44, border_radius=12,
                        border=ft.Border.all(1, BORDER),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text("Cabinet", size=12, weight=ft.FontWeight.BOLD, color=NAVY, text_align=ft.TextAlign.CENTER),
                    ft.Text("Dr Aslem Gouiaa", size=10, color=MUTED, text_align=ft.TextAlign.CENTER),
                    # Legende des raccourcis de navigation (le rail n'expose pas de
                    # tooltip par destination) : tout le sommaire au survol de l'icone.
                    ft.IconButton(
                        ft.Icons.KEYBOARD, icon_color=MUTED, icon_size=18,
                        tooltip=(
                            "Raccourcis clavier\n"
                            f"Tableau de bord {SC_NAV[0]} · Patients {SC_NAV[1]} · "
                            f"Prestataires {SC_NAV[2]} · Finances {SC_NAV[3]} · "
                            f"Travaux {SC_NAV[4]} · Paramétrage {SC_NAV[5]}\n"
                            f"Nouveau {SC_NEW} · Modifier {SC_EDIT} · Rechercher {SC_SEARCH}\n"
                            f"Importer facture {SC_IMPORT} · Enregistrer {SC_SAVE} · "
                            f"Imprimer {SC_PRINT}\n"
                            f"Page {SC_PREV}/{SC_NEXT} · Fermer {SC_CLOSE} · Valider {SC_SUBMIT}"
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            padding=ft.Padding.only(top=16, bottom=8),
        )

        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=92,
            bgcolor=SURFACE,
            expand=True,  # occupe toute la hauteur pour pousser le footer version tout en bas
            leading=brand,
            indicator_color=ft.Colors.with_opacity(0.45, TEAL),
            selected_label_text_style=ft.TextStyle(color=NAVY, weight=ft.FontWeight.BOLD, size=12),
            unselected_label_text_style=ft.TextStyle(color=MUTED, size=12),
            group_alignment=-0.9,
            destinations=[
                dest(ft.Icons.SPACE_DASHBOARD_OUTLINED, ft.Icons.SPACE_DASHBOARD, "Tableau"),
                dest(ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE, "Patients"),
                dest(ft.Icons.STOREFRONT_OUTLINED, ft.Icons.STOREFRONT, "Prestataires"),
                dest(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, ft.Icons.ACCOUNT_BALANCE_WALLET, "Finances"),
                dest(ft.Icons.WORK_OUTLINE, ft.Icons.WORK, "Travaux"),
                dest(ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Paramétrage"),
            ],
            on_change=self._on_nav,
        )
        # Sidebar = rail (extensible) + footer version épinglé tout en bas.
        sidebar = ft.Container(
            content=ft.Column(
                [self.rail, self._version_footer()],
                spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=SURFACE,
        )
        self.page.add(
            ft.Row(
                [sidebar, ft.VerticalDivider(width=1), self.body],
                expand=True,
                spacing=0,
            )
        )

    def _version_footer(self) -> ft.Control:
        """Pied du sidebar : version sémantique + tag de build (change à chaque build)."""
        return ft.Container(
            content=ft.Column([
                ft.Text(version.app_version(), size=10, weight=ft.FontWeight.BOLD,
                        color=MUTED, text_align=ft.TextAlign.CENTER),
                ft.Text(version.build_tag(), size=8, color=MUTED,
                        text_align=ft.TextAlign.CENTER, selectable=True),
            ], spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(top=4, bottom=10, left=2, right=2),
            alignment=ft.Alignment.CENTER,
            tooltip=f"Cabinet CRM {version.app_version_full()}",
        )

    def _on_nav(self, e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx == 0:
            self.show_dashboard()
        elif idx == 1:
            self.show_patients()
        elif idx == 2:
            self.show_prestataires()
        elif idx == 3:
            self.show_finances()
        elif idx == 4:
            self.show_travaux()
        else:
            self.show_parametrage()

    # --- Helpers UI -----------------------------------------------------------
    def _title(self, text: str, action: ft.Control | None = None) -> ft.Control:
        row = [ft.Text(text, size=26, weight=ft.FontWeight.BOLD, color=TEXT)]
        if action:
            row.append(ft.Container(expand=True))
            row.append(action)
        return ft.Row(row, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _card(self, content: ft.Control, padding: int = 16,
              expand: bool = False) -> ft.Container:
        return ft.Container(
            content=content,
            bgcolor=SURFACE,
            border_radius=12,
            padding=padding,
            border=ft.Border.all(1, BORDER),
            expand=expand,
        )

    def _money_summary(self, items: list[tuple[str, float, str]],
                       icon=ft.Icons.SHOPPING_CART_CHECKOUT) -> ft.Container:
        """Carte récap de montants : chaque (libellé, valeur, couleur) en colonne,
        le libellé exactement au-dessus de sa valeur, cellules de largeur égale
        séparées par un filet vertical (alignement propre, sans « · »)."""
        cells: list[ft.Control] = [ft.Icon(icon, color=NAVY)]
        for i, (label, value, color) in enumerate(items):
            if i:
                cells.append(ft.VerticalDivider(width=24, thickness=1, color=BORDER))
            cells.append(ft.Container(
                content=ft.Column([
                    ft.Text(label, color=MUTED, size=12),
                    ft.Text(f"{value:.2f}", size=20, weight=ft.FontWeight.BOLD, color=color),
                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.START, tight=True),
                expand=True,
            ))
        return self._card(ft.Row(
            cells, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12))

    def _btn(self, text, on_click, icon=None, primary=True, shortcut=None, busy=True):
        """Bouton primaire/secondaire de l'app.

        Par defaut (`busy=True`), le clic est emballe dans `_run_busy` : le bouton
        se desactive et affiche un spinner pendant l'action, ce qui empeche le
        double-clic et garantit que le premier clic est bien pris en compte.

        On passe `busy=False` quand le spinner n'a pas lieu d'etre :
        - boutons qui se contentent d'ouvrir un dialogue (action instantanee,
          le vrai traitement est derriere le bouton primaire de la modale) ;
        - boutons qui gerent deja eux-memes leur etat de chargement (generation,
          envoi, synchro) — eviter un double emballage neutralise par `_busy`.
        """
        style = ft.ButtonStyle(
            bgcolor=NAVY if primary else SURFACE,
            color=SURFACE if primary else NAVY,
            shape=ft.RoundedRectangleBorder(radius=10),
            side=None if primary else ft.BorderSide(1, NAVY),
            padding=ft.Padding.symmetric(vertical=14, horizontal=18),
        )
        # Infobulle = libelle + raccourci : c'est la « legende » accessible au survol.
        tooltip = f"{text} ({shortcut})" if shortcut else None
        btn = ft.ElevatedButton(text, icon=icon, style=style,
                                elevation=0, tooltip=tooltip)
        if busy and on_click is not None:
            handler = on_click
            btn.on_click = lambda e, b=btn: self._run_busy(b, None, lambda: handler(e))
        else:
            btn.on_click = on_click
        return btn

    def _toast(self, message: str, ok: bool = True) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                ft.Text(message, color=SURFACE),
                bgcolor=GREEN if ok else RED,
            )
        )

    def _kv_copy(self, key: str, value: str | None) -> ft.Control:
        """Comme `_kv` mais la valeur se copie dans le presse-papiers au clic.

        Utilisé pour l'email et le téléphone (fiches patient et prestataire) :
        un clic copie la valeur et affiche un toast de confirmation. Si la
        valeur est vide, on retombe sur l'affichage simple non cliquable.
        """
        if not value:
            return _kv(key, "—")

        def _copy(e):
            self.page.run_task(self.page.clipboard.set, value)
            self._toast(f"« {value} » copié dans le presse-papiers.")

        val = ft.Container(
            content=ft.Row(
                [
                    ft.Text(value, color=TEXT),
                    ft.Icon(ft.Icons.CONTENT_COPY, size=15, color=MUTED),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=_copy,
            tooltip="Cliquer pour copier",
            ink=True,
            border_radius=6,
            padding=ft.Padding.symmetric(vertical=2, horizontal=6),
        )
        return ft.Row([
            ft.Text(key, color=MUTED, width=150),
            val,
        ])

    def _show_dialog(self, dlg: ft.Control, submit=None, shortcuts=None) -> None:
        """Ouvre un AlertDialog en memorisant l'action de son bouton primaire.

        Si `submit` n'est pas fourni, on le deduit du bouton primaire du
        dialogue (l'unique ElevatedButton construit par `_btn` dans `actions`)
        et on enrichit son infobulle avec le raccourci Ctrl+Entree. Ainsi un
        seul point centralise la validation clavier ET la legende, sans avoir
        a annoter chaque dialogue. `submit` est rappele par Ctrl+Entree et
        remis a None a la fermeture.

        `shortcuts` : raccourcis additionnels du dialogue, {lettre -> callback}
        (ex. {"P": generer+imprimer}). Chaque callback est appele avec None par
        Ctrl+<lettre> tant que le dialogue est ouvert (cf. _on_key).

        Validation au clavier (systematique pour tous les formulaires) :
        - Entree depuis un champ texte simple ligne -> valide le formulaire
          (cable ici via `on_submit`), pratique pour la saisie ;
        - les champs multilignes gardent Entree pour le saut de ligne ;
        - Ctrl+Entree (gere dans `_on_key`) reste le raccourci universel, y
          compris depuis un champ multiligne, une liste deroulante ou un radio.
        """
        if submit is None and isinstance(dlg, ft.AlertDialog):
            for action in dlg.actions or []:
                if isinstance(action, ft.ElevatedButton):
                    submit = action.on_click
                    if not action.tooltip and getattr(action, "text", None):
                        action.tooltip = f"{action.text} ({SC_SUBMIT})"
                    break
        self._dialog_submit = submit
        self._dialog_shortcuts = shortcuts or {}
        # Saisie au clavier, systematique pour les champs simple ligne du
        # formulaire (les multilignes sont laisses intacts : Entree = saut de
        # ligne, et pas de select-all qui effacerait un texte qu'on complete) :
        # - select-all au focus (re-saisie immediate de la valeur) ;
        # - Entree valide le formulaire (Ctrl+Entree restant universel).
        for c in _iter_controls(dlg):
            if isinstance(c, ft.TextField) and not c.multiline:
                _select_all_on_focus(c)
                if submit is not None and c.on_submit is None:
                    c.on_submit = submit
        self.page.show_dialog(dlg)

    def _close_dialog(self) -> None:
        self._dialog_submit = None
        self._dialog_shortcuts = {}
        self.page.pop_dialog()

    # --- Raccourcis clavier ---------------------------------------------------
    def _on_key(self, e: ft.KeyboardEvent) -> None:
        """Dispatch clavier global (branche sur page.on_keyboard_event).

        Les actions globales utilisent Ctrl pour ne jamais capturer la saisie
        dans les champs texte (Flet route les evenements au niveau page quel
        que soit le focus).
        """
        # Modificateur « commande » : Ctrl sous Windows/Linux, Cmd (meta) sous macOS.
        cmd = e.ctrl or e.meta
        # Normalise les libelles du pave numerique (« Numpad 1 » -> « 1 ») pour
        # que les raccourcis chiffres fonctionnent aussi depuis le pave num.
        key = e.key[len("Numpad "):] if e.key.startswith("Numpad ") else e.key

        # 1) Un dialogue est ouvert : on lui reserve Echap / Ctrl+Entree, plus les
        #    raccourcis additionnels declares par le dialogue (Ctrl+lettre).
        if self._dialog_submit is not None:
            if key == "Escape":
                self._close_dialog()
            elif key == "Enter" and cmd:
                self._dialog_submit(None)
            elif cmd and key in self._dialog_shortcuts:
                self._dialog_shortcuts[key](None)
            return

        # 2) Portee globale.
        if cmd and key in ("1", "2", "3", "4", "5", "6"):
            idx = int(key) - 1
            self.rail.selected_index = idx
            (self.show_dashboard, self.show_patients, self.show_prestataires,
             self.show_finances, self.show_travaux, self.show_parametrage)[idx]()
        elif cmd and key == "N":
            self._new_for_current_view()
        elif cmd and key == "M":
            self._edit_current_view()
        elif cmd and key == "F":
            self._focus_search()
        elif cmd and key == "I" and self.current_view == "prestataire_detail" \
                and self.current_prestataire:
            self.page.run_task(self._pick_and_import, self.current_prestataire)
        elif cmd and key == "S" and self.current_view == "printer" \
                and self._printer_save_action:
            self._printer_save_action()
        elif cmd and key == "P" and self.current_view == "printer" \
                and self._printer_test_action:
            self._printer_test_action()
        elif cmd and key in ("Arrow Left", "Arrow Right"):
            self._page_step(-1 if key == "Arrow Left" else 1)
        elif key == "Escape" and self.current_view == "patient_detail":
            self.show_patients()
        elif key == "Escape" and self.current_view == "prestataire_detail":
            self.show_prestataires()
        elif key == "Escape" and self.current_view == "job_detail":
            self.show_jobs()

    def _new_for_current_view(self) -> None:
        """Action « Nouveau » selon la vue (Ctrl+N). Sur une fiche, « Nouveau » =
        l'action de creation propre a cette fiche (document / depense)."""
        if self.current_view == "patients":
            self._patient_dialog()
        elif self.current_view == "prestataires":
            self._prestataire_dialog()
        elif self.current_view == "depenses":
            self._depense_dialog()
        elif self.current_view == "templates":
            self._new_template_dialog()
        elif self.current_view == "mail":
            self._mail_template_dialog()
        elif self.current_view == "actes":
            self._acte_dialog()
        elif self.current_view == "patient_detail" and self.current_patient:
            self._generate_dialog(self.current_patient)
        elif self.current_view == "prestataire_detail" and self.current_prestataire:
            self._depense_dialog(self.current_prestataire)

    def _edit_current_view(self) -> None:
        """Action « Modifier » (Ctrl+M) de la fiche actuellement ouverte."""
        if self.current_view == "patient_detail" and self.current_patient:
            self._patient_dialog(self.current_patient)
        elif self.current_view == "prestataire_detail" and self.current_prestataire:
            self._prestataire_dialog(self.current_prestataire)

    def _focus_search(self) -> None:
        """Donne le focus au champ de recherche de la vue courante (s'il en a un).

        `TextField.focus()` est une coroutine dans cette version de Flet : on la
        planifie sur la boucle via `run_task` (un simple appel non attendu ne
        ferait rien). Best-effort : silencieux si la boucle n'est pas prete
        (ex. tout premier rendu au demarrage)."""
        field = {
            "patients": self.search,
            "prestataires": self.pr_search,
            "paiements": self.paie_search,
            "depenses": self.dep_search,
            "documents": self.doc_search,
            "templates": self.tpl_search,
            "mail": self.mail_search,
            "actes": self.actes_search,
        }.get(self.current_view)
        if field is None:
            return
        try:
            self.page.run_task(field.focus)
        except Exception:  # noqa: BLE001
            pass

    def _page_step(self, delta: int) -> None:
        """Page precedente/suivante de la vue active (bornee par _clamp_page)."""
        if self.current_view == "patients":
            self.patients_page += delta
            self._refresh_patients()
        elif self.current_view == "prestataires":
            self.pr_page += delta
            self._refresh_prestataires()
        elif self.current_view == "paiements":
            self.paie_page += delta
            self._refresh_paiements()
        elif self.current_view == "depenses":
            self.dep_page += delta
            self._refresh_depenses()
        elif self.current_view == "templates":
            self.tpl_page += delta
            self._refresh_templates()
        elif self.current_view == "mail":
            self.mail_page += delta
            self._refresh_mail_templates()
        elif self.current_view == "actes":
            self.actes_page += delta
            self._refresh_actes()
        elif self.current_view == "documents":
            self.doc_page += delta
            self._refresh_documents()
        elif self.current_view == "jobs":
            self.jobs_page += delta
            self._refresh_jobs()

    def _set_body(self, *controls: ft.Control) -> None:
        self.body.content = ft.Column(list(controls), spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)
        self.page.update()
        # A chaque arrivee sur une page, on place le curseur dans son champ de
        # recherche (no-op si la vue n'en a pas). Les rafraichissements (saisie,
        # pagination) passent par les conteneurs, pas par _set_body : le focus
        # n'est donc jamais vole pendant la frappe.
        self._focus_search()

    def _search_field(self, hint: str, on_change) -> ft.TextField:
        return ft.TextField(
            hint_text=hint,
            tooltip=f"Rechercher ({SC_SEARCH})",
            prefix_icon=ft.Icons.SEARCH,
            on_change=on_change,
            border_radius=10,
            height=44,
            content_padding=12,
            expand=True,
            bgcolor=SURFACE,
            color=TEXT,
            text_style=ft.TextStyle(color=TEXT),
            hint_style=ft.TextStyle(color=MUTED),
            border_color=BORDER,
            focused_border_color=NAVY,
        )

    def _reset_and(self, view: str) -> None:
        """Remet la pagination de `view` a la premiere page puis rafraichit la
        liste UNIQUEMENT (sans reconstruire le scaffold), pour que le champ de
        recherche conserve son focus pendant la saisie."""
        if view == "patients":
            self.patients_page = 0
            self._refresh_patients()
        elif view == "prestataires":
            self.pr_page = 0
            self._refresh_prestataires()
        elif view == "paiements":
            self.paie_page = 0
            self._refresh_paiements()
        elif view == "depenses":
            self.dep_page = 0
            self._refresh_depenses()
        elif view == "templates":
            self.tpl_page = 0
            self._refresh_templates()
        elif view == "mail":
            self.mail_page = 0
            self._refresh_mail_templates()
        elif view == "actes":
            self.actes_page = 0
            self._refresh_actes()
        elif view == "documents":
            self.doc_page = 0
            self._refresh_documents()
        elif view == "jobs":
            self.jobs_page = 0
            self._refresh_jobs()

    def _clamp_page(self, page: int, total: int) -> int:
        """Borne l'index de page dans [0, derniere page] selon le nb de resultats."""
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        return max(0, min(page, pages - 1))

    def _pagination(self, page: int, total: int, on_page) -> ft.Control:
        """Barre de pagination : « X–Y sur N » + boutons precedent/suivant."""
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if total:
            start = page * PAGE_SIZE + 1
            end = min(total, (page + 1) * PAGE_SIZE)
            label = f"{start}–{end} sur {total}"
        else:
            label = "0 résultat"
        return ft.Row(
            [
                ft.Text(label, color=MUTED, size=12),
                ft.Container(expand=True),
                ft.IconButton(
                    ft.Icons.CHEVRON_LEFT, icon_color=NAVY, tooltip=f"Précédent ({SC_PREV})",
                    disabled=page <= 0, on_click=lambda e: on_page(page - 1)),
                ft.Text(f"Page {page + 1} / {pages}", color=MUTED, size=12),
                ft.IconButton(
                    ft.Icons.CHEVRON_RIGHT, icon_color=NAVY, tooltip=f"Suivant ({SC_NEXT})",
                    disabled=page >= pages - 1, on_click=lambda e: on_page(page + 1)),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _run_busy(self, button: ft.Control, status: ft.Text | None, work) -> None:
        """Execute `work()` en bloquant les double-clics et en affichant un chargement.

        Desactive le bouton + affiche un spinner, puis lance `work()` dans un
        thread d'arriere-plan : sans cela, un travail bloquant (generation
        Word/PDF, envoi email) figerait la fenetre et le spinner n'aurait jamais
        le temps d'etre peint. Le bouton est reactive a la fin. En cas d'erreur,
        le message est mis dans `status` (ou un toast).
        """
        if self._busy:
            return
        self._busy = True
        button.disabled = True
        original = getattr(button, "content", None)
        button.content = ft.Row(
            [ft.ProgressRing(width=16, height=16, stroke_width=2, color=SURFACE),
             ft.Text("Veuillez patienter…", color=SURFACE)],
            tight=True, spacing=8, alignment=ft.MainAxisAlignment.CENTER,
        )
        if status is not None:
            status.value = ""
        self.page.update()  # peint l'etat de chargement AVANT de lancer le travail

        def runner() -> None:
            try:
                work()
            except Exception as exc:  # noqa: BLE001
                msg = f"Échec : {exc}"
                if status is not None:
                    status.value = msg
                    status.color = RED
                else:
                    self._toast(msg, ok=False)
            finally:
                self._busy = False
                button.disabled = False
                button.content = original
                self.page.update()

        threading.Thread(target=runner, daemon=True).start()

    def _date_field(self, label: str, initial: str = "",
                    on_change: Callable[[], None] | None = None,
                    editable: bool = True,
                    ) -> tuple[ft.Control, ft.TextField]:
        """Champ date + bouton ouvrant un calendrier FR.

        Par defaut (`editable=True`) la saisie clavier est active et affichee au
        format FR (JJ/MM/AAAA) avec un placeholder, le calendrier restant
        disponible ; la valeur s'obtient via `_date_iso`/`_fr_to_iso`. Avec
        `editable=False`, le champ est en lecture seule au format ISO (AAAA-MM-JJ).
        Retourne (row, field). `on_change`, s'il est fourni, est appele apres la
        selection d'une date (ou a chaque frappe en mode editable).
        """
        if editable:
            field = ft.TextField(
                label=label, value=_iso_to_fr(initial), hint_text="JJ/MM/AAAA",
                expand=True, keyboard_type=ft.KeyboardType.NUMBER,
            )

            def _on_type(e, f=field, cb=on_change):
                # Auto-formatage JJ/MM/AAAA : les '/' sont inseres pendant la frappe.
                masked = _mask_date_fr(f.value)
                if masked != f.value:
                    f.value = masked
                    f.update()
                if cb:
                    cb()

            field.on_change = _on_type
        else:
            field = ft.TextField(label=label, value=initial, read_only=True, expand=True)

        row = ft.Row(
            [field, ft.IconButton(
                ft.Icons.CALENDAR_MONTH, icon_color=NAVY,
                on_click=lambda e: self._open_calendar(field, on_change, fr=editable))],
            spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return row, field

    def _open_calendar(self, field: ft.TextField,
                       on_change: Callable[[], None] | None = None,
                       fr: bool = False) -> None:
        """Calendrier mensuel FR (semaine du lundi au dimanche).

        Le DatePicker Material natif ne valide qu'au clic sur OK ; ce calendrier
        maison retient la date des le clic sur le jour, puis ferme la modale.
        `fr=True` : le champ affiche/saisit au format JJ/MM/AAAA (sinon ISO).
        """
        if fr:
            iso, _ = _fr_to_iso(field.value)
        else:
            iso = field.value or None
        try:
            selected = date.fromisoformat(iso) if iso else None
        except ValueError:
            selected = None
        today = date.today()
        cursor = selected or today
        state = {"year": cursor.year, "month": cursor.month}

        title = ft.Text(weight=ft.FontWeight.BOLD, size=16, color=NAVY)
        grid = ft.Column(spacing=4, tight=True)

        def pick(d: date) -> None:
            field.value = _iso_to_fr(d.isoformat()) if fr else d.isoformat()
            self._close_dialog()
            self.page.update()
            if on_change is not None:
                on_change()

        def render() -> None:
            y, m = state["year"], state["month"]
            title.value = f"{_MOIS_FR[m - 1]} {y}"
            rows = [ft.Row(
                [ft.Container(
                    ft.Text(j, size=12, weight=ft.FontWeight.BOLD, color=MUTED,
                            text_align=ft.TextAlign.CENTER),
                    width=38, alignment=ft.Alignment.CENTER) for j in _JOURS_FR],
                spacing=2)]
            for week in calendar.Calendar(firstweekday=0).monthdayscalendar(y, m):
                cells = []
                for day in week:
                    if day == 0:
                        cells.append(ft.Container(width=38, height=38))
                        continue
                    d = date(y, m, day)
                    is_sel = selected is not None and d == selected
                    is_today = d == today
                    cells.append(ft.Container(
                        ft.Text(str(day), text_align=ft.TextAlign.CENTER,
                                color=SURFACE if is_sel else TEXT,
                                weight=ft.FontWeight.BOLD if (is_sel or is_today) else None),
                        width=38, height=38, alignment=ft.Alignment.CENTER,
                        border_radius=19, ink=True,
                        bgcolor=NAVY if is_sel else (TEAL if is_today else None),
                        on_click=lambda e, dd=d: pick(dd),
                    ))
                rows.append(ft.Row(cells, spacing=2))
            grid.controls = rows

        def shift(delta: int) -> None:
            m = state["month"] - 1 + delta
            state["year"] += m // 12
            state["month"] = m % 12 + 1
            render()
            self.page.update()

        render()
        header = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=NAVY, on_click=lambda e: shift(-1)),
            ft.Container(title, expand=True, alignment=ft.Alignment.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=NAVY, on_click=lambda e: shift(1)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        dlg = ft.AlertDialog(
            content=ft.Container(
                ft.Column([header, grid], tight=True, spacing=8), width=300),
            actions=[ft.TextButton("Annuler", on_click=lambda e: self._close_dialog())],
            bgcolor=SURFACE,
        )
        self._show_dialog(dlg)

    # --- Filtre periode : un seul champ pour la plage « du / au » -------------
    @staticmethod
    def _format_range(from_field: ft.TextField, to_field: ft.TextField) -> str:
        """Libelle lisible de la plage a partir des deux champs (valeurs FR)."""
        f = (from_field.value or "").strip()
        t = (to_field.value or "").strip()
        if f and t:
            return f"{f} → {t}"
        if f:
            return f"À partir du {f}"
        if t:
            return f"Jusqu'au {t}"
        return "Toutes les dates"

    def _date_range_field(
        self, initial_from: str = "", initial_to: str = "",
        on_change: Callable[[], None] | None = None, label: str = "Période",
    ) -> tuple[ft.Control, ft.TextField, ft.TextField]:
        """Champ unique de selection d'une plage de dates (remplace deux « Du/Au »).

        Renvoie (control, from_field, to_field). `from_field`/`to_field` sont des
        champs *cachés* qui portent la valeur (format FR) : on les passe a
        `_date_iso` exactement comme les anciens champs simples, donc le code de
        filtrage (lecture des bornes) reste inchange. `control` est l'unique
        widget affiche : un champ en lecture seule resumant la plage + un bouton
        calendrier qui ouvre le selecteur de plage.
        """
        from_field = ft.TextField(value=_iso_to_fr(initial_from))
        to_field = ft.TextField(value=_iso_to_fr(initial_to))
        display = ft.TextField(
            label=label, read_only=True, expand=True,
            value=self._format_range(from_field, to_field),
            prefix_icon=ft.Icons.DATE_RANGE,
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
        )

        def open_picker(e=None):
            self._open_range_calendar(from_field, to_field, display, on_change)

        display.on_click = open_picker
        control = ft.Row(
            [display, ft.IconButton(
                ft.Icons.CALENDAR_MONTH, icon_color=NAVY, tooltip="Choisir une période",
                on_click=open_picker)],
            spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return control, from_field, to_field

    def _apply_range(self, from_field: ft.TextField, to_field: ft.TextField,
                     display: ft.TextField, start, end,
                     on_change: Callable[[], None] | None) -> None:
        """Ecrit la plage (ou la vide) dans les champs, ferme et rafraichit."""
        from_field.value = _iso_to_fr(start.isoformat()) if start else ""
        to_field.value = _iso_to_fr(end.isoformat()) if end else ""
        display.value = self._format_range(from_field, to_field)
        self._close_dialog()
        self.page.update()
        if on_change is not None:
            on_change()

    def _open_range_calendar(self, from_field: ft.TextField, to_field: ft.TextField,
                             display: ft.TextField,
                             on_change: Callable[[], None] | None = None) -> None:
        """Calendrier FR de selection d'une plage : 1er clic = debut, 2e = fin.

        Cliquer une date avant le debut deja choisi inverse les bornes. La plage
        complete s'applique et ferme aussitot (comme le calendrier simple). Le
        bouton « Effacer la période » remet le filtre a « toutes les dates ».
        """
        def parse(field: ft.TextField):
            iso, _ = _fr_to_iso(field.value)
            try:
                return date.fromisoformat(iso) if iso else None
            except ValueError:
                return None

        sel = {"start": parse(from_field), "end": parse(to_field)}
        today = date.today()
        cursor = sel["start"] or today
        state = {"year": cursor.year, "month": cursor.month}

        title = ft.Text(weight=ft.FontWeight.BOLD, size=16, color=NAVY)
        grid = ft.Column(spacing=4, tight=True)
        hint = ft.Text(size=12, color=MUTED)

        def hint_text() -> str:
            s, e = sel["start"], sel["end"]
            if s and e:
                return f"Période : {_iso_to_fr(s.isoformat())} → {_iso_to_fr(e.isoformat())}"
            if s:
                return f"Début : {_iso_to_fr(s.isoformat())} — cliquez la date de fin."
            return "Cliquez la date de début."

        def click(d: date) -> None:
            s, e = sel["start"], sel["end"]
            if s is None or (s and e):       # (re)commence une nouvelle plage
                sel["start"], sel["end"] = d, None
            elif d >= s:                      # fin posterieure : borne haute
                sel["end"] = d
            else:                             # fin anterieure : on inverse
                sel["start"], sel["end"] = d, s
            if sel["start"] and sel["end"]:   # plage complete -> applique + ferme
                self._apply_range(from_field, to_field, display,
                                  sel["start"], sel["end"], on_change)
                return
            hint.value = hint_text()
            render()
            self.page.update()

        def render() -> None:
            y, m = state["year"], state["month"]
            s, e = sel["start"], sel["end"]
            title.value = f"{_MOIS_FR[m - 1]} {y}"
            rows = [ft.Row(
                [ft.Container(
                    ft.Text(j, size=12, weight=ft.FontWeight.BOLD, color=MUTED,
                            text_align=ft.TextAlign.CENTER),
                    width=38, alignment=ft.Alignment.CENTER) for j in _JOURS_FR],
                spacing=2)]
            for week in calendar.Calendar(firstweekday=0).monthdayscalendar(y, m):
                cells = []
                for day in week:
                    if day == 0:
                        cells.append(ft.Container(width=38, height=38))
                        continue
                    d = date(y, m, day)
                    is_end = d == s or d == e
                    in_range = bool(s and e and s <= d <= e)
                    is_today = d == today and not (s or e)
                    cells.append(ft.Container(
                        ft.Text(str(day), text_align=ft.TextAlign.CENTER,
                                color=SURFACE if is_end else TEXT,
                                weight=ft.FontWeight.BOLD if (is_end or is_today) else None),
                        width=38, height=38, alignment=ft.Alignment.CENTER,
                        border_radius=19, ink=True,
                        bgcolor=(NAVY if is_end else
                                 (ft.Colors.with_opacity(0.30, TEAL) if in_range else
                                  (TEAL if is_today else None))),
                        on_click=lambda e, dd=d: click(dd),
                    ))
                rows.append(ft.Row(cells, spacing=2))
            grid.controls = rows

        def shift(delta: int) -> None:
            m = state["month"] - 1 + delta
            state["year"] += m // 12
            state["month"] = m % 12 + 1
            render()
            self.page.update()

        render()
        hint.value = hint_text()
        header = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=NAVY, on_click=lambda e: shift(-1)),
            ft.Container(title, expand=True, alignment=ft.Alignment.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=NAVY, on_click=lambda e: shift(1)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        dlg = ft.AlertDialog(
            content=ft.Container(
                ft.Column([header, grid, hint], tight=True, spacing=8), width=300),
            actions=[
                ft.TextButton("Effacer la période",
                              on_click=lambda e: self._apply_range(
                                  from_field, to_field, display, None, None, on_change)),
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
            ],
            bgcolor=SURFACE,
        )
        self._show_dialog(dlg)

    # --- Vue TABLEAU DE BORD --------------------------------------------------
    def show_dashboard(self) -> None:
        self.current_view = "dashboard"
        self.rail.selected_index = 0
        self._set_body(
            self._title("Tableau de bord"),
            ft.Row([ft.Container(self.dash_date_range, width=360)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.dash_results,
        )
        self._refresh_dashboard()

    def _kpi(self, label: str, value, icon, color=NAVY) -> ft.Control:
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color=color, size=20),
                        ft.Text(label, color=MUTED, size=12, expand=True)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(str(value), size=24, weight=ft.FontWeight.BOLD, color=TEXT),
            ], spacing=8),
            bgcolor=SURFACE, border_radius=12, padding=16,
            border=ft.Border.all(1, BORDER),
        )

    def _camembert(self, encaisse: float, encours: float) -> ft.Control:
        """Camembert « encaissé vs à recouvrer », dessiné via canvas (sans dépendance)."""
        total = encaisse + encours
        size = 170
        if total <= 0:
            shapes = [cv.Circle(size / 2, size / 2, size / 2,
                                paint=ft.Paint(color=BORDER, style=ft.PaintingStyle.FILL))]
        else:
            start = -math.pi / 2  # demarre en haut (12 h)
            sweep_enc = 2 * math.pi * (encaisse / total)
            shapes = [
                cv.Arc(0, 0, size, size, start, sweep_enc, use_center=True,
                       paint=ft.Paint(color=GREEN, style=ft.PaintingStyle.FILL)),
                cv.Arc(0, 0, size, size, start + sweep_enc, 2 * math.pi - sweep_enc,
                       use_center=True,
                       paint=ft.Paint(color=AMBER, style=ft.PaintingStyle.FILL)),
                # trou central -> effet « donut » plus lisible
                cv.Circle(size / 2, size / 2, size / 4,
                          paint=ft.Paint(color=SURFACE, style=ft.PaintingStyle.FILL)),
            ]
        chart = cv.Canvas(shapes, width=size, height=size)

        def legende(color, label, montant):
            pct = (montant / total * 100) if total > 0 else 0
            return ft.Row([
                ft.Container(width=12, height=12, bgcolor=color, border_radius=3),
                ft.Text(label, color=TEXT, size=13, expand=True),
                ft.Text(f"{montant:.2f}  ({pct:.0f} %)", color=MUTED, size=12),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

        details = ft.Column([
            legende(GREEN, "Encaissé", encaisse),
            legende(AMBER, "À recouvrer", encours),
        ], spacing=10)
        if total <= 0:
            details.controls.append(
                ft.Text("Aucun paiement sur la période.", color=MUTED, size=12))

        return ft.Row(
            [chart, ft.Container(details, expand=True,
                                 padding=ft.Padding.only(left=20))],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _balance_chart(self, entrees: float, sorties: float) -> ft.Control:
        """Donut « entrées encaissées vs sorties réglées » + solde net (sans dépendance)."""
        total = entrees + sorties
        size = 170
        if total <= 0:
            shapes = [cv.Circle(size / 2, size / 2, size / 2,
                                paint=ft.Paint(color=BORDER, style=ft.PaintingStyle.FILL))]
        else:
            start = -math.pi / 2
            sweep_in = 2 * math.pi * (entrees / total)
            shapes = [
                cv.Arc(0, 0, size, size, start, sweep_in, use_center=True,
                       paint=ft.Paint(color=GREEN, style=ft.PaintingStyle.FILL)),
                cv.Arc(0, 0, size, size, start + sweep_in, 2 * math.pi - sweep_in,
                       use_center=True,
                       paint=ft.Paint(color=AMBER, style=ft.PaintingStyle.FILL)),
                cv.Circle(size / 2, size / 2, size / 4,
                          paint=ft.Paint(color=SURFACE, style=ft.PaintingStyle.FILL)),
            ]
        chart = cv.Canvas(shapes, width=size, height=size)
        solde = entrees - sorties

        def legende(color, label, montant):
            pct = (montant / total * 100) if total > 0 else 0
            return ft.Row([
                ft.Container(width=12, height=12, bgcolor=color, border_radius=3),
                ft.Text(label, color=TEXT, size=13, expand=True),
                ft.Text(f"{montant:.2f}  ({pct:.0f} %)", color=MUTED, size=12),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

        details = ft.Column([
            ft.Text("Balance entrées / sorties", weight=ft.FontWeight.BOLD, color=TEXT, size=13),
            legende(GREEN, "Entrées (encaissé)", entrees),
            legende(AMBER, "Sorties (payé)", sorties),
            ft.Row([
                ft.Text("Solde net", color=TEXT, size=13, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(f"{solde:.2f}", color=GREEN if solde >= 0 else RED,
                        size=14, weight=ft.FontWeight.BOLD),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=10)
        if total <= 0:
            details.controls.append(ft.Text("Aucun flux sur la période.", color=MUTED, size=12))

        return ft.Row(
            [chart, ft.Container(details, expand=True, padding=ft.Padding.only(left=20))],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _refresh_dashboard(self) -> None:
        df = _date_iso(self.dash_date_from)
        dt = _date_iso(self.dash_date_to)

        # Tresorerie patient COMBINEE (notes + actes), cf. plans-de-traitement D7 :
        #  - encaisse = paiements encaisses + reglements d'actes (par date) ;
        #  - a recouvrer = paiements en attente + actes au reste positif.
        ca = repo.total_encaisse(self.conn, date_from=df, date_to=dt)
        encours = repo.total_creances(self.conn, date_from=df, date_to=dt)
        nb_enc = repo.count_paiements(self.conn, statut="encaisse", date_from=df, date_to=dt)

        nb_doc = repo.count_documents(self.conn, None, df, dt)
        nb_brouillon = repo.count_documents(self.conn, "brouillon", df, dt)
        nb_envoye = repo.count_documents(self.conn, "envoye", df, dt)

        nouveaux = repo.count_patients_new(self.conn, df, dt)
        total_pat = repo.count_patients(self.conn)
        impayes = repo.count_patients(self.conn, filtre="impayes")

        # Flux de tresorerie de la PERIODE, par date de transaction :
        #  - entrees = encaisse sur la periode (ca ci-dessus, par date_encaissement) ;
        #  - sorties = paye sur la periode (par date_reglement, reglements partiels inclus).
        sorties = repo.total_regle_periode(self.conn, df, dt)
        solde = ca - sorties
        # Stock "a ce jour" (independant du filtre de dates) : dette fournisseurs courante.
        # statut="tous" => inclut aussi les depenses partiellement reglees (reste > 0).
        _, _, reste_total = repo.total_depenses(self.conn, statut="tous")

        # Bandeau de KPI : 9 tuiles, 3 par ligne, occupant toute la largeur
        # (repli a 2 puis 1 par ligne sur fenetre etroite). Le `col` est pose
        # directement sur la tuile : ResponsiveRow l'etire a la largeur de colonne.
        def _kcol(tile):
            tile.col = {"xs": 6, "md": 4, "lg": 4}
            return tile

        kpis = ft.ResponsiveRow([_kcol(t) for t in [
            self._kpi("CA encaissé", f"{ca:.2f}", ft.Icons.PAYMENTS, GREEN),
            self._kpi("Encours à recouvrer", f"{encours:.2f}", ft.Icons.SCHEDULE, NAVY),
            self._kpi("Paiements encaissés", nb_enc, ft.Icons.RECEIPT_LONG, GREEN),
            self._kpi("Documents créés", nb_doc, ft.Icons.DESCRIPTION, NAVY),
            self._kpi("Brouillons en attente", nb_brouillon, ft.Icons.EDIT_NOTE, TEAL_DARK),
            self._kpi("Envoyés", nb_envoye, ft.Icons.MARK_EMAIL_READ, GREEN),
            self._kpi("Nouveaux (période)", nouveaux, ft.Icons.PERSON_ADD, NAVY),
            self._kpi("Total patients", total_pat, ft.Icons.PEOPLE, NAVY),
            self._kpi("Avec impayés", impayes, ft.Icons.WARNING_AMBER, AMBER),
            self._kpi("Dépenses payées (période)", f"{sorties:.2f}", ft.Icons.PRICE_CHECK, AMBER),
            self._kpi("Reste à payer (à ce jour)", f"{reste_total:.2f}",
                      ft.Icons.SCHEDULE_SEND, AMBER),
            self._kpi("Solde net (période)", f"{solde:.2f}", ft.Icons.ACCOUNT_BALANCE,
                      GREEN if solde >= 0 else RED),
        ]], spacing=12, run_spacing=12)

        camembert = self._card(self._camembert(ca, encours))
        balance = self._card(self._balance_chart(ca, sorties))

        by_type = repo.documents_by_type(self.conn, df, dt)
        if by_type:
            type_rows = [ft.Row([
                ft.Text(_humanize(t), color=TEXT, expand=True),
                ft.Text(str(n), color=NAVY, weight=ft.FontWeight.BOLD),
            ]) for t, n in by_type]
        else:
            type_rows = [ft.Text("Aucun document sur la période.", color=MUTED)]
        repartition = self._card(ft.Column(type_rows, spacing=8))

        audit = repo.list_audit(self.conn, limit=12, date_from=df, date_to=dt)
        if audit:
            # Detail desormais structure (JSON) : on le rend lisible via la meme
            # description que l'onglet Historique (tolerant aux anciennes lignes).
            audit_rows = []
            for ts, action, detail in audit:
                _cat, _icon, title, sublines = self._describe_audit(action, detail)
                audit_rows.append(ft.Row([
                    ft.Text(ts, size=12, color=MUTED, width=150),
                    ft.Text(title, color=TEXT, width=220),
                    ft.Text(" · ".join(sublines), size=12, color=MUTED, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER))
        else:
            audit_rows = [ft.Text("Aucune activité sur la période.", color=MUTED)]
        activite = self._card(ft.Column(audit_rows, spacing=6))

        # Grille responsive (sans titres de section, les cartes s'etirent pour
        # remplir la page) : bandeau KPI, puis camembert + repartition cote a
        # cote, puis l'activite recente en pleine largeur.
        def _col(control, small, large):
            control.col = {"xs": 12, "md": small, "lg": large}
            return control

        self.dash_results.content = ft.Column([
            kpis,
            ft.ResponsiveRow(
                [_col(camembert, 12, 6), _col(balance, 12, 6)],
                spacing=20, run_spacing=20),
            repartition,
            activite,
        ], spacing=20)
        self.page.update()

    # --- Vue PATIENTS ---------------------------------------------------------
    def show_patients(self) -> None:
        self.current_view = "patients"
        self.rail.selected_index = 1
        self._set_body(
            self._title(
                "Patients",
                self._btn("Nouveau patient", lambda e: self._patient_dialog(),
                          icon=ft.Icons.ADD, shortcut=SC_NEW, busy=False),
            ),
            ft.Row([self.search, self.patients_filter], spacing=12,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.patients_results,
            self.patients_pager,
        )
        self._refresh_patients()

    # --- Traitement par lot (page Documents) ----------------------------------
    def _doc_batch_action(self) -> tuple[str, str, str] | None:
        """Action de lot deduite du filtre de statut courant, ou None.

        Brouillon / Erreur generation -> generation ; En attente d'envoi /
        Erreur envoi -> envoi. Les autres filtres (tous / genere / envoye)
        n'exposent pas de traitement par lot.
        """
        s = self.doc_statut.value or "tous"
        if s in ("brouillon", "erreur"):
            return ("generation", "Générer les documents", ft.Icons.PLAY_ARROW)
        if s in ("en_attente_envoi", "erreur_envoi"):
            return ("envoi", "Envoyer les emails", ft.Icons.SEND)
        return None

    def _on_doc_statut_change(self) -> None:
        # Changer de statut change l'action de lot : on repart d'une selection vide.
        self.doc_selected.clear()
        self._reset_and("documents")

    def _doc_batch_count_label(self) -> str:
        return f"{len(self.doc_selected)} document(s) sélectionné(s)"

    def _doc_batch_bar_content(self, action: tuple[str, str, str]) -> ft.Control:
        """Carte « Traitement par lot » de la page Documents : Tout sélectionner +
        compteur + bouton d'action contextuel (Générer / Envoyer)."""
        kind, label, icon = action
        self.doc_select_all = ft.Checkbox(
            label="Tout sélectionner", value=False, on_change=self._on_doc_select_all)
        self.doc_batch_count_text = ft.Text(
            self._doc_batch_count_label(), size=12, color=MUTED)
        self.doc_launch_btn = self._btn(
            label, lambda e, k=kind, l=label: self._on_doc_launch(k, l),
            icon=icon, busy=False)
        self.doc_launch_btn.disabled = self._job_running or not self.doc_selected
        return self._card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.LAYERS, color=NAVY),
                    ft.Text("Traitement par lot", weight=ft.FontWeight.BOLD, color=TEXT)],
                   spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.doc_select_all, self.doc_batch_count_text,
                    ft.Container(expand=True), self.doc_launch_btn],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=12))

    def _update_doc_batch_bar(self) -> None:
        """Met a jour le compteur et l'etat du bouton sans reconstruire la liste."""
        if not hasattr(self, "doc_batch_count_text"):
            return
        self.doc_batch_count_text.value = self._doc_batch_count_label()
        self.doc_launch_btn.disabled = self._job_running or not self.doc_selected

    def _doc_toggle_select(self, document_id: int, value: bool) -> None:
        if value:
            self.doc_selected.add(document_id)
        else:
            self.doc_selected.discard(document_id)
        self._update_doc_batch_bar()
        self.page.update()

    def _on_doc_select_all(self, e: ft.ControlEvent) -> None:
        if e.control.value:
            ids = repo.list_document_ids_filtered(
                self.conn, self.doc_search.value or "",
                self.doc_statut.value or "tous",
                _date_iso(self.doc_date_from), _date_iso(self.doc_date_to))
            self.doc_selected = set(ids)
        else:
            self.doc_selected.clear()
        self._refresh_documents()

    def _on_doc_launch(self, kind: str, label: str) -> None:
        if self._job_running:
            self._toast("Un job est déjà en cours.", ok=False); return
        if not self.doc_selected:
            self._toast("Sélectionnez au moins un document.", ok=False); return
        ids = sorted(self.doc_selected)
        if kind == "envoi":
            self._doc_launch_envoi_dialog(ids)
        else:
            self._launch_job("generation", "documents", document_ids=ids)

    def _doc_launch_envoi_dialog(self, document_ids: list[int]) -> None:
        mtemplates = repo.list_mail_templates(self.conn)
        if not mtemplates:
            self._toast("Aucun modèle d'email. Ajoutez-en un dans l'onglet « Emails ».", ok=False)
            self.show_mail_templates()
            return
        default = repo.get_default_mail_template(self.conn)
        tpl_dd = ft.Dropdown(
            label="Modèle d'email",
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key=str(t.id), text=f"{t.name}  (#{t.mailjet_template_id})")
                     for t in mtemplates],
            value=str(default.id) if default else str(mtemplates[0].id),
        )
        by_id = {str(t.id): t for t in mtemplates}
        status = ft.Text("", color=RED, size=12)
        n = len(document_ids)

        def on_launch(e):
            chosen = by_id.get(tpl_dd.value)
            if not chosen:
                status.value = "Choisissez un modèle."; self.page.update(); return
            self._close_dialog()
            self._launch_job("envoi", "documents", document_ids=document_ids, params={
                "mailjet_template_id": chosen.mailjet_template_id,
                "mail_template_name": chosen.name,
            })

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Envoyer les emails par lot"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"{n} document(s) sélectionné(s).", color=MUTED, size=13),
                    tpl_dd, status,
                ], tight=True, spacing=12),
                width=420,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Lancer l'envoi", on_launch, icon=ft.Icons.SEND, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _launch_job(self, kind: str, doc_type: str, patient_ids: list[int] | None = None,
                    params: dict | None = None, document_ids: list[int] | None = None) -> None:
        """Crée un job et le déroule dans un thread d'arrière-plan (UI navigable).

        Deux modes : par patients (lot normal, `patient_ids`) ou par documents précis
        (`document_ids`, utilisé pour « Relancer les erreurs »).
        """
        if self._job_running:
            self._toast("Un job est déjà en cours.", ok=False)
            return
        params = params or {}
        statuts = _BATCH_STATUTS[kind]
        # En mode documents (le seul utilise par l'UI desormais), la periode ne
        # sert pas au filtrage : les ids de documents sont deja explicites.
        date_from = date_to = ""
        by_documents = document_ids is not None

        config = None
        mailjet_template_id = params.get("mailjet_template_id")
        if kind == "envoi":
            try:
                from src.config import load_config
                config = load_config()
            except Exception as exc:  # noqa: BLE001
                self._toast(f"config.ini invalide : {exc}", ok=False)
                return

        total = len(document_ids) if by_documents else len(patient_ids or [])
        job_params = json.dumps({
            "date_from": date_from, "date_to": date_to,
            "mode": "documents" if by_documents else "patients", **params,
        }, ensure_ascii=False)
        job = repo.create_job(self.conn, kind, doc_type, total, job_params)
        repo.log_audit(self.conn, f"job_{kind}",
                       f"job #{job.id} {doc_type} — {total} élément(s)")

        self._job_running = True
        self.doc_selected.clear()
        self.current_job_id = job.id
        self.show_job_detail(job.id)  # suivre la progression

        def run_one(jconn, d):
            """Exécute le rendu ou l'envoi d'un document. Lève en cas d'échec."""
            if kind == "generation":
                generator.render_document(jconn, d)
            else:
                generator.send_document(jconn, d, config, template_id=mailjet_template_id)

        def runner() -> None:
            # Connexion propre au thread : SQLite gere la concurrence entre
            # connexions (file lock + busy_timeout), contrairement au partage
            # d'une meme connexion entre threads.
            jconn = connect()
            try:
                if by_documents:
                    for did in document_ids:
                        # Chaque document est isole : une erreur n'arrete pas le job.
                        try:
                            d = repo.get_document(jconn, did)
                            if d is None:
                                repo.add_job_item(jconn, job.id, None, "skip",
                                                  document_id=did, message="Document introuvable.")
                            else:
                                try:
                                    run_one(jconn, d)
                                    repo.add_job_item(jconn, job.id, d.patient_id, "ok",
                                                      document_id=d.id)
                                except Exception as exc:  # noqa: BLE001
                                    repo.add_job_item(jconn, job.id, d.patient_id, "erreur",
                                                      document_id=d.id, message=str(exc))
                        except Exception as exc:  # noqa: BLE001
                            try:
                                repo.add_job_item(jconn, job.id, None, "erreur",
                                                  document_id=did, message=str(exc))
                            except Exception:  # noqa: BLE001
                                pass
                        self._on_job_progress(job.id, jconn)
                else:
                    for pid in (patient_ids or []):
                        # Chaque patient est isole : une erreur (rendu, envoi, ou meme
                        # acces DB) n'arrete jamais le job, elle est consignee comme
                        # ligne 'erreur' et le job continue (succes partiel en fin).
                        try:
                            docs = repo.list_documents_for_batch(
                                jconn, pid, doc_type, statuts, date_from, date_to)
                            if not docs:
                                repo.add_job_item(jconn, job.id, pid, "skip",
                                                  message="Aucun document à traiter.")
                            else:
                                errs: list[str] = []
                                last_id = None
                                for d in docs:
                                    last_id = d.id
                                    try:
                                        run_one(jconn, d)
                                    except Exception as exc:  # noqa: BLE001
                                        errs.append(str(exc))
                                if errs:
                                    repo.add_job_item(jconn, job.id, pid, "erreur",
                                                      document_id=last_id, message="; ".join(errs))
                                else:
                                    msg = f"{len(docs)} document(s)" if len(docs) > 1 else None
                                    repo.add_job_item(jconn, job.id, pid, "ok",
                                                      document_id=last_id, message=msg)
                        except Exception as exc:  # noqa: BLE001
                            try:
                                repo.add_job_item(jconn, job.id, pid, "erreur", message=str(exc))
                            except Exception:  # noqa: BLE001
                                pass
                        self._on_job_progress(job.id, jconn)
                # Statut final : partiel si au moins une erreur mais au moins un
                # succes ; erreur si tout a echoue ; termine sinon.
                final = repo.get_job(jconn, job.id)
                if final and final.errors:
                    statut = "termine_partiel" if final.ok else "erreur"
                else:
                    statut = "termine"
                repo.finish_job(jconn, job.id, statut)
            except Exception:  # noqa: BLE001
                # Filet de securite ultime (ex. connexion DB perdue) : ne pas laisser
                # le job bloque en 'en_cours'.
                try:
                    repo.finish_job(jconn, job.id, "erreur")
                except Exception:  # noqa: BLE001
                    pass
            finally:
                self._job_running = False
                # Rebuild complet de la vue (en-tete inclus) pour afficher l'etat
                # final : statut « Termine / Succes partiel / Erreur » et le bouton
                # « Relancer les erreurs ». Marshalle sur la boucle UI (cf.
                # _run_on_ui) et lit via self.conn — jconn est fermee juste apres
                # et liee a ce thread.
                def finalize() -> None:
                    if self.current_view == "job_detail" and self.current_job_id == job.id:
                        self.show_job_detail(job.id)
                    elif self.current_view == "jobs":
                        self._refresh_jobs()
                self._run_on_ui(finalize)
                jconn.close()

        threading.Thread(target=runner, daemon=True).start()

    def _run_on_ui(self, fn) -> None:
        """Exécute `fn` sur la boucle d'événements Flet (thread UI).

        Flet envoie les patches de contrôle de façon synchrone : appeler
        `page.update()` depuis un thread d'arrière-plan n'est pas transmis au
        client tant que la boucle ne tourne pas (d'où un suivi de job figé jusqu'à
        ce qu'on change de page). On marshalle donc le rafraîchissement sur la
        boucle, où le patch est réellement « flush ».
        """
        loop = getattr(self.page, "loop", None)
        if loop is None:  # hors contexte Flet (tests) : exécution directe.
            fn()
            return
        try:
            loop.call_soon_threadsafe(fn)
        except RuntimeError:
            pass  # boucle arrêtée (fermeture de l'app) : rien à rafraîchir.

    def _on_job_progress(self, job_id: int,
                         conn: sqlite3.Connection | None = None) -> None:
        """Rafraîchit la vue Travaux/détail depuis le thread du job.

        Le rafraîchissement est marshallé sur la boucle UI (cf. `_run_on_ui`) et
        lit via `self.conn` (connexion du thread UI) — `conn`, propre au thread du
        job, n'est pas utilisable hors de ce thread.
        """
        def refresh() -> None:
            try:
                if self.current_view == "jobs":
                    self._refresh_jobs()
                elif self.current_view == "job_detail" and self.current_job_id == job_id:
                    self._refresh_job_detail(job_id)
            except Exception:  # noqa: BLE001
                pass
        self._run_on_ui(refresh)

    def _refresh_patients(self) -> None:
        search = self.search.value or ""
        filtre = self.patients_filter.value or "tous"
        total = repo.count_patients(self.conn, search, filtre)
        self.patients_page = self._clamp_page(self.patients_page, total)
        patients = repo.list_patients(
            self.conn, search, filtre,
            limit=PAGE_SIZE, offset=self.patients_page * PAGE_SIZE,
        )
        rows = [self._patient_row(p) for p in patients]
        empty = ("Aucun patient ne correspond à votre recherche."
                 if (search.strip() or filtre != "tous")
                 else "Aucun patient. Cliquez sur « Nouveau patient ».")

        liste = ft.Column(rows, spacing=8) if rows else ft.Text(empty, color=MUTED)

        def on_page(idx):
            self.patients_page = idx
            self._refresh_patients()

        self.patients_results.content = self._card(liste)
        self.patients_pager.content = self._pagination(self.patients_page, total, on_page)
        self.page.update()

    def _patient_row(self, p: Patient) -> ft.Control:
        sub = " · ".join(filter(None, [p.email, p.telephone])) or "—"
        avatar = ft.CircleAvatar(
            content=ft.Text(_initials(p), color=NAVY, weight=ft.FontWeight.BOLD),
            bgcolor=TEAL, radius=18,
        )
        infos = ft.Column(
            [ft.Text(p.display, weight=ft.FontWeight.W_600, color=TEXT),
             ft.Text(sub, size=12, color=MUTED)],
            spacing=2, expand=True,
        )
        return ft.Container(
            content=ft.Row(
                [avatar, infos, ft.Text(f"#{p.id}", color=MUTED, size=12),
                 ft.Icon(ft.Icons.CHEVRON_RIGHT, color=MUTED)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=10, border_radius=10, ink=True,
            on_click=lambda e, pid=p.id: self.show_patient_detail(pid),
        )

    def show_patient_detail(self, patient_id: int,
                            conn: sqlite3.Connection | None = None) -> None:
        # `conn` : passe par l'auto-polling (thread) pour ne pas partager self.conn.
        conn = conn or self.conn
        p = repo.get_patient(conn, patient_id)
        if not p:
            return self.show_patients()
        # Ouverture d'un AUTRE patient : on repart a la 1re page de chaque section,
        # au 1er onglet et sans filtre d'historique.
        if not self.current_patient or self.current_patient.id != patient_id:
            self.detail_docs_page = 0
            self.detail_paie_page = 0
            self.detail_tab = 0
            self.detail_hist_filter = "tous"
        self.current_view = "patient_detail"  # Echap revient a la liste des patients
        self.current_patient = p

        # Pagination cote SQL (LIMIT/OFFSET) : la fiche reste rapide meme avec
        # un long historique de documents/paiements.
        docs_total = repo.count_documents_for_patient(conn, patient_id)
        enc_total = repo.count_encaissements_patient(conn, patient_id)
        self.detail_docs_page = self._clamp_page(self.detail_docs_page, docs_total)
        self.detail_paie_page = self._clamp_page(self.detail_paie_page, enc_total)
        docs = repo.list_documents(
            conn, patient_id, limit=PAGE_SIZE, offset=self.detail_docs_page * PAGE_SIZE)
        encs = repo.list_encaissements_patient(
            conn, patient_id, limit=PAGE_SIZE, offset=self.detail_paie_page * PAGE_SIZE)
        solde_du, solde_enc, solde_reste = repo.solde_patient(conn, patient_id)
        has_sent = repo.patient_has_sent_document(conn, patient_id)

        def on_docs_page(idx):
            self.detail_docs_page = idx
            self.show_patient_detail(patient_id)

        def on_paies_page(idx):
            self.detail_paie_page = idx
            self.show_patient_detail(patient_id)

        # Barre de pagination affichee seulement si l'historique depasse une page,
        # pour garder l'onglet epure quand il y a peu d'elements.
        docs_pager = (self._pagination(self.detail_docs_page, docs_total, on_docs_page)
                      if docs_total > PAGE_SIZE else ft.Container())
        regl_pager = (self._pagination(self.detail_paie_page, enc_total, on_paies_page)
                      if enc_total > PAGE_SIZE else ft.Container())

        # --- Colonne d'identite (figee a gauche) ------------------------------
        # Compacte : retour, nom, coordonnees (email/tel cliquables = copie),
        # naissance/adresse/notes, montants cles Du/Reste, et bouton Modifier.
        # STRETCH : les cartes (infos, montants) occupent 100% de la largeur de la
        # colonne d'identite. Le bouton retour est enveloppe dans une Row pour
        # rester a gauche a sa taille naturelle (sinon STRETCH l'etirerait aussi).
        identity = ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Retour à la liste",
                              icon_color=NAVY,
                              on_click=lambda e: self.show_patients()),
            ]),
            # Nom + bouton « Modifier » sur la meme ligne : le nom prend la place
            # disponible (expand), le bouton reste a sa taille naturelle a droite.
            ft.Row([
                ft.Text(p.display, size=20, weight=ft.FontWeight.BOLD, color=TEXT,
                        selectable=True, expand=True),
                self._btn("Modifier", lambda e: self._patient_dialog(p),
                          icon=ft.Icons.EDIT, primary=False, shortcut=SC_EDIT,
                          busy=False),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._card(ft.Column([
                self._id_field("Email", p.email, copyable=True),
                self._id_field("Téléphone", p.telephone, copyable=True),
                self._id_field("Date de naissance", _iso_to_fr(p.date_naissance)),
                self._id_field("Adresse", p.adresse),
                self._id_field("Notes", p.notes),
            ], spacing=10)),
            self._money_summary([
                ("Dû", solde_du, TEXT),
                ("Reste", solde_reste, AMBER),
            ]),
        ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        # --- Onglet « Plans & actes » -----------------------------------------
        plans_tab = ft.Column(self._plans_actes_section(p, conn),
                              spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

        # --- Onglet « Documents » ---------------------------------------------
        docs_title = [
            ft.Text("Documents", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Container(expand=True),
            self._btn("Note d'honoraires", lambda e: self._note_dialog(p),
                      icon=ft.Icons.RECEIPT_LONG, primary=False, busy=False),
            self._btn("Générer un document", lambda e: self._generate_dialog(p),
                      icon=ft.Icons.NOTE_ADD, primary=False, shortcut=SC_NEW, busy=False),
        ]
        if has_sent:
            docs_title.append(
                self._btn("Rafraîchir les statuts",
                          lambda e, pid=patient_id: self._refresh_patient_mail_statuses(e, pid),
                          icon=ft.Icons.REFRESH, primary=False, busy=False))
        docs_tab = ft.Column([
            # Row normale (PAS wrap=True) : l'espaceur `Container(expand=True)` de
            # docs_title est un enfant Flex, incompatible avec un Wrap Flutter
            # (wrap+expand => echec de rendu, onglet gris). Meme idiome que
            # l'en-tete « Plans & actes ».
            ft.Row(docs_title, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._card(self._grouped_docs_column(docs)),
            docs_pager,
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

        # --- Onglet « Règlements » --------------------------------------------
        regl_tab = ft.Column([
            self._money_summary([
                ("Dû", solde_du, TEXT),
                ("Encaissé", solde_enc, GREEN),
                ("Reste à recouvrer", solde_reste, AMBER),
            ]),
            self._card(ft.Column(
                [self._encaissement_row(en) for en in encs]
                or [ft.Text("Aucun règlement encaissé.", color=MUTED)],
                spacing=8)),
            regl_pager,
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

        # --- Onglet « Historique » --------------------------------------------
        hist_tab = self._historique_tab(patient_id, conn)

        # API Tabs (Flet récent) : un TabBar (en-têtes) + un TabBarView (contenus),
        # de même longueur, dans la `content` du Tabs. `selected_index`/`on_change`
        # pilotent l'onglet actif (mémorisé dans self.detail_tab).
        tab_defs = [
            ("Plans & actes", ft.Icons.MEDICAL_SERVICES, plans_tab),
            ("Documents", ft.Icons.DESCRIPTION, docs_tab),
            ("Règlements", ft.Icons.PAYMENTS, regl_tab),
            ("Historique", ft.Icons.HISTORY, hist_tab),
        ]

        def on_tab_change(e):
            try:
                self.detail_tab = int(e.data)
            except (TypeError, ValueError):
                self.detail_tab = e.control.selected_index

        tabs = ft.Tabs(
            length=len(tab_defs),
            selected_index=self.detail_tab,
            animation_duration=200,
            on_change=on_tab_change,
            expand=True,
            content=ft.Column([
                ft.TabBar(tabs=[ft.Tab(label=lbl, icon=ic)
                                for lbl, ic, _c in tab_defs]),
                ft.TabBarView(
                    controls=[ft.Container(c, padding=ft.Padding.only(top=12))
                              for _l, _i, c in tab_defs],
                    expand=True),
            ], expand=True, spacing=0),
        )

        # Mise en page : identite figee a gauche + onglets a droite. Sur fenetre
        # etroite (mode web notamment), l'identite repasse AU-DESSUS des onglets
        # (degradation gracieuse). On pilote la hauteur sans le scroll global de
        # _set_body : chaque onglet scrolle independamment, l'identite reste figee.
        narrow = bool(self.page.width and self.page.width < 860)
        if narrow:
            # Identite a hauteur naturelle au-dessus, onglets remplissant le reste.
            layout = ft.Column([identity, tabs], spacing=12, expand=True)
        else:
            # Identite figee a gauche (largeur fixe, scrollable si tres longue,
            # hauteur bornee par STRETCH), onglets a droite.
            layout = ft.Row(
                [ft.Container(
                    ft.Column([identity], scroll=ft.ScrollMode.AUTO), width=300),
                 ft.Container(tabs, expand=True)],
                spacing=18, expand=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.body.content = layout
        self.page.update()

    def _id_field(self, label: str, value: str | None,
                  copyable: bool = False) -> ft.Control:
        """Champ compact (libellé au-dessus de la valeur) de la colonne d'identité
        de la fiche patient. `copyable` rend la valeur cliquable (copie dans le
        presse-papiers), comme l'email/le téléphone."""
        lbl = ft.Text(label, size=11, color=MUTED)
        if not value:
            return ft.Column([lbl, ft.Text("—", color=MUTED)], spacing=1)
        if copyable:
            def _copy(e, v=value):
                self.page.run_task(self.page.clipboard.set, v)
                self._toast(f"« {v} » copié dans le presse-papiers.")
            val: ft.Control = ft.Container(
                content=ft.Row(
                    [ft.Text(value, color=TEXT, expand=True),
                     ft.Icon(ft.Icons.CONTENT_COPY, size=14, color=MUTED)],
                    spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=_copy, tooltip="Cliquer pour copier", ink=True,
                border_radius=6, padding=ft.Padding.symmetric(vertical=2, horizontal=4))
        else:
            val = ft.Text(value, color=TEXT, selectable=True)
        return ft.Column([lbl, val], spacing=1)

    def _historique_tab(self, patient_id: int,
                        conn: sqlite3.Connection) -> ft.Control:
        """Onglet « Historique » : flux antichronologique des événements de la
        fiche (journal d'audit par patient), groupé par jour, filtrable par
        catégorie, avec détail avant→après des mises à jour. Le filtre re-remplit
        la liste en mémoire sans recharger toute la fiche."""
        LIMIT = 200
        events = repo.list_audit_patient(conn, patient_id, limit=LIMIT)
        liste = ft.Column(
            self._historique_rows(events, self.detail_hist_filter, LIMIT),
            spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)

        def build_chips() -> list[ft.Control]:
            chips: list[ft.Control] = []
            for key, lbl in _AUDIT_FILTERS:
                active = self.detail_hist_filter == key
                chips.append(ft.Container(
                    ft.Text(lbl, size=12, color=SURFACE if active else NAVY),
                    bgcolor=NAVY if active else ft.Colors.with_opacity(0.08, NAVY),
                    padding=ft.Padding.symmetric(vertical=6, horizontal=12),
                    border_radius=20, ink=True,
                    on_click=lambda e, k=key: on_filter(k)))
            return chips

        def on_filter(key: str) -> None:
            self.detail_hist_filter = key
            chips_row.controls = build_chips()
            liste.controls = self._historique_rows(events, key, LIMIT)
            self.page.update()

        chips_row = ft.Row(build_chips(), wrap=True, spacing=8, run_spacing=8)
        return ft.Column([chips_row, liste], spacing=12, expand=True)

    def _historique_rows(self, events: list[tuple[str, str, str]],
                         filtre: str, limit: int) -> list[ft.Control]:
        """Lignes de l'onglet Historique : entrées (icône + heure + libellé +
        sous-lignes) groupées par jour, filtrées par catégorie."""
        rows: list[ft.Control] = []
        current_day = None
        shown = 0
        for ts, action, detail in events:
            cat, icon, title, sublines = self._describe_audit(action, detail)
            if filtre != "tous" and cat != filtre:
                continue
            shown += 1
            day = self._jour_label(ts)
            if day != current_day:
                current_day = day
                rows.append(ft.Container(
                    ft.Text(day, size=12, weight=ft.FontWeight.BOLD, color=MUTED),
                    padding=ft.Padding.only(top=8 if rows else 0, bottom=2)))
            entry: list[ft.Control] = [ft.Row([
                ft.Icon(icon, size=18, color=TEAL_DARK),
                ft.Text(self._heure_label(ts), size=12, color=MUTED, width=44),
                ft.Text(title, color=TEXT, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)]
            for sl in sublines:
                entry.append(ft.Row([
                    ft.Container(width=70),
                    ft.Text(sl, size=12, color=MUTED, expand=True),
                ], spacing=0))
            rows.append(ft.Container(ft.Column(entry, spacing=2),
                                     padding=ft.Padding.symmetric(vertical=2)))
        if not shown:
            return [ft.Text("Aucun historique.", color=MUTED)]
        if len(events) >= limit:
            rows.append(ft.Text(
                f"Affichage limité aux {limit} événements les plus récents.",
                size=11, color=MUTED, italic=True))
        return rows

    def _describe_audit(self, action: str, detail_raw: str):
        """(catégorie, icône, titre, sous-lignes) d'un événement du journal.
        Tolère un detail JSON (lignes récentes) ou texte libre/absent (anciennes
        lignes : titre humanisé + détail brut en sous-ligne)."""
        cat, icon, base = _AUDIT_META.get(
            action, ("autre", ft.Icons.CIRCLE, _humanize(action)))
        data = repo.parse_audit_detail(detail_raw)
        title = base
        sublines: list[str] = []
        if isinstance(data, dict):
            if action == "fiche_modifiee":
                for label, couple in (data.get("champs") or {}).items():
                    av = couple[0] if isinstance(couple, (list, tuple)) and couple else None
                    ap = (couple[1] if isinstance(couple, (list, tuple))
                          and len(couple) > 1 else None)
                    sublines.append(
                        f"{label} : {_audit_val(av)} → {_audit_val(ap)}")
            elif action in ("plan_cree", "plan_modifie", "plan_supprime"):
                if data.get("titre"):
                    title = f"{base} « {data['titre']} »"
                if data.get("actes"):
                    sublines.append(f"{data['actes']} acte(s)")
            elif action in ("acte_ajoute", "acte_modifie", "acte_supprime"):
                if data.get("libelle"):
                    title = f"{base} — {data['libelle']}"
                if data.get("dents"):
                    sublines.append(f"Dent(s) : {data['dents']}")
            elif action == "acte_regle":
                if data.get("libelle"):
                    title = f"{base} — {data['libelle']}"
                sub = _audit_montant(data.get("montant"))
                if data.get("mode"):
                    sub += f" · {_MODE_LABELS.get(data['mode'], data['mode'])}"
                sublines.append(sub)
            elif action == "reglement_cascade":
                sub = _audit_montant(data.get("montant"))
                if data.get("mode"):
                    sub += f" · {_MODE_LABELS.get(data['mode'], data['mode'])}"
                if data.get("lignes"):
                    sub += f" · {data['lignes']} créance(s)"
                sublines.append(sub)
            elif action in ("paiement_encaisse", "paiement_annule"):
                sub = _audit_montant(data.get("montant"))
                if data.get("mode"):
                    sub += f" · {_MODE_LABELS.get(data['mode'], data['mode'])}"
                if data.get("libelle"):
                    sub += f" · {data['libelle']}"
                sublines.append(sub)
            elif action in ("document_genere", "note_honoraires_generee",
                            "brouillon_cree", "brouillon_modifie"):
                modele = data.get("modele") or data.get("type")
                if modele:
                    title = f"{base} — {modele}"
            elif action == "document_envoye":
                if data.get("email"):
                    sublines.append(f"→ {data['email']}")
                elif data.get("type"):
                    title = f"{base} — {data['type']}"
            elif action in ("document_imprime", "brouillon_supprime"):
                t = data.get("type") or data.get("modele")
                if t:
                    title = f"{base} — {t}"
        elif isinstance(data, str) and data:
            sublines.append(data)  # ancienne ligne au detail texte libre
        return cat, icon, title, sublines

    def _jour_label(self, ts: str) -> str:
        """Libellé de jour pour le regroupement : « Aujourd'hui » / « Hier » / date."""
        try:
            d = date.fromisoformat(ts[:10])
        except ValueError:
            return ts[:10] or "—"
        delta = (date.today() - d).days
        if delta == 0:
            return "Aujourd'hui"
        if delta == 1:
            return "Hier"
        return _iso_to_fr(d.isoformat())

    def _heure_label(self, ts: str) -> str:
        """Heure HH:MM extraite d'un horodatage « AAAA-MM-JJ HH:MM:SS »."""
        return ts[11:16] if len(ts) >= 16 else ""

    def _grouped_docs_column(self, docs: list[Document]) -> ft.Control:
        """Documents de la fiche regroupes par catégorie en sections repliables.

        Sections `ExpansionTile` SANS bordure : `shape`/`collapsed_shape` fournis
        (side=None) neutralisent les liserés haut/bas que Flutter dessine par
        defaut. Le padding du titre et celui des lignes sont alignes (8 px) pour
        que l'icône dossier de catégorie et l'icône des documents partagent le même
        bord. Catégories connues d'abord, inconnues ensuite, « Sans catégorie » en
        dernier ; ordre récent-d'abord conservé. Une seule catégorie => liste à plat.
        """
        if not docs:
            return ft.Column([ft.Text("Aucun document.", color=MUTED)], spacing=8)
        order = [c.nom for c in repo.list_categories(self.conn)]
        groups: dict[str | None, list] = {}
        for d in docs:
            groups.setdefault(d.categorie or None, []).append(d)

        def sort_key(nom):
            if not nom:
                return (2, "")
            return (0, order.index(nom)) if nom in order else (1, nom.lower())

        if len(groups) == 1:
            only = next(iter(groups.values()))
            return ft.Column([self._doc_row(d) for d in only], spacing=8)
        no_border = ft.RoundedRectangleBorder(radius=8)
        sections: list[ft.Control] = []
        for nom in sorted(groups.keys(), key=sort_key):
            items = groups[nom]
            sections.append(ft.ExpansionTile(
                title=self._cat_pastille(nom, len(items)),
                controls=[ft.Container(
                    ft.Column([self._doc_row(d) for d in items], spacing=8),
                    padding=ft.Padding.only(left=8, right=8, bottom=8))],
                shape=no_border, collapsed_shape=no_border,
                tile_padding=ft.Padding.symmetric(horizontal=8),
                controls_padding=ft.Padding.all(0),
                expanded=True, maintain_state=True,
            ))
        return ft.Column(sections, spacing=6)

    def _doc_row(self, d: Document) -> ft.Control:
        label, color = _STATUT_LABELS.get(d.statut, (d.statut, MUTED))
        actions = []
        if d.statut in ("brouillon", "erreur"):
            tip = "Générer le document" if d.statut == "brouillon" else "Réessayer la génération"
            actions.append(ft.IconButton(
                ft.Icons.PLAY_CIRCLE_OUTLINE, tooltip=tip, icon_color=NAVY,
                on_click=lambda e, dd=d: self._render_draft(e, dd)))
            if d.statut == "brouillon":
                actions.append(ft.IconButton(
                    ft.Icons.EDIT, tooltip="Modifier le brouillon", icon_color=NAVY,
                    on_click=lambda e, dd=d: self._generate_dialog(self.current_patient, draft=dd)))
            actions.append(ft.IconButton(
                ft.Icons.DELETE_OUTLINE, tooltip="Supprimer", icon_color=RED,
                on_click=lambda e, dd=d: self._delete_draft_dialog(dd)))
        else:
            actions.append(ft.IconButton(
                ft.Icons.FOLDER_OPEN, tooltip="Ouvrir le fichier",
                on_click=lambda e, dd=d: self._open_file(dd)))
            actions.append(ft.IconButton(
                ft.Icons.PRINT, tooltip="Imprimer", icon_color=NAVY,
                on_click=lambda e, dd=d: self._print_file(e, dd)))
        if d.email and d.statut in ("en_attente_envoi", "erreur_envoi"):
            actions.append(ft.IconButton(ft.Icons.SEND, tooltip="Envoyer par email", icon_color=NAVY,
                                         on_click=lambda e, dd=d: self._send_dialog(dd)))
        if d.statut == "envoye":
            actions.append(ft.IconButton(
                ft.Icons.REFRESH, tooltip="Rafraîchir le statut Mailjet", icon_color=NAVY,
                on_click=lambda e, dd=d: self._refresh_mail_status(e, dd)))

        if d.statut == "envoye":
            sub = " · ".join(filter(None, [
                d.date_envoi or "",
                f"livraison : {d.mailjet_status}" if d.mailjet_status else "",
                f"ouvert {d.mailjet_opened_at}" if d.mailjet_opened_at else "",
                f"cliqué {d.mailjet_clicked_at}" if d.mailjet_clicked_at else "",
            ]))
        else:
            sub = d.date_generation or ""
        return ft.Row([
            ft.Icon(ft.Icons.PICTURE_AS_PDF if d.output_format == "pdf" else ft.Icons.IMAGE, color=TEAL_DARK),
            ft.Column([
                ft.Text(_doc_label(d), weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=2, expand=True),
            ft.Container(ft.Text(label, size=12, color=color),
                         bgcolor=ft.Colors.with_opacity(0.12, color), padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                         border_radius=20),
            *actions,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _render_draft(self, e: ft.ControlEvent, d: Document) -> None:
        """Génère immédiatement un brouillon (rendu Word→PDF) depuis la fiche patient."""
        def work():
            generator.render_document(self.conn, d)
            repo.log_audit(self.conn, "document_genere",
                           {"document_id": d.id, "type": d.type, "modele": d.template},
                           patient_id=d.patient_id)
            self._toast("Document généré.")
            self._after_doc_change()

        self._run_busy(e.control, None, work)

    def _delete_draft_dialog(self, d: Document) -> None:
        def on_delete(e):
            try:
                if d.file_path and Path(d.file_path).exists():
                    Path(d.file_path).unlink()
            except OSError:
                pass  # fichier verrouille/absent : on supprime quand meme l'enregistrement
            repo.delete_document(self.conn, d.id)
            repo.log_audit(self.conn, "brouillon_supprime",
                           {"document_id": d.id, "type": d.type},
                           patient_id=d.patient_id)
            self._close_dialog()
            self._toast("Brouillon supprimé.")
            if self.current_patient:
                self.show_patient_detail(self.current_patient.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer le brouillon"),
            content=ft.Text(f"Supprimer définitivement ce brouillon « {_doc_label(d)} » ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Supprimer", on_delete, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _refresh_mail_status(self, e: ft.ControlEvent, d: Document) -> None:
        """Interroge Mailjet pour le statut de livraison d'un document envoyé."""
        def work():
            from src.config import load_config
            config = load_config()
            status = generator.refresh_mail_status(self.conn, d, config)
            self._toast(f"Statut Mailjet : {status}")
            if self.current_patient:
                self.show_patient_detail(self.current_patient.id)

        self._run_busy(e.control, None, work)

    def _refresh_patient_mail_statuses(self, e: ft.ControlEvent, patient_id: int) -> None:
        """Rafraîchit (à la demande) le suivi Mailjet de tous les docs envoyés du patient."""
        def work():
            from src.config import load_config
            config = load_config()
            n = 0
            for d in repo.list_documents(self.conn, patient_id):
                if d.statut == "envoye" and d.mailjet_message_id:
                    try:
                        generator.refresh_mail_status(self.conn, d, config)
                        n += 1
                    except Exception:  # noqa: BLE001
                        pass
            self._toast(f"{n} statut(s) rafraîchi(s).")
            if self.current_patient:
                self.show_patient_detail(self.current_patient.id)

        self._run_busy(e.control, None, work)

    # --- Auto-polling du suivi Mailjet (ouvertures / clics) -------------------
    def _start_status_poller(self) -> None:
        """Thread de fond : rafraîchit périodiquement le suivi Mailjet des envois récents.

        Pas de vrai « push » possible (app locale sans serveur) : on interroge l'API
        toutes les `MAIL_POLL_SECONDS`. Le bouton « Rafraîchir » force une mise à jour.
        """
        def loop() -> None:
            while True:
                time.sleep(MAIL_POLL_SECONDS)
                try:
                    self._poll_mail_statuses()
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=loop, daemon=True).start()

    def _poll_mail_statuses(self) -> None:
        """Un cycle d'auto-polling : connexion propre au thread (jamais self.conn)."""
        try:
            from src.config import load_config
            config = load_config()
        except Exception:  # noqa: BLE001
            return  # config Mailjet absente/invalide : rien à faire
        pconn = connect()
        try:
            changed = False
            for d in repo.list_pollable_documents(pconn, limit=200):
                before = (d.mailjet_status, d.mailjet_opened_at, d.mailjet_clicked_at)
                try:
                    generator.refresh_mail_status(pconn, d, config)
                except Exception:  # noqa: BLE001
                    continue
                if (d.mailjet_status, d.mailjet_opened_at, d.mailjet_clicked_at) != before:
                    changed = True
            # Reflète les changements si l'utilisateur regarde justement la fiche.
            if changed and self.current_view == "patient_detail" and self.current_patient:
                self.show_patient_detail(self.current_patient.id, pconn)
        finally:
            pconn.close()

    def _paie_row(self, pa: Paiement) -> ft.Control:
        encaisse = pa.statut == "encaisse"
        chip_color = GREEN if encaisse else NAVY
        chip = ft.Container(
            ft.Text("Encaissé" if encaisse else "En attente", size=12, color=chip_color),
            bgcolor=ft.Colors.with_opacity(0.12, chip_color),
            padding=ft.Padding.symmetric(vertical=4, horizontal=10), border_radius=20,
        )
        right = []
        if not encaisse:
            right.append(ft.IconButton(ft.Icons.CHECK_CIRCLE, tooltip="Marquer encaissé",
                         icon_color=GREEN, on_click=lambda e, pp=pa: self._encaisser(pp)))
            right.append(ft.IconButton(ft.Icons.CANCEL, tooltip="Annuler le paiement",
                         icon_color=RED, on_click=lambda e, pp=pa: self._annuler_paiement(pp)))
        if encaisse:
            mode_txt = _MODE_LABELS.get(pa.mode, "mode non précisé")
            sub = f"Réglé par {mode_txt}"
            if pa.date_encaissement:
                sub += f" le {_iso_to_fr(pa.date_encaissement)}"
        else:
            sub = f"Échéance : {_iso_to_fr(pa.date_echeance) or '—'}"
        return ft.Row([
            ft.Text(f"{pa.montant:.2f}", weight=ft.FontWeight.W_600, color=TEXT),
            ft.Column([
                ft.Text(pa.notes or "Paiement", color=TEXT),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=2, expand=True),
            chip, *right,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _encaissement_row(self, en: "repo.Encaissement") -> ft.Control:
        """Ligne de l'historique UNIFIÉ des règlements : versement d'acte ou note
        encaissée, ce qui a réellement été encaissé (synchronisé avec les actes)."""
        is_acte = en.nature == "acte"
        icon = ft.Icons.MEDICAL_SERVICES if is_acte else ft.Icons.DESCRIPTION
        tag = "Acte" if is_acte else "Note"
        sub = f"{tag} · {_MODE_LABELS.get(en.mode, 'mode non précisé')}"
        if en.date:
            sub += f" · {_iso_to_fr(en.date)}"
        return ft.Row([
            ft.Text(f"{en.montant:.2f}", weight=ft.FontWeight.W_600, color=GREEN, width=90),
            ft.Icon(icon, size=16, color=TEAL_DARK),
            ft.Column([
                ft.Text(en.libelle, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=2, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # --- Plans de traitement & actes realises (fiche patient) -----------------
    def _dents_badges(self, dents: str | None) -> list[ft.Control]:
        """Petits badges turquoise « 26 » a partir d'une chaine « 26, 27 »."""
        out: list[ft.Control] = []
        for d in (dents or "").split(","):
            d = d.strip()
            if d:
                out.append(ft.Container(
                    ft.Text(d, size=11, color=TEAL_DARK),
                    bgcolor=ft.Colors.with_opacity(0.14, TEAL_DARK),
                    padding=ft.Padding.symmetric(vertical=2, horizontal=8),
                    border_radius=12))
        return out

    def _plans_actes_section(self, p: Patient,
                             conn: sqlite3.Connection) -> list[ft.Control]:
        """Section « Plans & actes » de la fiche patient : créances regroupées au
        même endroit — notes en attente, actes isolés, puis chaque plan en section
        repliable (3.1). Le bouton « Régler » (cascade globale) apparaît dès qu'une
        créance reste à recouvrer. Renvoie [titre, carte]."""
        plans = repo.list_plans(conn, p.id)
        isoles = repo.list_prestations(conn, p.id, plan_id=None)
        notes_attente = [pa for pa in repo.list_paiements(conn, p.id)
                         if pa.statut == "en_attente"]
        actes_a_regler = repo.list_prestations_a_regler(conn, p.id)
        actions = [
            ft.Container(expand=True),
            self._btn("Plan", lambda e: self._plan_dialog(p),
                      icon=ft.Icons.ADD_CHART, primary=False, busy=False),
            self._btn("Acte", lambda e: self._prestation_dialog(p),
                      icon=ft.Icons.ADD, primary=False, busy=False),
        ]
        if actes_a_regler:
            actions.append(self._btn(
                "Régler", lambda e: self._regler_dialog(p, back="fiche"),
                icon=ft.Icons.PAYMENTS, primary=False, busy=False))
        title = ft.Row(
            [ft.Text("Plans & actes", size=18, weight=ft.FontWeight.BOLD, color=TEXT)]
            + actions, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        body: list[ft.Control] = []
        if notes_attente:
            body.append(ft.Text("Notes en attente", size=12, color=MUTED))
            body.append(ft.Column([self._paie_row(pa) for pa in notes_attente],
                                   spacing=8))
        if isoles:
            body.append(ft.Text("Actes isolés", size=12, color=MUTED))
            body.append(ft.Column([self._prestation_row(x) for x in isoles], spacing=8))
        for plan in plans:
            body.append(self._plan_tile(p, plan, conn))
        if not body:
            body = [ft.Text("Aucun plan ni acte. Cliquez « Plan » ou « Acte ».",
                            color=MUTED)]
        return [title, self._card(ft.Column(body, spacing=12))]

    def _actions_menu(self, actions: list[tuple], tooltip: str = "Actions") -> ft.Control:
        """Regroupe les actions d'une ligne (acte / plan) dans un menu déroulant :
        un clic ouvre le menu, puis on choisit l'action. Allège les lignes en
        remplaçant les boutons d'action en ligne. `actions` est une liste de
        tuples `(icône, libellé, on_click, couleur)` ; l'ordre est conservé."""
        items = [
            ft.PopupMenuItem(
                content=ft.Row(
                    [ft.Icon(icon, color=color, size=18),
                     ft.Text(label, color=TEXT)],
                    spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=on_click)
            for icon, label, on_click, color in actions
        ]
        return ft.PopupMenuButton(
            items=items, icon=ft.Icons.MORE_VERT, icon_color=NAVY, tooltip=tooltip)

    def _plan_tile(self, p: Patient, plan: "repo.PlanTraitement",
                   conn: sqlite3.Connection) -> ft.Control:
        """Un plan en section repliable : titre + totaux derives + barre de
        progression d'ensemble + actions, et ses actes en corps (3.3)."""
        prests = repo.list_prestations(conn, p.id, plan_id=plan.id)
        du, enc, reste = repo.plan_totaux(conn, plan.id)
        v = (enc / du) if du > 0 else 0.0
        header = ft.Row([
            ft.Column([
                ft.Text(plan.titre, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text(f"dû {du:.2f} · encaissé {enc:.2f} · reste {reste:.2f}",
                        size=12, color=MUTED),
            ], spacing=2, expand=True),
            self._actions_menu([
                (ft.Icons.ADD, "Ajouter un acte",
                 lambda e, pl=plan: self._prestation_dialog(p, plan_id=pl.id), NAVY),
                (ft.Icons.EDIT, "Modifier le plan",
                 lambda e, pl=plan: self._plan_dialog(p, plan=pl), NAVY),
                (ft.Icons.DELETE_OUTLINE, "Supprimer le plan",
                 lambda e, pl=plan: self._supprimer_plan(p, pl), RED),
            ], tooltip="Actions du plan"),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        title = ft.Column([
            header,
            ft.ProgressBar(value=v, color=GREEN,
                           bgcolor=ft.Colors.with_opacity(0.15, NAVY)),
        ], spacing=6)
        inner = ([self._prestation_row(x, in_plan=True) for x in prests]
                 or [ft.Text("Aucun acte dans ce plan.", color=MUTED)])
        if plan.notes:
            inner.insert(0, ft.Text(plan.notes, size=12, color=MUTED, italic=True))
        no_border = ft.RoundedRectangleBorder(radius=8)
        return ft.ExpansionTile(
            title=title,
            controls=[ft.Container(
                ft.Column(inner, spacing=8),
                padding=ft.Padding.only(left=8, right=8, bottom=8))],
            shape=no_border, collapsed_shape=no_border,
            tile_padding=ft.Padding.symmetric(horizontal=8),
            controls_padding=ft.Padding.all(0),
            expanded=True, maintain_state=True,
        )

    def _prestation_row(self, pres: "repo.Prestation",
                        in_plan: bool = False) -> ft.Control:
        """Ligne d'un acte : montant, libelle, dents, date, note ; si facturable,
        barre de progression + reste + chip de statut + bouton Régler ; sinon badge
        « non facturable » (3.2)."""
        if pres.facturable:
            left = ft.Column([
                ft.Text(f"{pres.montant:.2f}", weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(f"réglé {pres.montant_regle:.2f} · reste {pres.reste:.2f}",
                        size=11, color=MUTED),
            ], spacing=2, width=150)
            label, color = _DEPENSE_STATUT_LABELS.get(pres.statut, (pres.statut, MUTED))
        else:
            left = ft.Column([
                ft.Text(f"{pres.montant:.2f}", weight=ft.FontWeight.W_600, color=MUTED),
                ft.Text("acte non facturé", size=11, color=MUTED),
            ], spacing=2, width=150)
            label, color = ("Non facturable", MUTED)
        chip = ft.Container(
            ft.Text(label, size=12, color=color),
            bgcolor=ft.Colors.with_opacity(0.12, color),
            padding=ft.Padding.symmetric(vertical=4, horizontal=10), border_radius=20)

        titre_row = ft.Row(
            [ft.Text(pres.libelle, weight=ft.FontWeight.W_600, color=TEXT)]
            + self._dents_badges(pres.dents),
            spacing=6, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        mid: list[ft.Control] = [titre_row]
        if pres.facturable:
            v = (pres.montant_regle / pres.montant) if pres.montant else 0.0
            mid.append(ft.ProgressBar(value=v, color=GREEN,
                                      bgcolor=ft.Colors.with_opacity(0.15, NAVY)))
        if pres.date_acte:
            mid.append(ft.Text(f"Date : {_iso_to_fr(pres.date_acte)}", size=12, color=MUTED))
        if pres.note:
            mid.append(ft.Text(pres.note, size=12, color=MUTED, italic=True))

        actions: list[tuple] = []
        if pres.facturable and pres.reste > 1e-9:
            actions.append((
                ft.Icons.PAYMENTS, "Régler cet acte",
                lambda e, pr=pres: self._payer_acte_dialog(pr.id, back="fiche"), GREEN))
        actions.append((
            ft.Icons.EDIT, "Modifier l'acte",
            lambda e, pr=pres: self._prestation_dialog(self.current_patient, pres=pr),
            NAVY))
        actions.append((
            ft.Icons.DELETE_OUTLINE, "Supprimer l'acte",
            lambda e, pr=pres: self._supprimer_prestation(pr), RED))
        return ft.Row([
            left,
            ft.Column(mid, spacing=4, expand=True),
            chip, self._actions_menu(actions, tooltip="Actions de l'acte"),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _odontogramme(self, *, is_selected, on_toggle,
                      denture: str = "adulte") -> types.SimpleNamespace:
        """Odontogramme cliquable (capability `selection-dents`).

        Grille de dents FDI en croix (maxillaire en haut, mandibulaire en bas ;
        côté DROIT du patient à gauche de l'écran — vue « face au patient »),
        avec bascule denture adulte (permanentes) / enfant (temporaires).
        Composant 100 % Flet : rendu et clics identiques en desktop et en web.

        Paramètres :
          is_selected(num) -> bool : la dent `num` est-elle retenue ?
          on_toggle(num)           : bascule la dent `num` (appelé au clic).
          denture                  : « adulte » | « enfant » affichée au départ.

        La SÉLECTION reste portée par l'appelant (source de vérité unique) ; ce
        composant n'en est qu'une vue. Renvoie un handle : `.control`,
        `.refresh()` (re-rend selon la sélection) et `.set_denture(d)`."""
        state = {"denture": denture if denture in ("adulte", "enfant") else "adulte"}
        grid = ft.Column([], tight=True, spacing=4)

        def _tooth(num: str) -> ft.Control:
            sel = is_selected(num)
            # Le numéro FDI reste TOUJOURS visible (sélectionnée ou non) ; la
            # sélection se distingue par le fond NAVY et le texte blanc.
            return ft.Container(
                ft.Text(num, size=11, text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.BOLD, color=SURFACE if sel else NAVY),
                width=30, height=30, alignment=ft.Alignment.CENTER,
                border_radius=6, ink=True,
                bgcolor=NAVY if sel else ft.Colors.with_opacity(0.08, NAVY),
                border=ft.Border.all(1, TEAL_DARK if sel else BORDER),
                tooltip=f"Dent {num}",
                on_click=lambda e, n=num: on_toggle(n))

        def _arcade(nums: list[str]) -> ft.Row:
            # Petit espace central marquant la ligne médiane entre les deux côtés.
            cells: list[ft.Control] = []
            half = len(nums) // 2
            for i, n in enumerate(nums):
                if i == half:
                    cells.append(ft.Container(width=10))
                cells.append(_tooth(n))
            return ft.Row(cells, spacing=2, tight=True,
                          alignment=ft.MainAxisAlignment.CENTER)

        def refresh(e=None):
            q = (repo.DENTS_TEMPORAIRES if state["denture"] == "enfant"
                 else repo.DENTS_PERMANENTES)
            qd = (5, 6, 7, 8) if state["denture"] == "enfant" else (1, 2, 3, 4)
            # Haut : quadrant droit (inversé, 8→1 vers la médiane) puis gauche ;
            # Bas : quadrant droit (inversé) puis gauche.
            top = list(reversed(q[qd[0]])) + list(q[qd[1]])
            bottom = list(reversed(q[qd[3]])) + list(q[qd[2]])
            grid.controls = [_arcade(top), _arcade(bottom)]
            self.page.update()

        btn_adulte = ft.TextButton("Adulte", on_click=lambda e: set_denture("adulte"))
        btn_enfant = ft.TextButton("Enfant", on_click=lambda e: set_denture("enfant"))

        def _render_switch():
            for b, key in ((btn_adulte, "adulte"), (btn_enfant, "enfant")):
                on = state["denture"] == key
                b.style = ft.ButtonStyle(
                    bgcolor=NAVY if on else ft.Colors.with_opacity(0.06, NAVY),
                    color=SURFACE if on else NAVY)

        def set_denture(d: str):
            if d in ("adulte", "enfant") and d != state["denture"]:
                state["denture"] = d
                _render_switch()
                refresh()

        _render_switch()
        refresh()
        control = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Text("Schéma dentaire", size=12, color=MUTED,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True), btn_adulte, btn_enfant,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                grid,
            ], tight=True, spacing=6),
            padding=8, border_radius=8, border=ft.Border.all(1, BORDER),
            bgcolor=ft.Colors.with_opacity(0.4, BG))
        return types.SimpleNamespace(
            control=control, refresh=refresh, set_denture=set_denture,
            denture=lambda: state["denture"])

    def _acte_card(self, *, pres: "repo.Prestation | None" = None,
                   actes: "list[repo.Acte] | None" = None,
                   on_change=None, on_remove=None,
                   date_naissance: "str | None" = None,
                   removable: bool = True) -> types.SimpleNamespace:
        """Composant reutilisable « carte acte » (3.4) : selecteur referentiel qui
        pre-remplit libelle+prix (modifiables), date, dents (chips) et note. Sert le
        dialogue d'acte isole ET le composer de plan (cartes empilees).

        Renvoie un handle (SimpleNamespace) : `.control` (UI), `.read()` (dict valide
        ou ValueError), `.montant()` (prix courant pour le total en direct),
        `.blank()` (carte neuve vide a ignorer), `.pres_id`."""
        if actes is None:
            actes = repo.list_actes(self.conn)
        state = {"acte_id": (pres.acte_id if pres else None)}

        libelle = ft.TextField(label="Libellé *",
                               value=(pres.libelle if pres else ""), expand=True)
        prix = ft.TextField(label="Prix", value=(f"{pres.montant:.2f}" if pres else "0"),
                            keyboard_type=ft.KeyboardType.NUMBER, width=130)

        def _changed(e=None):
            if on_change:
                on_change()
        prix.on_change = _changed
        libelle.on_change = lambda e: (state.__setitem__("acte_id", None))

        ref_dd = ft.Dropdown(
            label="Pré-remplir depuis le référentiel",
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key="", text="— Acte libre —")]
            + [ft.dropdown.Option(key=str(a.id), text=f"{a.libelle} · {_fmt_prix(a.prix)}")
               for a in actes],
            value="",
        )

        def on_ref(e):
            if not ref_dd.value:
                return
            a = next((x for x in actes if str(x.id) == ref_dd.value), None)
            if a:
                libelle.value = a.libelle
                prix.value = f"{a.prix:.2f}"
                state["acte_id"] = a.id
                self.page.update()
                _changed()
        ref_dd.on_select = on_ref

        date_row, date_field = self._date_field(
            "Date (réalisée ou prévue)", (pres.date_acte if pres else ""))
        note = ft.TextField(label="Note (optionnelle)", value=(pres.note if pres else ""),
                            multiline=True, min_lines=1, max_lines=3)

        # `dents_list` = SOURCE DE VÉRITÉ unique de la sélection ; le champ (ajout)
        # et l'odontogramme (affichage + sélection) en sont les deux vues. Pas de
        # chips dans le formulaire : la sélection est lue/modifiée sur le schéma.
        dents_list = [d for d in repo.normalize_dents(pres.dents if pres else "").split(", ")
                      if d]
        dent_input = ft.TextField(
            label="Dents (FDI)", expand=True,
            hint_text="dictez ou tapez plusieurs dents, puis Entrée pour les ajouter")

        # Odontogramme : denture par défaut dérivée de l'âge (adulte si naissance
        # inconnue) ; clic = toggle de la dent dans `dents_list`.
        odonto = self._odontogramme(
            is_selected=lambda n: n in dents_list,
            on_toggle=lambda n: toggle_dent(n),
            denture=repo.denture_par_defaut(date_naissance))

        def sync():
            """Re-rend l'odontogramme depuis `dents_list`."""
            odonto.refresh()

        def toggle_dent(num: str):
            if num in dents_list:
                dents_list.remove(num)
            else:
                dents_list.append(num)
            sync()

        def add_dents_from_input(e=None):
            """Ajoute en bloc toutes les dents saisies/dictées dans le champ.

            On dicte ou tape plusieurs numéros enchaînés (séparés par espace,
            virgule, point-virgule ou saut de ligne) puis Entrée les ajoute tous
            d'un coup et vide le champ. Déclenché aussi par le bouton « + » et la
            perte de focus (filet de sécurité), jamais au fil de la frappe."""
            raw = (dent_input.value or "").strip()
            if not raw:
                return
            tokens = [t for t in re.split(r"[,\s;]+", raw) if t]
            dent_input.value = ""
            added = False
            for t in tokens:
                if t not in dents_list:
                    dents_list.append(t)
                    added = True
            if added:
                sync()                # re-surligne les dents sur l'odontogramme
            else:
                self.page.update()    # vide le champ même si tout était doublon

        dent_input.on_blur = add_dents_from_input
        dent_input.on_submit = add_dents_from_input

        del_btn = (ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=RED,
                                 tooltip="Retirer cet acte",
                                 on_click=lambda e: on_remove(handle))
                   if (removable and on_remove) else ft.Container())
        control = self._card(ft.Column([
            ft.Row([ref_dd, del_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([libelle, prix], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            date_row,
            ft.Row([dent_input,
                    ft.IconButton(ft.Icons.ADD, icon_color=NAVY,
                                  tooltip="Ajouter les dents saisies",
                                  on_click=add_dents_from_input)],
                   spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            odonto.control,
            note,
        ], tight=True, spacing=8), padding=12)

        def read() -> dict:
            lib = (libelle.value or "").strip()
            if not lib:
                raise ValueError("Le libellé d'un acte est obligatoire.")
            try:
                m = float((prix.value or "0").replace(",", "."))
            except ValueError:
                raise ValueError(f"Prix invalide pour « {lib} ».")
            if m < 0:
                raise ValueError(f"Le prix de « {lib} » doit être positif ou nul.")
            di, ok = _fr_to_iso(date_field.value)
            if not ok:
                raise ValueError(f"Date invalide pour « {lib} » (JJ/MM/AAAA).")
            return {"acte_id": state["acte_id"], "libelle": lib, "montant": m,
                    "date_acte": di or None, "dents": ", ".join(dents_list),
                    "note": (note.value or "").strip() or None}

        def montant() -> float:
            try:
                return float((prix.value or "0").replace(",", "."))
            except ValueError:
                return 0.0

        handle = types.SimpleNamespace(
            control=control, read=read, montant=montant,
            blank=lambda: (pres is None and not (libelle.value or "").strip()),
            pres_id=(pres.id if pres else None))
        return handle

    def _plan_dialog(self, p: Patient, plan: "repo.PlanTraitement | None" = None) -> None:
        """Composer de plan (3.5) : titre + notes + pile de cartes d'actes, total dû
        en direct, un seul bouton « + Acte ». Sert création et édition."""
        is_edit = plan is not None
        actes = repo.list_actes(self.conn)
        titre = ft.TextField(label="Titre du plan *",
                             value=(plan.titre if plan else ""), autofocus=True)
        notes = ft.TextField(label="Notes (optionnelles)",
                             value=(plan.notes if plan else ""),
                             multiline=True, min_lines=1, max_lines=3)
        cards: list[types.SimpleNamespace] = []
        cards_col = ft.Column([], tight=True, spacing=10)
        total_txt = ft.Text("Total dû : 0.00", weight=ft.FontWeight.BOLD, color=TEXT)
        status = ft.Text("", color=RED, size=12)

        def recompute():
            tot = sum(c.montant() for c in cards)
            total_txt.value = f"Total dû : {tot:.2f}"
            self.page.update()

        def remove_card(h):
            if h in cards:
                cards.remove(h)
                cards_col.controls = [c.control for c in cards]
                recompute()

        def add_card(pres=None):
            h = self._acte_card(pres=pres, actes=actes,
                                on_change=recompute, on_remove=remove_card,
                                date_naissance=p.date_naissance)
            cards.append(h)
            cards_col.controls = [c.control for c in cards]
            recompute()

        if is_edit:
            for pres in repo.list_prestations(self.conn, p.id, plan_id=plan.id):
                add_card(pres)
        if not cards:
            add_card()

        def on_save(e=None):
            t = (titre.value or "").strip()
            if not t:
                status.value = "Le titre du plan est obligatoire."
                self.page.update(); return
            process = [c for c in cards if not c.blank()]
            if not process:
                status.value = "Ajoutez au moins un acte (libellé requis)."
                self.page.update(); return
            try:
                data = [c.read() for c in process]
            except ValueError as ex:
                status.value = str(ex); self.page.update(); return
            try:
                if is_edit:
                    existing = {x.id: x for x in repo.list_prestations(
                        self.conn, p.id, plan_id=plan.id)}
                    kept = {c.pres_id for c in process if c.pres_id}
                    removed = [pid for pid in existing if pid not in kept]
                    bloques = [existing[pid].libelle for pid in removed
                               if repo.prestation_has_reglements(self.conn, pid)]
                    if bloques:
                        status.value = ("Acte réglé non supprimable : "
                                        + ", ".join(bloques) + ". Soldez/annulez-le d'abord.")
                        self.page.update(); return
                    repo.update_plan(self.conn, plan.id, t, notes.value or None)
                    for c, d in zip(process, data):
                        if c.pres_id:
                            repo.update_prestation(
                                self.conn, c.pres_id, libelle=d["libelle"],
                                montant=d["montant"], plan_id=plan.id,
                                acte_id=d["acte_id"], date_acte=d["date_acte"],
                                dents=d["dents"], note=d["note"])
                        else:
                            repo.create_prestation(
                                self.conn, p.id, d["libelle"], d["montant"],
                                plan_id=plan.id, acte_id=d["acte_id"],
                                date_acte=d["date_acte"], dents=d["dents"], note=d["note"])
                    for pid in removed:
                        repo.delete_prestation(self.conn, pid)
                    repo.log_audit(self.conn, "plan_modifie",
                                   {"plan_id": plan.id, "titre": t,
                                    "actes": len(process)}, patient_id=p.id)
                else:
                    newplan = repo.create_plan(self.conn, p.id, t, notes.value or None)
                    for d in data:
                        repo.create_prestation(
                            self.conn, p.id, d["libelle"], d["montant"],
                            plan_id=newplan.id, acte_id=d["acte_id"],
                            date_acte=d["date_acte"], dents=d["dents"], note=d["note"])
                    repo.log_audit(self.conn, "plan_cree",
                                   {"plan_id": newplan.id, "titre": t,
                                    "actes": len(data)}, patient_id=p.id)
            except ValueError as ex:
                status.value = f"Échec : {ex}"; self.page.update(); return
            self._close_dialog()
            self._toast("Plan enregistré.")
            self.show_patient_detail(p.id)

        add_btn = self._btn("Ajouter un acte", lambda e: add_card(),
                            icon=ft.Icons.ADD, primary=False, busy=False)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier le plan" if is_edit else "Nouveau plan"),
            content=ft.Container(
                ft.Column([
                    titre, notes,
                    ft.Divider(height=1, color=BORDER),
                    ft.Row([ft.Text("Actes", weight=ft.FontWeight.BOLD, color=TEXT),
                            ft.Container(expand=True), total_txt],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    cards_col,
                    add_btn,
                    status,
                ], tight=True, spacing=12, scroll=ft.ScrollMode.AUTO),
                width=580, height=560),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, icon=ft.Icons.SAVE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _prestation_dialog(self, p: Patient, pres: "repo.Prestation | None" = None,
                           plan_id: int | None = None) -> None:
        """Dialogue d'un acte isolé ou rattaché (3.6) : une carte d'acte + sélecteur
        de plan (« aucun » par défaut)."""
        is_edit = pres is not None
        actes = repo.list_actes(self.conn)
        plans = repo.list_plans(self.conn, p.id)
        card = self._acte_card(pres=pres, actes=actes, removable=False,
                               date_naissance=p.date_naissance)
        init_plan = (str(pres.plan_id) if (pres and pres.plan_id)
                     else (str(plan_id) if plan_id else ""))
        plan_dd = ft.Dropdown(
            label="Plan (optionnel)", value=init_plan,
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key="", text="— Aucun (acte isolé) —")]
            + [ft.dropdown.Option(key=str(pl.id), text=pl.titre) for pl in plans],
        )
        status = ft.Text("", color=RED, size=12)

        def on_save(e=None):
            try:
                d = card.read()
            except ValueError as ex:
                status.value = str(ex); self.page.update(); return
            sel_plan = int(plan_dd.value) if plan_dd.value else None
            try:
                if is_edit:
                    repo.update_prestation(
                        self.conn, pres.id, libelle=d["libelle"], montant=d["montant"],
                        plan_id=sel_plan, acte_id=d["acte_id"], date_acte=d["date_acte"],
                        dents=d["dents"], note=d["note"])
                    repo.log_audit(self.conn, "acte_modifie",
                                   {"prestation_id": pres.id, "libelle": d["libelle"],
                                    "montant": d["montant"], "dents": d["dents"]},
                                   patient_id=p.id)
                else:
                    created = repo.create_prestation(
                        self.conn, p.id, d["libelle"], d["montant"],
                        plan_id=sel_plan, acte_id=d["acte_id"], date_acte=d["date_acte"],
                        dents=d["dents"], note=d["note"])
                    repo.log_audit(self.conn, "acte_ajoute",
                                   {"prestation_id": created.id, "libelle": d["libelle"],
                                    "montant": d["montant"], "dents": d["dents"]},
                                   patient_id=p.id)
            except ValueError as ex:
                status.value = f"Échec : {ex}"; self.page.update(); return
            self._close_dialog()
            self._toast("Acte enregistré.")
            self.show_patient_detail(p.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier l'acte" if is_edit else "Nouvel acte"),
            content=ft.Container(
                ft.Column([plan_dd, card.control, status],
                          tight=True, spacing=12, scroll=ft.ScrollMode.AUTO),
                width=580, height=540),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, icon=ft.Icons.SAVE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _supprimer_prestation(self, pres: "repo.Prestation") -> None:
        """Supprime un acte (3.8). Refus si des règlements existent (garde D8)."""
        if repo.prestation_has_reglements(self.conn, pres.id):
            self._toast("Acte réglé : soldez/annulez-le d'abord. Suppression impossible.",
                        ok=False)
            return

        def confirm(e):
            try:
                repo.delete_prestation(self.conn, pres.id)
            except ValueError as ex:
                self._close_dialog(); self._toast(str(ex), ok=False); return
            repo.log_audit(self.conn, "acte_supprime",
                           {"prestation_id": pres.id, "libelle": pres.libelle},
                           patient_id=pres.patient_id)
            self._close_dialog()
            self._toast("Acte supprimé.")
            self.show_patient_detail(pres.patient_id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer l'acte"),
            content=ft.Text(f"Supprimer définitivement l'acte « {pres.libelle} » "
                            f"({pres.montant:.2f}) ?"),
            actions=[
                ft.TextButton("Retour", on_click=lambda e: self._close_dialog()),
                self._btn("Supprimer", confirm, icon=ft.Icons.DELETE_OUTLINE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _supprimer_plan(self, p: Patient, plan: "repo.PlanTraitement") -> None:
        """Supprime un plan (3.8). Ses actes sont DÉTACHÉS (deviennent isolés) ;
        aucun règlement n'est perdu (garde D8)."""
        n = len(repo.list_prestations(self.conn, p.id, plan_id=plan.id))

        def confirm(e):
            repo.delete_plan(self.conn, plan.id)
            repo.log_audit(self.conn, "plan_supprime",
                           {"plan_id": plan.id, "titre": plan.titre}, patient_id=p.id)
            self._close_dialog()
            self._toast("Plan supprimé (actes conservés en isolés).")
            self.show_patient_detail(p.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer le plan"),
            content=ft.Text(
                f"Supprimer le plan « {plan.titre} » ? "
                f"Ses {n} acte(s) deviennent des actes isolés du patient "
                "(aucun règlement n'est perdu)."),
            actions=[
                ft.TextButton("Retour", on_click=lambda e: self._close_dialog()),
                self._btn("Supprimer le plan", confirm,
                          icon=ft.Icons.DELETE_OUTLINE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _regler_dialog(self, p: Patient, back: str = "fiche") -> None:
        """Règlement GLOBAL en cascade (D9 révisé) : on saisit UN montant reçu, qui
        est réparti automatiquement sur les ACTES non soldés du patient, du plus
        ancien au plus récent, en PAIEMENT PARTIEL (le dernier acte atteint reste
        partiel). Un aperçu se met à jour en direct.

        Les notes d'honoraires sont binaires (pas de paiement partiel possible) : on
        les EXCLUT de la cascade pour ne jamais bloquer un reliquat — elles se règlent
        séparément via leur bouton « Encaisser » dans « Notes en attente »."""
        creances = repo.creances_patient(self.conn, p.id, include_notes=False)
        if not creances:
            self._toast("Aucun acte à régler.", ok=False)
            return
        total_reste = sum(c.reste for c in creances)
        montant = ft.TextField(label="Montant reçu", value=f"{total_reste:.2f}",
                               keyboard_type=ft.KeyboardType.NUMBER, autofocus=True)
        mode = ft.RadioGroup(
            value="especes",
            content=ft.Column(
                [ft.Radio(value=k, label=val) for k, val in _MODE_LABELS.items()],
                tight=True, spacing=2))
        date_row, date_field = self._date_field(
            "Date du règlement", date.today().isoformat())
        warn = ft.Text("", color=AMBER, size=12)
        preview = ft.Column([], tight=True, spacing=4)
        reste_txt = ft.Text("", weight=ft.FontWeight.BOLD)

        def compute():
            try:
                amt = float((montant.value or "0").replace(",", "."))
            except ValueError:
                amt = 0.0
            remaining = max(0.0, amt)
            rows: list[ft.Control] = []
            for c in creances:
                if c.nature == "acte":
                    pay = min(remaining, c.reste)
                else:  # note binaire : soldée seulement si le reliquat la couvre
                    pay = c.reste if c.reste <= remaining + 1e-9 else 0.0
                remaining -= pay
                solde = pay >= c.reste - 1e-9 and pay > 0
                tag = ("soldé" if solde else (f"+{pay:.2f}" if pay > 0 else "—"))
                tcolor = GREEN if solde else (AMBER if pay > 0 else MUTED)
                rows.append(ft.Row([
                    ft.Icon(ft.Icons.MEDICAL_SERVICES if c.nature == "acte"
                            else ft.Icons.DESCRIPTION, size=14, color=MUTED),
                    ft.Text(c.libelle, color=TEXT, expand=True),
                    ft.Text(f"reste {c.reste:.2f}", size=12, color=MUTED, width=110),
                    ft.Text(tag, size=12, color=tcolor, width=80,
                            text_align=ft.TextAlign.RIGHT),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER))
            preview.controls = rows
            # Reste à payer APRÈS le règlement = total à recouvrer − part réellement allouée.
            alloue = max(0.0, amt) - remaining
            reste_apres = max(0.0, total_reste - alloue)
            reste_txt.value = f"Reste à payer après règlement : {reste_apres:.2f}"
            reste_txt.color = GREEN if reste_apres <= 1e-9 else AMBER
            warn.value = (f"{remaining:.2f} non affecté (montant supérieur aux créances)."
                          if remaining > 1e-9 else "")
            warn.color = AMBER
            self.page.update()

        montant.on_change = lambda e: compute()
        compute()

        def confirm(e):
            try:
                amt = float((montant.value or "0").replace(",", "."))
            except ValueError:
                warn.value = "Montant invalide."; warn.color = RED
                self.page.update(); return
            if amt <= 0:
                warn.value = "Le montant doit être strictement supérieur à 0."
                warn.color = RED; self.page.update(); return
            if not mode.value:
                warn.value = "Sélectionnez un mode."; warn.color = RED
                self.page.update(); return
            di, ok = _fr_to_iso(date_field.value)
            if not ok:
                warn.value = "Date invalide (JJ/MM/AAAA)."; warn.color = RED
                self.page.update(); return
            res = repo.regler_creances(
                self.conn, p.id, amt, mode=mode.value, date_reglement=di or None,
                include_notes=False)
            repo.log_audit(
                self.conn, "reglement_cascade",
                {"montant": res['alloue'], "mode": mode.value,
                 "lignes": len(res['lignes']), "reste": res['reste']},
                patient_id=p.id)
            self._close_dialog()
            msg = f"{res['alloue']:.2f} réparti sur {len(res['lignes'])} créance(s)."
            if res['reste'] > 1e-9:
                msg += f" {res['reste']:.2f} non affecté."
            self._toast(msg)
            if back == "paiements":
                self.show_paiements()
            else:
                self.show_patient_detail(p.id)

        montant.on_submit = confirm
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Régler — {p.display}"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"Total à recouvrer : {total_reste:.2f}",
                            weight=ft.FontWeight.BOLD, color=AMBER),
                    montant,
                    ft.Text("Mode de règlement", weight=ft.FontWeight.BOLD,
                            color=TEXT, size=12),
                    mode, date_row,
                    ft.Divider(height=1, color=BORDER),
                    ft.Text("Répartition (du plus ancien au plus récent)",
                            size=12, color=MUTED),
                    preview,
                    ft.Divider(height=1, color=BORDER),
                    reste_txt, warn,
                ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=480, height=540),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Régler", confirm, icon=ft.Icons.PAYMENTS, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _payer_acte_dialog(self, prestation_id: int, back: str = "fiche") -> None:
        """Versement sur UN acte précis (partiel ou solde) — action par ligne et
        depuis l'écran Finances. Garde « versement > reste »."""
        pres = repo.get_prestation(self.conn, prestation_id)
        if pres is None or not pres.facturable:
            self._toast("Acte introuvable ou non facturable.", ok=False)
            return
        versement = ft.TextField(
            label="Montant versé", value=f"{pres.reste:.2f}",
            keyboard_type=ft.KeyboardType.NUMBER, autofocus=True)
        mode = ft.RadioGroup(
            value="especes",
            content=ft.Column(
                [ft.Radio(value=k, label=val) for k, val in _MODE_LABELS.items()],
                tight=True, spacing=2))
        date_row, date_field = self._date_field(
            "Date du règlement", date.today().isoformat())
        warn = ft.Text("", color=RED, size=12)

        def confirm(e):
            try:
                val = float((versement.value or "0").replace(",", "."))
            except ValueError:
                warn.value = "Montant invalide."; self.page.update(); return
            if val <= 0:
                warn.value = "Le versement doit être strictement supérieur à 0."
                self.page.update(); return
            if val > pres.reste + 1e-9:
                warn.value = f"Le versement dépasse le reste ({pres.reste:.2f})."
                self.page.update(); return
            if not mode.value:
                warn.value = "Sélectionnez un mode."; self.page.update(); return
            di, ok = _fr_to_iso(date_field.value)
            if not ok:
                warn.value = "Date invalide (JJ/MM/AAAA)."; self.page.update(); return
            new = repo.add_prestation_reglement(
                self.conn, pres.id, val, mode=mode.value, date_reglement=di or None)
            repo.log_audit(
                self.conn, "acte_regle",
                {"prestation_id": pres.id, "libelle": pres.libelle, "montant": val,
                 "mode": mode.value, "statut": new.statut},
                patient_id=pres.patient_id)
            self._close_dialog()
            self._toast("Acte soldé." if new.statut == "regle"
                        else "Règlement enregistré.")
            if back == "paiements":
                self.show_paiements()
            elif self.current_patient:
                self.show_patient_detail(self.current_patient.id)
        versement.on_submit = confirm

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Régler — {pres.libelle}"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"Total dû : {pres.montant:.2f}", color=MUTED),
                    ft.Text(f"Déjà réglé : {pres.montant_regle:.2f}", color=MUTED),
                    ft.Text(f"Reste à payer : {pres.reste:.2f}",
                            weight=ft.FontWeight.BOLD, color=AMBER),
                    versement,
                    ft.Text("Mode de règlement", weight=ft.FontWeight.BOLD, color=TEXT),
                    mode, date_row, warn,
                ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=360, height=440),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Régler", confirm, icon=ft.Icons.CHECK_CIRCLE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Vue FINANCES (Paiements + Depenses) ----------------------------------
    def show_finances(self, tab: str | None = None) -> None:
        """Page Finances a deux sous-vues : Paiements (entrees) et Depenses (sorties).

        `current_view` conserve la cle de la sous-vue active ("paiements"/"depenses")
        afin que Recherche / Pagination restent contextuelles.
        """
        self.finances_tab = tab or self.finances_tab
        self.rail.selected_index = 3
        if self.finances_tab == "depenses":
            self.show_depenses()
        else:
            self.show_paiements()

    def _finances_submenu(self) -> ft.Control:
        """Sous-menu a deux onglets de la page Finances (calque _param_submenu)."""
        def tab_btn(key: str, label: str, icon) -> ft.Control:
            active = self.finances_tab == key
            return ft.Container(
                ft.Row([ft.Icon(icon, size=18, color=SURFACE if active else NAVY),
                        ft.Text(label, color=SURFACE if active else NAVY,
                                weight=ft.FontWeight.BOLD, size=13)],
                       spacing=8, tight=True),
                bgcolor=NAVY if active else ft.Colors.with_opacity(0.10, NAVY),
                padding=ft.Padding.symmetric(vertical=9, horizontal=16),
                border_radius=10, ink=True,
                on_click=lambda e, k=key: self.show_finances(k),
            )
        return ft.Row([
            tab_btn("paiements", "Paiements", ft.Icons.PAYMENTS),
            tab_btn("depenses", "Dépenses", ft.Icons.SHOPPING_CART_CHECKOUT),
        ], spacing=10)

    def show_paiements(self) -> None:
        self.finances_tab = "paiements"
        self.current_view = "paiements"
        self.rail.selected_index = 3
        self._set_body(
            self._title("Finances"),
            self._finances_submenu(),
            ft.Row([self.paie_search, self.paie_statut,
                    ft.Container(self.paie_date_range, width=360)],
                   spacing=12,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.paie_summary,
            self.paie_results,
            self.paie_pager,
        )
        self._refresh_paiements()

    def _paie_finance_row(self, pa: Paiement, pt: Patient) -> ft.Control:
        """Ligne « paiement » de l'écran Finances (note d'honoraires)."""
        encaisse = pa.statut == "encaisse"
        chip_color = GREEN if encaisse else NAVY
        chip = ft.Container(
            ft.Text("Encaissé" if encaisse else "En attente", size=12, color=chip_color),
            bgcolor=ft.Colors.with_opacity(0.12, chip_color),
            padding=ft.Padding.symmetric(vertical=4, horizontal=10), border_radius=20,
        )
        actions = [
            ft.TextButton("Ouvrir la fiche",
                          on_click=lambda e, pid=pt.id: self.show_patient_detail(pid)),
        ]
        if not encaisse:
            actions.append(ft.IconButton(
                ft.Icons.CHECK_CIRCLE, tooltip="Marquer encaissé", icon_color=GREEN,
                on_click=lambda e, pp=pa: self._encaisser(pp, back_to_paiements=True)))
            actions.append(ft.IconButton(
                ft.Icons.CANCEL, tooltip="Annuler le paiement", icon_color=RED,
                on_click=lambda e, pp=pa: self._annuler_paiement(pp, back_to_paiements=True)))
        if encaisse:
            date_info = f"Encaissé le {_iso_to_fr(pa.date_encaissement) or '—'}"
            date_info += f" · {_MODE_LABELS.get(pa.mode, 'mode non précisé')}"
        else:
            date_info = f"Échéance : {_iso_to_fr(pa.date_echeance) or '—'}"
        return ft.Row([
            ft.Text(f"{pa.montant:.2f}", weight=ft.FontWeight.W_600, color=TEXT, width=90),
            ft.Column([
                ft.Text(pt.display, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(date_info, size=12, color=MUTED),
            ], spacing=2, expand=True),
            chip, *actions,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _creance_row(self, c: "repo.Creance") -> ft.Control:
        """Ligne unifiée « à recouvrer » : note (encaisser) ou acte (régler), selon
        sa nature, avec le reste à recouvrer en tête (D7 / 4.2)."""
        if c.nature == "acte":
            chip_color = AMBER if c.statut == "regle_partiellement" else NAVY
            chip_label = ("Acte · réglé part." if c.statut == "regle_partiellement"
                          else "Acte")
            sub = c.libelle + (f" · {_iso_to_fr(c.date)}" if c.date else "")
            action = ft.IconButton(
                ft.Icons.PAYMENTS, tooltip="Régler l'acte", icon_color=GREEN,
                on_click=lambda e, sid=c.source_id: self._payer_acte_dialog(
                    sid, back="paiements"))
        else:
            chip_color, chip_label = NAVY, "Note"
            sub = c.libelle + (f" · échéance {_iso_to_fr(c.date)}" if c.date else "")
            pa = Paiement(id=c.source_id, patient_id=c.patient.id, montant=c.montant,
                          statut="en_attente", notes=c.libelle)
            action = ft.IconButton(
                ft.Icons.CHECK_CIRCLE, tooltip="Encaisser", icon_color=GREEN,
                on_click=lambda e, pp=pa: self._encaisser(pp, back_to_paiements=True))
        chip = ft.Container(
            ft.Text(chip_label, size=12, color=chip_color),
            bgcolor=ft.Colors.with_opacity(0.12, chip_color),
            padding=ft.Padding.symmetric(vertical=4, horizontal=10), border_radius=20)
        return ft.Row([
            ft.Text(f"{c.reste:.2f}", weight=ft.FontWeight.W_600, color=TEXT, width=90),
            ft.Column([
                ft.Text(c.patient.display, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=2, expand=True),
            chip,
            ft.TextButton("Ouvrir la fiche",
                          on_click=lambda e, pid=c.patient.id: self.show_patient_detail(pid)),
            action,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _refresh_paiements(self) -> None:
        search = self.paie_search.value or ""
        statut = self.paie_statut.value or "en_attente"
        date_from = _date_iso(self.paie_date_from)
        date_to = _date_iso(self.paie_date_to)

        if statut == "en_attente":
            # Vue UNIFIEE des creances (D7) : notes en attente + actes au reste positif.
            count = repo.count_creances(self.conn, search, date_from, date_to)
            somme = repo.total_creances(self.conn, search, date_from, date_to)
            self.paie_page = self._clamp_page(self.paie_page, count)
            items = repo.list_creances(
                self.conn, search, date_from, date_to,
                limit=PAGE_SIZE, offset=self.paie_page * PAGE_SIZE)
            rows = [self._creance_row(c) for c in items]
            total_label = "Total à recouvrer (notes + actes)"
            empty = ("Aucune créance ne correspond à votre recherche."
                     if search.strip() else
                     "Aucune créance sur la période sélectionnée."
                     if (date_from.strip() or date_to.strip()) else
                     "Aucune créance à recouvrer.")
        else:
            count = repo.count_paiements(self.conn, search, statut, date_from, date_to)
            if statut == "encaisse":
                # Total tresorerie : paiements encaisses + reglements d'actes (D7 / 4.3).
                somme = repo.total_encaisse(self.conn, date_from, date_to)
                total_label = "Total encaissé (paiements + actes)"
            else:
                somme = repo.total_paiements(self.conn, search, statut, date_from, date_to)
                total_label = "Total (tous statuts)"
            self.paie_page = self._clamp_page(self.paie_page, count)
            items = repo.list_paiements_filtered(
                self.conn, search, statut,
                limit=PAGE_SIZE, offset=self.paie_page * PAGE_SIZE,
                date_from=date_from, date_to=date_to,
            )
            rows = [self._paie_finance_row(pa, pt) for pa, pt in items]
            empty = ("Aucun paiement ne correspond à votre recherche."
                     if search.strip() else
                     "Aucun paiement sur la période sélectionnée."
                     if (date_from.strip() or date_to.strip()) else
                     "Aucun paiement.")

        liste = ft.Column(rows, spacing=8) if rows else ft.Text(empty, color=MUTED)

        def on_page(idx):
            self.paie_page = idx
            self._refresh_paiements()

        self.paie_summary.content = self._card(ft.Row([
            ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color=NAVY),
            ft.Text(total_label, color=MUTED),
            ft.Container(expand=True),
            ft.Text(f"{somme:.2f}", size=22, weight=ft.FontWeight.BOLD, color=NAVY),
        ]))
        self.paie_results.content = self._card(liste)
        self.paie_pager.content = self._pagination(self.paie_page, count, on_page)
        self.page.update()

    # --- Sous-vue DEPENSES (Finances) -----------------------------------------
    def show_depenses(self) -> None:
        self.finances_tab = "depenses"
        self.current_view = "depenses"
        self.rail.selected_index = 3
        action = self._btn("Nouvelle dépense", lambda e: self._depense_dialog(),
                           icon=ft.Icons.ADD, shortcut=SC_NEW, busy=False)
        self._set_body(
            self._title("Finances", action),
            self._finances_submenu(),
            ft.Row([self.dep_search, self.dep_statut,
                    ft.Container(self.dep_date_range, width=360)],
                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.dep_summary,
            self.dep_results,
            self.dep_pager,
        )
        self._refresh_depenses()

    def _refresh_depenses(self) -> None:
        search = self.dep_search.value or ""
        statut = self.dep_statut.value or "tous"
        date_from = _date_iso(self.dep_date_from)
        date_to = _date_iso(self.dep_date_to)
        count = repo.count_depenses(self.conn, search, statut, date_from, date_to)
        du, regle, reste = repo.total_depenses(self.conn, search, statut, date_from, date_to)
        self.dep_page = self._clamp_page(self.dep_page, count)
        items = repo.list_depenses_filtered(
            self.conn, search, statut,
            limit=PAGE_SIZE, offset=self.dep_page * PAGE_SIZE,
            date_from=date_from, date_to=date_to,
        )
        rows = [self._depense_list_row(dep, pr) for dep, pr in items]
        if rows:
            liste = ft.Column(rows, spacing=8)
        elif search.strip():
            liste = ft.Text("Aucune dépense ne correspond à votre recherche.", color=MUTED)
        elif date_from.strip() or date_to.strip():
            liste = ft.Text("Aucune dépense sur la période sélectionnée.", color=MUTED)
        else:
            liste = ft.Text("Aucune dépense. Cliquez « Nouvelle dépense », ou importez "
                            "une facture depuis une fiche prestataire.",
                            color=MUTED)

        def on_page(idx):
            self.dep_page = idx
            self._refresh_depenses()

        self.dep_summary.content = self._money_summary([
            ("Total dû", du, TEXT),
            ("Réglé", regle, GREEN),
            ("Reste à payer", reste, AMBER),
        ])
        self.dep_results.content = self._card(liste)
        self.dep_pager.content = self._pagination(self.dep_page, count, on_page)
        self.page.update()

    def _depense_list_row(self, dep: "repo.Depense", pr: "repo.Prestataire | None",
                          from_fiche: bool = False) -> ft.Control:
        label, color = _DEPENSE_STATUT_LABELS.get(dep.statut, (dep.statut, MUTED))
        chip = ft.Container(
            ft.Text(label, size=12, color=color),
            bgcolor=ft.Colors.with_opacity(0.12, color),
            padding=ft.Padding.symmetric(vertical=4, horizontal=10), border_radius=20,
        )
        if dep.statut in ("regle", "regle_partiellement") and dep.date_paiement:
            mode_txt = _MODE_LABELS.get(dep.mode, "mode non précisé")
            sub = f"Dernier règlement le {_iso_to_fr(dep.date_paiement)} · {mode_txt}"
        else:
            sub = f"Échéance : {_iso_to_fr(dep.date_echeance) or '—'}"
        back = "fiche" if from_fiche else "depenses"
        actions: list[ft.Control] = []
        if not from_fiche:
            actions.append(ft.TextButton(
                "Ouvrir la fiche",
                on_click=lambda e, pid=(pr.id if pr else dep.prestataire_id):
                    self.show_prestataire_detail(pid)))
        if dep.statut != "regle":
            actions.append(ft.IconButton(
                ft.Icons.CHECK_CIRCLE, tooltip="Régler (versement)", icon_color=GREEN,
                on_click=lambda e, d=dep: self._regler_depense(d, back)))
        actions.append(ft.IconButton(
            ft.Icons.DELETE_OUTLINE, tooltip="Supprimer la dépense", icon_color=RED,
            on_click=lambda e, d=dep: self._supprimer_depense(d, back)))
        title = pr.display if pr else (dep.libelle or "Dépense")
        return ft.Row([
            ft.Column([
                ft.Text(f"{dep.montant:.2f}", weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(f"réglé {dep.montant_regle:.2f} · reste {dep.reste:.2f}",
                        size=11, color=MUTED),
            ], spacing=2, width=160),
            ft.Column([
                ft.Text(title, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=2, expand=True),
            chip, *actions,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _after_depense_change(self, prestataire_id: int, back: str) -> None:
        if back == "fiche":
            self.show_prestataire_detail(prestataire_id)
        else:
            self._refresh_depenses()

    def _regler_depense(self, dep: "repo.Depense", back: str = "depenses") -> None:
        """Modale de versement (partiel ou solde) : calque de _encaisser, etendue au partiel."""
        dep = repo.get_depense(self.conn, dep.id) or dep
        versement = ft.TextField(
            label="Montant versé", value=f"{dep.reste:.2f}",
            keyboard_type=ft.KeyboardType.NUMBER, autofocus=True)
        mode = ft.RadioGroup(
            value=dep.mode or "especes",
            content=ft.Column([ft.Radio(value=k, label=v) for k, v in _MODE_LABELS.items()],
                              tight=True, spacing=2))
        motif = ft.TextField(label="Motif (optionnel)", value="")
        warn = ft.Text("", color=RED, size=12)

        def confirm(e):
            try:
                v = float((versement.value or "0").replace(",", "."))
            except ValueError:
                warn.value = "Montant invalide."; self.page.update(); return
            if v <= 0:
                warn.value = "Le versement doit être strictement supérieur à 0."
                self.page.update(); return
            if v > dep.reste + 1e-9:
                warn.value = f"Le versement dépasse le reste à payer ({dep.reste:.2f})."
                self.page.update(); return
            if not mode.value:
                warn.value = "Sélectionnez un mode de règlement."; self.page.update(); return
            new = repo.add_depense_reglement(
                self.conn, dep.id, v, mode=mode.value, motif=motif.value or None)
            repo.log_audit(
                self.conn, "depense_reglee",
                f"#{dep.id} +{v:.2f} ({_MODE_LABELS.get(mode.value, mode.value)}) "
                f"→ {new.statut} (prestataire #{dep.prestataire_id})")
            self._close_dialog()
            self._toast("Dépense soldée." if new.statut == "regle" else "Règlement enregistré.")
            self._after_depense_change(dep.prestataire_id, back)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Régler la dépense"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"Total dû : {dep.montant:.2f}", color=MUTED),
                    ft.Text(f"Déjà réglé : {dep.montant_regle:.2f}", color=MUTED),
                    ft.Text(f"Reste à payer : {dep.reste:.2f}",
                            weight=ft.FontWeight.BOLD, color=AMBER),
                    versement,
                    ft.Text("Mode de règlement", weight=ft.FontWeight.BOLD, color=TEXT),
                    mode, motif, warn,
                ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=340, height=430),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Régler", confirm, icon=ft.Icons.CHECK_CIRCLE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _supprimer_depense(self, dep: "repo.Depense", back: str = "depenses") -> None:
        """Confirme puis supprime une dépense (la facture archivée reste conservée)."""
        def confirm(e):
            repo.delete_depense(self.conn, dep.id)
            repo.log_audit(
                self.conn, "depense_supprimee",
                f"#{dep.id} {dep.montant:.2f} (prestataire #{dep.prestataire_id})")
            self._close_dialog()
            self._toast("Dépense supprimée.")
            self._after_depense_change(dep.prestataire_id, back)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer la dépense"),
            content=ft.Text(
                f"Supprimer définitivement cette dépense de {dep.montant:.2f} ? "
                "La facture archivée est conservée."),
            actions=[
                ft.TextButton("Retour", on_click=lambda e: self._close_dialog()),
                self._btn("Supprimer", confirm, icon=ft.Icons.DELETE_OUTLINE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Vue PARAMETRAGE (Modeles de documents + Modeles d'email) -------------
    def show_parametrage(self, tab: str | None = None) -> None:
        """Page de parametrage regroupant les deux sous-vues, avec un sous-menu
        permettant de basculer entre « Modèles de documents » et « Emails ».

        `current_view` conserve la cle de la sous-vue active ("templates"/"mail")
        afin que les actions Nouveau / Rechercher / Pagination restent contextuelles.
        """
        self.param_tab = tab or self.param_tab
        self.current_view = self.param_tab
        self.rail.selected_index = 5  # Paramétrage (5e après Travaux=4)
        if self.param_tab == "templates":
            action = self._btn("Nouveau modèle", lambda e: self._new_template_dialog(),
                               icon=ft.Icons.ADD, shortcut=SC_NEW, busy=False)
            body = [
                ft.Text("Chaque modèle est un fichier Word. Balises : <NOM>, <PRENOM>, <DATE>, <ACTE>, <MONTANT>…",
                        color=MUTED, size=13),
                self._note_category_selector(),
                ft.Row([self.tpl_search,
                        self._btn("Renommer une catégorie",
                                  lambda e: self._rename_category_dialog(),
                                  icon=ft.Icons.LABEL_OUTLINE, primary=False, busy=False)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.tpl_results,
                self.tpl_pager,
            ]
        elif self.param_tab == "printer":
            action = None
            body = [self._printer_settings_card()]
        elif self.param_tab == "actes":
            action = self._btn("Nouvel acte", lambda e: self._acte_dialog(),
                               icon=ft.Icons.ADD, shortcut=SC_NEW, busy=False)
            inactifs_toggle = ft.Checkbox(
                label="Inclure les inactifs", value=self.actes_inclure_inactifs,
                on_change=lambda e: self._toggle_actes_inactifs(e.control.value))
            body = [
                ft.Text("Catalogue d'actes tarifés (libellé + prix), réutilisé pour "
                        "pré-remplir des montants. Retirer un acte le désactive "
                        "(il disparaît des listes de saisie) sans le supprimer.",
                        color=MUTED, size=13),
                ft.Row([self.actes_search, inactifs_toggle],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.actes_results,
                self.actes_pager,
            ]
        else:
            action = self._btn("Nouveau modèle", lambda e: self._mail_template_dialog(),
                               icon=ft.Icons.ADD, shortcut=SC_NEW, busy=False)
            body = [
                ft.Text("Associez un nom lisible à l'ID d'un template transactionnel Mailjet. "
                        "Le modèle « par défaut » est présélectionné à l'envoi.", color=MUTED, size=13),
                ft.Row([self.mail_search]),
                self.mail_results,
                self.mail_pager,
            ]
        self._set_body(self._title("Paramétrage", action), self._param_submenu(), *body)
        if self.param_tab == "templates":
            self._refresh_templates()
        elif self.param_tab == "mail":
            self._refresh_mail_templates()
        elif self.param_tab == "actes":
            self._refresh_actes()

    def _param_submenu(self) -> ft.Control:
        """Sous-menu a trois onglets de la page Parametrage."""
        def tab_btn(key: str, label: str, icon) -> ft.Control:
            active = self.param_tab == key
            return ft.Container(
                ft.Row([ft.Icon(icon, size=18, color=SURFACE if active else NAVY),
                        ft.Text(label, color=SURFACE if active else NAVY,
                                weight=ft.FontWeight.BOLD, size=13)],
                       spacing=8, tight=True),
                bgcolor=NAVY if active else ft.Colors.with_opacity(0.10, NAVY),
                padding=ft.Padding.symmetric(vertical=9, horizontal=16),
                border_radius=10, ink=True,
                on_click=lambda e, k=key: self.show_parametrage(k),
            )
        return ft.Row([
            tab_btn("templates", "Modèles de documents", ft.Icons.DESCRIPTION),
            tab_btn("mail", "Modèles d'email", ft.Icons.MARK_EMAIL_READ),
            tab_btn("actes", "Actes", ft.Icons.SELL_OUTLINED),
            tab_btn("printer", "Imprimante", ft.Icons.PRINT),
        ], spacing=10)

    # --- Sous-vue IMPRIMANTE --------------------------------------------------
    def _printer_settings_card(self) -> ft.Control:
        """Carte de configuration de l'imprimante cible (memorisee dans `meta`)."""
        # Reinitialise les actions clavier de la page (reassignees plus bas si la
        # carte aboutit a des boutons) pour ne jamais declencher une action obsolete.
        self._printer_save_action = None
        self._printer_test_action = None
        try:
            printers = printing.list_printers()
        except Exception as exc:  # noqa: BLE001
            return self._card(ft.Text(
                f"Impossible de lister les imprimantes : {exc}", color=RED))
        saved = repo.get_setting(self.conn, PRINTER_KEY)
        current = saved or printing.default_printer()
        if printers and current not in printers:
            current = printers[0]

        intro = ft.Text(
            "Choisissez l'imprimante sur laquelle imprimer les notes générées. "
            "Ce réglage est mémorisé : le bouton Imprimer d'un document l'utilise "
            "directement. L'impression part de l'ordinateur où tourne l'application "
            "(et non du navigateur, en mode web).",
            color=MUTED, size=13)

        if not printers:
            return self._card(ft.Column([
                intro,
                ft.Text("Aucune imprimante détectée sur cet ordinateur.", color=RED),
            ], spacing=12))

        dd = ft.Dropdown(
            label="Imprimante cible", value=current,
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(p) for p in printers], expand=True,
        )

        # --- Reglages par type de document (format papier / couleur) -----------
        # Types connus = union des noms de modeles et des types deja generes.
        known_types = sorted(
            {t.name for t in templates.list_templates()}
            | set(repo.all_document_types(self.conn))
        )
        all_cfg = print_settings.all_settings(self.conn)
        # type -> (dropdown format, dropdown couleur), lus a l'enregistrement.
        type_controls: dict[str, tuple[ft.Dropdown, ft.Dropdown]] = {}

        def _type_dropdown(options, value):
            # Cle "" = « Defaut imprimante » (=> None cote print_settings).
            return ft.Dropdown(
                value=value or "", width=190, dense=True,
                color=TEXT, text_style=ft.TextStyle(color=TEXT),
                options=[ft.dropdown.Option(key=(k or ""), text=lbl)
                         for k, lbl in options],
            )

        type_rows: list[ft.Control] = []
        for t in known_types:
            cfg = all_cfg.get(t, {})
            paper_dd = _type_dropdown(_PAPER_OPTIONS, cfg.get("paper"))
            color_dd = _type_dropdown(_COLOR_OPTIONS, cfg.get("color"))
            type_controls[t] = (paper_dd, color_dd)
            type_rows.append(ft.Row(
                [ft.Text(t.replace("_", " "), color=TEXT, size=13, width=210),
                 paper_dd, color_dd],
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10))

        def on_save(e=None):
            if not dd.value:
                self._toast("Choisissez une imprimante.", ok=False); return
            repo.set_setting(self.conn, PRINTER_KEY, dd.value)
            repo.log_audit(self.conn, "imprimante_configuree", dd.value)
            for t, (pdd, cdd) in type_controls.items():
                print_settings.set_settings_for(
                    self.conn, t, pdd.value or None, cdd.value or None)
            if type_controls:
                repo.log_audit(self.conn, "reglages_impression_configures",
                               f"{len(type_controls)} type(s)")
                self._toast(f"Imprimante « {dd.value} » et réglages par type "
                            "enregistrés.")
            else:
                self._toast(f"Imprimante « {dd.value} » enregistrée.")

        def on_test(e=None):
            if not dd.value:
                self._toast("Choisissez une imprimante.", ok=False); return
            printer = dd.value

            def work():
                printing.print_test_page(printer)
                self._toast(f"Page de test envoyée à « {printer} ».")

            # `test_btn` (defini plus bas) plutot que e.control : robuste a l'appel
            # clavier (Ctrl+P) ou il n'y a pas d'evenement.
            self._run_busy(test_btn, None, work)

        save_btn = self._btn("Enregistrer", on_save, icon=ft.Icons.SAVE,
                             shortcut=SC_SAVE, busy=False)
        test_btn = self._btn("Imprimer une page de test", on_test, icon=ft.Icons.PRINT,
                            primary=False, shortcut=SC_PRINT, busy=False)
        # Expose les actions au clavier tant que la page Imprimante est affichee
        # (Ctrl+S enregistrer / Ctrl+P test) — cf. _on_key.
        self._printer_save_action = on_save
        self._printer_test_action = on_test

        if saved:
            note = f"Imprimante enregistrée : « {saved} »."
        elif current:
            note = f"Aucune imprimante enregistrée. Défaut Windows : « {current} »."
        else:
            note = "Aucune imprimante enregistrée."

        # Section « réglages par type » : tableau type -> Format / Couleur.
        types_title = ft.Text("Format et couleur par type de document",
                              size=14, weight=ft.FontWeight.BOLD, color=TEXT)
        types_intro = ft.Text(
            "Appliqués automatiquement, sans boîte de dialogue, au moment "
            "d'imprimer un document. « Défaut imprimante » conserve le réglage "
            "par défaut de l'imprimante (comportement antérieur).",
            color=MUTED, size=13)
        if type_rows:
            header = ft.Row([
                ft.Text("Type de document", color=MUTED, size=12,
                        weight=ft.FontWeight.BOLD, width=210),
                ft.Text("Format", color=MUTED, size=12,
                        weight=ft.FontWeight.BOLD, width=190),
                ft.Text("Couleur", color=MUTED, size=12,
                        weight=ft.FontWeight.BOLD, width=190),
            ], spacing=10)
            types_section: ft.Control = ft.Column([header, *type_rows], spacing=8)
        else:
            types_section = ft.Text(
                "Aucun type de document connu pour l'instant "
                "(créez un modèle ou générez un document).",
                color=MUTED, size=12)

        return self._card(ft.Column([
            intro,
            ft.Row([dd,
                    ft.IconButton(ft.Icons.REFRESH, tooltip="Rafraîchir la liste",
                                  icon_color=NAVY,
                                  on_click=lambda e: self.show_parametrage("printer"))],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(note, size=12, color=MUTED),
            ft.Divider(height=1, color=BORDER),
            types_title,
            types_intro,
            types_section,
            ft.Row([save_btn, test_btn], spacing=10),
        ], spacing=14))

    # --- Sous-vue MODELES DE DOCUMENTS ----------------------------------------
    def show_templates(self) -> None:
        self.show_parametrage("templates")

    def _template_row(self, t: templates.Template) -> ft.Control:
        """Ligne d'un modele dans la liste (icône, nom, fichier, actions)."""
        return ft.Row([
            ft.Icon(ft.Icons.DESCRIPTION, color=NAVY),
            ft.Column([
                ft.Text(t.label, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(t.path.name, size=12, color=MUTED),
            ], spacing=2, expand=True),
            self._btn("Éditer dans Word", lambda e, tt=t: self._edit_template(tt),
                      icon=ft.Icons.OPEN_IN_NEW, primary=False),
            ft.IconButton(ft.Icons.TUNE, tooltip="Configurer les variables",
                          icon_color=NAVY, on_click=lambda e, tt=t: self._template_fields_dialog(tt)),
            ft.IconButton(ft.Icons.SELL_OUTLINED, tooltip="Catégorie",
                          icon_color=NAVY, on_click=lambda e, tt=t: self._set_template_category_dialog(tt)),
            ft.IconButton(ft.Icons.DRIVE_FILE_RENAME_OUTLINE, tooltip="Renommer",
                          icon_color=NAVY, on_click=lambda e, tt=t: self._rename_template_dialog(tt)),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Supprimer", icon_color=RED,
                          on_click=lambda e, tt=t: self._delete_template_dialog(tt)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _refresh_templates(self) -> None:
        q = (self.tpl_search.value or "").strip().lower()
        all_tpls = templates.list_templates()
        if q:
            all_tpls = [t for t in all_tpls if q in t.label.lower() or q in t.name.lower()]
        total = len(all_tpls)
        self.tpl_page = self._clamp_page(self.tpl_page, total)
        start = self.tpl_page * PAGE_SIZE
        tpls = all_tpls[start:start + PAGE_SIZE]

        # Categorie de chaque modele de la page, puis regroupement par categorie
        # (ordre des categories connues, puis inconnues, « Sans catégorie » en dernier).
        cat_of = {t.name: repo.get_template_category(self.conn, t.name) for t in tpls}
        order = [c.nom for c in repo.list_categories(self.conn)]
        groups: dict[str | None, list] = {}
        for t in tpls:
            groups.setdefault(cat_of[t.name], []).append(t)

        def sort_key(nom):
            if nom is None:
                return (2, "")
            return (0, order.index(nom)) if nom in order else (1, nom.lower())

        blocks: list[ft.Control] = []
        for nom in sorted(groups.keys(), key=sort_key):
            items = groups[nom]
            blocks.append(self._cat_pastille(nom, len(items)))
            blocks.append(ft.Column([self._template_row(t) for t in items], spacing=10))
        if blocks:
            liste = ft.Column(blocks, spacing=12)
        elif q:
            liste = ft.Text("Aucun modèle ne correspond à votre recherche.", color=MUTED)
        else:
            liste = ft.Text("Aucun modèle. Créez-en un avec le bouton ci-dessus.", color=MUTED)

        def on_page(idx):
            self.tpl_page = idx
            self._refresh_templates()

        self.tpl_results.content = self._card(liste)
        self.tpl_pager.content = self._pagination(self.tpl_page, total, on_page)
        self.page.update()

    def _template_fields_dialog(self, template: templates.Template) -> None:
        try:
            detected = extract_placeholders(template.path)
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Lecture du modèle impossible : {exc}", ok=False)
            return
        existing = {f.tag: f for f in repo.list_template_fields(self.conn, template.name)}
        auto = [t for t in detected if t in generator.AUTO_PATIENT_TAGS]
        custom = [t for t in detected if t not in generator.AUTO_PATIENT_TAGS]

        controls: dict[str, tuple] = {}
        field_rows = []
        for tag in custom:
            ex = existing.get(tag)
            label_tf = ft.TextField(value=(ex.label if ex else _humanize(tag)),
                                    label="Libellé", expand=True)
            type_dd = ft.Dropdown(
                value=(ex.type if ex else _guess_type(tag)), width=130,
                color=TEXT, text_style=ft.TextStyle(color=TEXT),
                options=[ft.dropdown.Option("text", "Texte"),
                         ft.dropdown.Option("paragraph", "Paragraphe"),
                         ft.dropdown.Option("number", "Nombre"),
                         ft.dropdown.Option("date", "Date")],
            )
            default_tf = ft.TextField(value=(ex.default_value if ex else ""),
                                      label="Défaut", width=120)
            controls[tag] = (label_tf, type_dd, default_tf)
            field_rows.append(ft.Row(
                [ft.Container(ft.Text(f"<{tag}>", color=NAVY, weight=ft.FontWeight.W_600), width=140),
                 label_tf, type_dd, default_tf],
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8))

        body = []
        if auto:
            body.append(ft.Text(
                "Auto-remplies depuis la fiche patient : " + ", ".join(f"<{t}>" for t in auto),
                color=MUTED, size=12))
        body += field_rows or [ft.Text(
            "Aucune variable personnalisée détectée. Ajoutez des balises <MA_VARIABLE> "
            "dans le modèle Word puis revenez ici.", color=MUTED, size=12)]

        def on_save(e):
            fields = [
                TemplateField(template.name, tag,
                              (l.value or _humanize(tag)), (ty.value or "text"), (d.value or ""))
                for tag, (l, ty, d) in controls.items()
            ]
            repo.replace_template_fields(self.conn, template.name, fields)
            self._close_dialog()
            self._toast("Variables enregistrées.")

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Variables — {template.label}"),
            content=ft.Container(
                ft.Column(body, tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=620, height=440),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                # Sauvegarde instantanee (ecriture SQLite) : pas de spinner inutile.
                # Cf. _mail_template_dialog, meme cas en busy=False.
                self._btn("Enregistrer", on_save, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Sous-vue MODELES D'EMAIL (Mailjet) -----------------------------------
    def show_mail_templates(self) -> None:
        self.show_parametrage("mail")

    def _refresh_mail_templates(self) -> None:
        q = (self.mail_search.value or "").strip().lower()
        all_templates = repo.list_mail_templates(self.conn)
        if q:
            mtemplates = [t for t in all_templates
                          if q in t.name.lower() or q in str(t.mailjet_template_id)]
        else:
            mtemplates = all_templates
        total = len(mtemplates)
        self.mail_page = self._clamp_page(self.mail_page, total)
        start = self.mail_page * PAGE_SIZE
        mtemplates = mtemplates[start:start + PAGE_SIZE]
        rows = []
        for t in mtemplates:
            badge = []
            if t.is_default:
                badge.append(ft.Container(
                    ft.Text("Par défaut", size=11, color=GREEN),
                    bgcolor=ft.Colors.with_opacity(0.12, GREEN),
                    padding=ft.Padding.symmetric(vertical=3, horizontal=8), border_radius=20))
            actions = []
            if not t.is_default:
                actions.append(ft.IconButton(ft.Icons.STAR_OUTLINE, tooltip="Définir par défaut",
                               icon_color=NAVY, on_click=lambda e, tt=t: self._set_default_mail_template(tt)))
            actions += [
                ft.IconButton(ft.Icons.EDIT, tooltip="Modifier", icon_color=NAVY,
                              on_click=lambda e, tt=t: self._mail_template_dialog(tt)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Supprimer", icon_color=RED,
                              on_click=lambda e, tt=t: self._delete_mail_template(tt)),
            ]
            rows.append(ft.Row([
                ft.Icon(ft.Icons.MARK_EMAIL_READ, color=NAVY),
                ft.Column([
                    ft.Text(t.name, weight=ft.FontWeight.W_600, color=TEXT),
                    ft.Text(f"Template Mailjet #{t.mailjet_template_id}", size=12, color=MUTED),
                ], spacing=2, expand=True),
                *badge, *actions,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER))
        if rows:
            liste = ft.Column(rows, spacing=8)
        elif q:
            liste = ft.Text("Aucun modèle ne correspond à votre recherche.", color=MUTED)
        else:
            liste = ft.Text(
                "Aucun modèle d'email. Ajoutez-en un (nom + ID de template Mailjet).", color=MUTED)

        def on_page(idx):
            self.mail_page = idx
            self._refresh_mail_templates()

        self.mail_results.content = self._card(liste)
        self.mail_pager.content = self._pagination(self.mail_page, total, on_page)
        self.page.update()

    def _mail_template_dialog(self, t: "repo.MailTemplate | None" = None) -> None:
        is_edit = t is not None
        name = ft.TextField(label="Nom du modèle (ex. Note d'honoraires)",
                            value=t.name if t else "", autofocus=True)
        mid = ft.TextField(label="ID du template Mailjet",
                           value=str(t.mailjet_template_id) if t else "",
                           keyboard_type=ft.KeyboardType.NUMBER)
        is_def = ft.Checkbox(label="Modèle par défaut", value=t.is_default if t else False)
        status = ft.Text("", color=RED, size=12)

        def on_save(e):
            if not name.value.strip():
                status.value = "Le nom est obligatoire."; self.page.update(); return
            try:
                mid_val = int((mid.value or "").strip())
            except ValueError:
                status.value = "L'ID Mailjet doit être un nombre."; self.page.update(); return
            if is_edit:
                t.name = name.value; t.mailjet_template_id = mid_val; t.is_default = is_def.value
                repo.update_mail_template(self.conn, t)
            else:
                repo.create_mail_template(self.conn, repo.MailTemplate(
                    id=None, name=name.value, mailjet_template_id=mid_val, is_default=is_def.value))
            self._close_dialog()
            self._toast("Modèle d'email enregistré.")
            self._refresh_mail_templates()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier le modèle d'email" if is_edit else "Nouveau modèle d'email"),
            content=ft.Container(ft.Column([name, mid, is_def, status], tight=True, spacing=12), width=400),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _set_default_mail_template(self, t: "repo.MailTemplate") -> None:
        repo.set_default_mail_template(self.conn, t.id)
        self._refresh_mail_templates()

    def _delete_mail_template(self, t: "repo.MailTemplate") -> None:
        repo.delete_mail_template(self.conn, t.id)
        self._toast("Modèle supprimé.")
        self._refresh_mail_templates()

    # --- Sous-vue ACTES (referentiel tarife) ----------------------------------
    def _toggle_actes_inactifs(self, value: bool) -> None:
        """Bascule « inclure les inactifs » : remet en 1re page et rafraichit."""
        self.actes_inclure_inactifs = bool(value)
        self.actes_page = 0
        self._refresh_actes()

    def _refresh_actes(self) -> None:
        search = self.actes_search.value or ""
        actifs_seulement = not self.actes_inclure_inactifs
        total = repo.count_actes(self.conn, search, actifs_seulement)
        self.actes_page = self._clamp_page(self.actes_page, total)
        actes = repo.list_actes(
            self.conn, search, actifs_seulement,
            limit=PAGE_SIZE, offset=self.actes_page * PAGE_SIZE)
        rows = [self._acte_row(a) for a in actes]
        if rows:
            liste = ft.Column(rows, spacing=8)
        elif search.strip():
            liste = ft.Text("Aucun acte ne correspond à votre recherche.", color=MUTED)
        else:
            liste = ft.Text(
                "Aucun acte. Ajoutez-en un avec le bouton ci-dessus.", color=MUTED)

        def on_page(idx):
            self.actes_page = idx
            self._refresh_actes()

        self.actes_results.content = self._card(liste)
        self.actes_pager.content = self._pagination(self.actes_page, total, on_page)
        self.page.update()

    def _acte_row(self, a: "repo.Acte") -> ft.Control:
        """Ligne d'un acte : libellé (+ code), prix formaté, badge « inactif »,
        actions (modifier, désactiver/réactiver).

        Le retrait est la désactivation NON destructive (icône œil), réversible :
        un acte inactif disparaît des listes de saisie mais reste en base. Aucune
        suppression dure n'est exposée ici (cohérent avec la philosophie de
        préservation des données ; `repo.delete_acte` reste disponible pour le
        `reset` ou une future purge gardée des actes jamais utilisés)."""
        sub = f"Code : {a.code}" if a.code else "Sans code"
        badge: list[ft.Control] = []
        if not a.actif:
            badge.append(ft.Container(
                ft.Text("Inactif", size=11, color=MUTED),
                bgcolor=ft.Colors.with_opacity(0.12, MUTED),
                padding=ft.Padding.symmetric(vertical=3, horizontal=8), border_radius=20))
        actions: list[ft.Control] = [
            ft.IconButton(ft.Icons.EDIT, tooltip="Modifier", icon_color=NAVY,
                          on_click=lambda e, aa=a: self._acte_dialog(aa)),
        ]
        if a.actif:
            actions.append(ft.IconButton(
                ft.Icons.VISIBILITY_OFF_OUTLINED,
                tooltip="Désactiver (retirer des listes de saisie)", icon_color=AMBER,
                on_click=lambda e, aa=a: self._set_acte_actif(aa, False)))
        else:
            actions.append(ft.IconButton(
                ft.Icons.VISIBILITY_OUTLINED, tooltip="Réactiver", icon_color=GREEN,
                on_click=lambda e, aa=a: self._set_acte_actif(aa, True)))
        return ft.Row([
            ft.Icon(ft.Icons.SELL_OUTLINED, color=NAVY),
            ft.Column([
                ft.Text(a.libelle, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=2, expand=True),
            ft.Text(_fmt_prix(a.prix), color=TEXT, weight=ft.FontWeight.W_600,
                    width=120, text_align=ft.TextAlign.RIGHT),
            *badge, *actions,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _set_acte_actif(self, a: "repo.Acte", actif: bool) -> None:
        repo.set_acte_actif(self.conn, a.id, actif)
        repo.log_audit(self.conn, "acte_reactive" if actif else "acte_desactive",
                       f"#{a.id} {a.libelle}")
        self._toast("Acte réactivé." if actif
                    else "Acte désactivé (retiré des listes de saisie).")
        self._refresh_actes()

    def _acte_dialog(self, a: "repo.Acte | None" = None) -> None:
        is_edit = a is not None
        libelle = ft.TextField(label="Libellé (ex. Détartrage)",
                               value=a.libelle if a else "", autofocus=True)
        prix = ft.TextField(label="Prix", value=(f"{a.prix:.2f}" if a else "0"),
                            keyboard_type=ft.KeyboardType.NUMBER)
        code = ft.TextField(label="Code (facultatif)",
                            value=(a.code or "") if a else "")
        status = ft.Text("", color=RED, size=12)
        warn = ft.Text("", color=AMBER, size=12)
        # Doublon de libelle : le 1er enregistrement sur un libelle actif deja
        # present avertit (non bloquant) ; un 2e clic confirme (cf. spec).
        pending = {"confirm": False}

        def on_save(e=None):
            lib = (libelle.value or "").strip()
            if not lib:
                status.value = "Le libellé est obligatoire."; warn.value = ""
                self.page.update(); return
            try:
                prix_val = float((prix.value or "0").replace(",", "."))
            except ValueError:
                status.value = "Prix invalide."; warn.value = ""
                self.page.update(); return
            if prix_val < 0:
                status.value = "Le prix doit être positif ou nul."; warn.value = ""
                self.page.update(); return
            dup = repo.find_acte_by_libelle(
                self.conn, lib, exclude_id=a.id if a else None)
            if dup is not None and not pending["confirm"]:
                pending["confirm"] = True
                status.value = ""
                warn.value = (f"Un acte actif « {dup.libelle} » existe déjà. "
                              "Cliquez à nouveau sur Enregistrer pour confirmer.")
                self.page.update(); return
            if is_edit:
                a.libelle = lib; a.prix = prix_val; a.code = code.value or None
                repo.update_acte(self.conn, a)
                repo.log_audit(self.conn, "acte_modifie",
                               f"#{a.id} {lib} ({prix_val:.2f})")
            else:
                created = repo.create_acte(self.conn, repo.Acte(
                    id=None, libelle=lib, prix=prix_val, code=code.value or None))
                repo.log_audit(self.conn, "acte_cree",
                               f"#{created.id} {lib} ({prix_val:.2f})")
            self._close_dialog()
            self._toast("Acte enregistré.")
            self._refresh_actes()

        # Modifier le libelle apres l'avertissement annule la re-confirmation
        # (on ne veut pas confirmer un doublon qui n'en est plus un).
        def on_libelle_change(e=None):
            if pending["confirm"]:
                pending["confirm"] = False
                warn.value = ""
                self.page.update()
        libelle.on_change = on_libelle_change

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier l'acte" if is_edit else "Nouvel acte"),
            content=ft.Container(
                ft.Column([libelle, prix, code, warn, status], tight=True, spacing=12),
                width=400),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Vue TRAVAUX (Documents + liste des jobs) -----------------------------
    def show_travaux(self, tab: str | None = None) -> None:
        """Page Travaux a deux sous-vues : « Documents » (lignes de documents,
        avec navigation vers la fiche patient) et « Travaux » (jobs par lot).

        `current_view` conserve la cle de la sous-vue active ("documents"/"jobs")
        afin que Recherche / Pagination restent contextuelles.
        """
        self.travaux_tab = tab or self.travaux_tab
        self.current_view = "documents" if self.travaux_tab == "documents" else "jobs"
        self.rail.selected_index = 4  # Travaux
        if self.travaux_tab == "documents":
            body = [
                ft.Text("Toutes les lignes de documents. Cliquez le nom du patient "
                        "pour ouvrir sa fiche.", color=MUTED, size=13),
                ft.Row([self.doc_search, self.doc_statut,
                        ft.Container(self.doc_date_range, width=360)],
                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.doc_batch_bar,
                self.doc_results,
                self.doc_pager,
            ]
        else:
            body = [
                ft.Text("Jobs de génération et d'envoi par lot. Cliquez un job pour "
                        "voir le détail (ligne par patient).", color=MUTED, size=13),
                ft.Row([ft.Container(self.jobs_date_range, width=360)],
                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.jobs_results,
                self.jobs_pager,
            ]
        self._set_body(self._title("Travaux"), self._travaux_submenu(), *body)
        if self.travaux_tab == "documents":
            self._refresh_documents()
        else:
            self._refresh_jobs()

    def _travaux_submenu(self) -> ft.Control:
        """Sous-menu a deux onglets de la page Travaux."""
        def tab_btn(key: str, label: str, icon) -> ft.Control:
            active = self.travaux_tab == key
            return ft.Container(
                ft.Row([ft.Icon(icon, size=18, color=SURFACE if active else NAVY),
                        ft.Text(label, color=SURFACE if active else NAVY,
                                weight=ft.FontWeight.BOLD, size=13)],
                       spacing=8, tight=True),
                bgcolor=NAVY if active else ft.Colors.with_opacity(0.10, NAVY),
                padding=ft.Padding.symmetric(vertical=9, horizontal=16),
                border_radius=10, ink=True,
                on_click=lambda e, k=key: self.show_travaux(k),
            )
        return ft.Row([
            tab_btn("documents", "Documents", ft.Icons.DESCRIPTION),
            tab_btn("jobs", "Travaux", ft.Icons.WORK),
        ], spacing=10)

    def show_jobs(self) -> None:
        """Alias historique (retour depuis le detail d'un job)."""
        self.show_travaux("jobs")

    def _refresh_documents(self) -> None:
        search = self.doc_search.value or ""
        statut = self.doc_statut.value or "tous"
        date_from = _date_iso(self.doc_date_from)
        date_to = _date_iso(self.doc_date_to)
        total = repo.count_documents_filtered(self.conn, search, statut, date_from, date_to)
        self.doc_page = self._clamp_page(self.doc_page, total)
        items = repo.list_documents_filtered(
            self.conn, search, statut,
            limit=PAGE_SIZE, offset=self.doc_page * PAGE_SIZE,
            date_from=date_from, date_to=date_to,
        )
        # Barre de lot contextuelle : visible seulement sur un filtre de statut
        # actionnable (brouillon/erreur -> generer ; en_attente/erreur_envoi -> envoyer).
        action = self._doc_batch_action()
        if action:
            self.doc_batch_bar.content = self._doc_batch_bar_content(action)
        else:
            self.doc_batch_bar.content = None
            self.doc_selected.clear()
        rows = [self._doc_line_row(d, pt, selectable=bool(action)) for d, pt in items]
        if rows:
            liste = ft.Column(rows, spacing=8)
        elif search.strip():
            liste = ft.Text("Aucun document ne correspond à votre recherche.", color=MUTED)
        elif date_from.strip() or date_to.strip():
            liste = ft.Text("Aucun document sur la période sélectionnée.", color=MUTED)
        else:
            liste = ft.Text("Aucun document.", color=MUTED)

        def on_page(idx):
            self.doc_page = idx
            self._refresh_documents()

        self.doc_results.content = self._card(liste)
        self.doc_pager.content = self._pagination(self.doc_page, total, on_page)
        self.page.update()

    def _doc_line_row(self, d: Document, patient: Patient,
                      selectable: bool = False) -> ft.Control:
        """Ligne de la page Documents : case de selection (en mode lot), cellule
        patient cliquable + actions (ouvrir le fichier, generer un brouillon,
        envoyer un email unitaire)."""
        label, color = _STATUT_LABELS.get(d.statut, (d.statut, MUTED))
        sub = " · ".join(filter(None, [
            _humanize(d.type),
            d.date_envoi or d.date_generation or "",
        ]))
        cells: list[ft.Control] = []
        if selectable:
            cells.append(ft.Checkbox(
                value=d.id in self.doc_selected,
                on_change=lambda e, did=d.id: self._doc_toggle_select(did, e.control.value)))
        actions: list[ft.Control] = []
        if d.statut in ("brouillon", "erreur"):
            tip = "Générer le document" if d.statut == "brouillon" else "Réessayer la génération"
            actions.append(ft.IconButton(
                ft.Icons.PLAY_CIRCLE_OUTLINE, tooltip=tip, icon_color=NAVY,
                on_click=lambda e, dd=d: self._render_draft(e, dd)))
        else:
            actions.append(ft.IconButton(
                ft.Icons.FOLDER_OPEN, tooltip="Ouvrir le fichier",
                on_click=lambda e, dd=d: self._open_file(dd)))
            actions.append(ft.IconButton(
                ft.Icons.PRINT, tooltip="Imprimer", icon_color=NAVY,
                on_click=lambda e, dd=d: self._print_file(e, dd)))
        if d.email and d.statut in ("en_attente_envoi", "erreur_envoi"):
            actions.append(ft.IconButton(
                ft.Icons.SEND, tooltip="Envoyer par email", icon_color=NAVY,
                on_click=lambda e, dd=d: self._send_dialog(dd)))
        cells += [
            ft.Icon(ft.Icons.PICTURE_AS_PDF if d.output_format == "pdf" else ft.Icons.IMAGE,
                    color=TEAL_DARK),
            ft.Column([
                ft.TextButton(
                    patient.display, tooltip="Ouvrir la fiche patient",
                    on_click=lambda e, pid=patient.id: self.show_patient_detail(pid)),
                ft.Text(sub, size=12, color=MUTED),
            ], spacing=0, expand=True),
            ft.Text(_doc_label(d), color=TEXT, width=160),
            ft.Container(ft.Text(label, size=12, color=color),
                         bgcolor=ft.Colors.with_opacity(0.12, color),
                         padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                         border_radius=20),
            *actions,
        ]
        return ft.Row(cells, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _after_doc_change(self) -> None:
        """Rafraichit la bonne vue apres une action document (generation/envoi) :
        la liste Documents si on y est, sinon la fiche patient courante."""
        if self.current_view == "documents":
            self._refresh_documents()
        elif self.current_patient:
            self.show_patient_detail(self.current_patient.id)

    def _refresh_jobs(self, conn: sqlite3.Connection | None = None) -> None:
        conn = conn or self.conn
        date_from = _date_iso(self.jobs_date_from)
        date_to = _date_iso(self.jobs_date_to)
        total = repo.count_jobs(conn, date_from, date_to)
        self.jobs_page = self._clamp_page(self.jobs_page, total)
        jobs = repo.list_jobs(
            conn, limit=PAGE_SIZE, offset=self.jobs_page * PAGE_SIZE,
            date_from=date_from, date_to=date_to)
        rows = [self._job_row(j) for j in jobs]
        if rows:
            liste = ft.Column(rows, spacing=8)
        elif date_from.strip() or date_to.strip():
            liste = ft.Text("Aucun job sur la période sélectionnée.", color=MUTED)
        else:
            liste = ft.Text("Aucun job lancé pour l'instant.", color=MUTED)

        def on_page(idx):
            self.jobs_page = idx
            self._refresh_jobs()

        self.jobs_results.content = self._card(liste)
        self.jobs_pager.content = self._pagination(self.jobs_page, total, on_page)
        self.page.update()

    def _job_row(self, j: Job) -> ft.Control:
        label, color = _JOB_STATUT_LABELS.get(j.statut, (j.statut, MUTED))
        kind_label = "Génération" if j.kind == "generation" else "Envoi email"
        progress = (j.done / j.total) if j.total else 0.0
        chip = ft.Container(
            ft.Text(label, size=12, color=color),
            bgcolor=ft.Colors.with_opacity(0.12, color),
            padding=ft.Padding.symmetric(vertical=4, horizontal=10), border_radius=20,
        )
        counts = (f"{j.done}/{j.total} traité(s) · {j.ok} ok · "
                  f"{j.skipped} ignoré(s) · {j.errors} erreur(s)")
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.BUILD_CIRCLE if j.kind == "generation"
                        else ft.Icons.OUTGOING_MAIL, color=TEAL_DARK),
                ft.Column([
                    ft.Text(f"#{j.id} · {kind_label} — {_humanize(j.doc_type)}",
                            weight=ft.FontWeight.W_600, color=TEXT),
                    ft.Text(counts, size=12, color=MUTED),
                    ft.ProgressBar(value=progress, color=NAVY,
                                   bgcolor=ft.Colors.with_opacity(0.15, NAVY), width=320),
                    ft.Text(j.created_at or "", size=11, color=MUTED),
                ], spacing=4, expand=True),
                chip,
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=MUTED),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10, border_radius=10, ink=True,
            on_click=lambda e, jid=j.id: self.show_job_detail(jid),
        )

    def show_job_detail(self, job_id: int,
                        conn: sqlite3.Connection | None = None) -> None:
        # `conn` : passe par le thread d'un job en cours (cf. show_patient_detail)
        # pour ne pas partager self.conn entre threads.
        conn = conn or self.conn
        self.current_view = "job_detail"
        self.current_job_id = job_id
        self.rail.selected_index = 4  # détail d'un job : sous Travaux
        job = repo.get_job(conn, job_id)
        if not job:
            return self.show_jobs()
        kind_label = "Génération" if job.kind == "generation" else "Envoi email"
        header_row = [
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.show_jobs()),
            ft.Text(f"Job #{job.id} — {kind_label} · {_humanize(job.doc_type)}",
                    size=22, weight=ft.FontWeight.BOLD, color=TEXT),
        ]
        # Relance des erreurs : seulement si le job est fini et a des echecs.
        if job.statut in ("termine", "termine_partiel", "erreur", "interrompu") and job.errors:
            header_row.append(ft.Container(expand=True))
            header_row.append(self._btn(
                "Relancer les erreurs", lambda e, j=job: self._relaunch_failed(j),
                icon=ft.Icons.REPLAY, busy=False))
        header = ft.Row(header_row, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self._set_body(header, self.job_detail_container)
        self._refresh_job_detail(job_id, conn)

    def _relaunch_failed(self, job: Job) -> None:
        """Relance un nouveau job sur les seuls documents en échec du job donné."""
        if self._job_running:
            self._toast("Un job est déjà en cours.", ok=False)
            return
        failed = repo.list_failed_job_items(self.conn, job.id)
        doc_ids = [it.document_id for it in failed if it.document_id]
        if not doc_ids:
            self._toast("Aucune erreur à relancer.", ok=False)
            return
        try:
            params = json.loads(job.params) if job.params else {}
        except (ValueError, TypeError):
            params = {}
        repo.log_audit(self.conn, "job_relance",
                       f"job #{job.id} → {len(doc_ids)} document(s) en erreur")
        self._launch_job(job.kind, job.doc_type, document_ids=doc_ids, params=params)

    def _refresh_job_detail(self, job_id: int,
                            conn: sqlite3.Connection | None = None) -> None:
        conn = conn or self.conn
        job = repo.get_job(conn, job_id)
        if not job:
            return
        label, color = _JOB_STATUT_LABELS.get(job.statut, (job.statut, MUTED))
        progress = (job.done / job.total) if job.total else 0.0
        summary = self._card(ft.Column([
            ft.Row([
                ft.Container(ft.Text(label, size=12, color=color),
                             bgcolor=ft.Colors.with_opacity(0.12, color),
                             padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                             border_radius=20),
                ft.Container(expand=True),
                ft.Text(f"{job.done}/{job.total}", color=MUTED, size=12),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.ProgressBar(value=progress, color=NAVY,
                           bgcolor=ft.Colors.with_opacity(0.15, NAVY)),
            ft.Text(f"{job.ok} ok · {job.skipped} ignoré(s) · {job.errors} erreur(s)",
                    size=12, color=MUTED),
        ], spacing=10))

        items = repo.list_job_items(conn, job_id)
        item_rows = []
        for it in items:
            ilabel, icolor = _JOB_ITEM_LABELS.get(it.statut, (it.statut, MUTED))
            patient = repo.get_patient(conn, it.patient_id) if it.patient_id else None
            doc = repo.get_document(conn, it.document_id) if it.document_id else None
            # Cellule patient cliquable -> fiche du patient.
            if patient:
                name_ctrl = ft.TextButton(
                    patient.display, tooltip="Ouvrir la fiche patient",
                    on_click=lambda e, pid=patient.id: self.show_patient_detail(pid))
            else:
                name_ctrl = ft.Text(f"Patient #{it.patient_id}",
                                    weight=ft.FontWeight.W_600, color=TEXT)
            # Action : ouvrir le document genere depuis la ligne (si fichier present).
            row_actions: list[ft.Control] = []
            if doc and doc.file_path:
                row_actions.append(ft.IconButton(
                    ft.Icons.FOLDER_OPEN, tooltip="Ouvrir le fichier", icon_color=NAVY,
                    on_click=lambda e, dd=doc: self._open_file(dd)))
                row_actions.append(ft.IconButton(
                    ft.Icons.PRINT, tooltip="Imprimer", icon_color=NAVY,
                    on_click=lambda e, dd=doc: self._print_file(e, dd)))
            item_rows.append(ft.Row([
                ft.Container(ft.Text(ilabel, size=12, color=icolor),
                             bgcolor=ft.Colors.with_opacity(0.12, icolor),
                             padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                             border_radius=20, width=90, alignment=ft.Alignment.CENTER),
                ft.Column([
                    name_ctrl,
                    ft.Text(it.message or "", size=12,
                            color=RED if it.statut == "erreur" else MUTED),
                ], spacing=2, expand=True),
                *row_actions,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER))
        detail = (ft.Column(item_rows, spacing=8) if item_rows
                  else ft.Text("Aucune ligne traitée pour l'instant.", color=MUTED))

        self.job_detail_container.content = ft.Column([
            summary,
            ft.Text("Détail par patient", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
            self._card(detail),
        ], spacing=18)
        self.page.update()

    # --- Vue PRESTATAIRES -----------------------------------------------------
    def show_prestataires(self) -> None:
        self.current_view = "prestataires"
        self.rail.selected_index = 2
        self._set_body(
            self._title(
                "Prestataires",
                self._btn("Nouveau prestataire", lambda e: self._prestataire_dialog(),
                          icon=ft.Icons.ADD, shortcut=SC_NEW, busy=False),
            ),
            ft.Row([self.pr_search], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.pr_results,
            self.pr_pager,
        )
        self._refresh_prestataires()

    def _refresh_prestataires(self) -> None:
        search = self.pr_search.value or ""
        total = repo.count_prestataires(self.conn, search)
        self.pr_page = self._clamp_page(self.pr_page, total)
        items = repo.list_prestataires(
            self.conn, search, limit=PAGE_SIZE, offset=self.pr_page * PAGE_SIZE)
        rows = [self._prestataire_row(p) for p in items]
        empty = ("Aucun prestataire ne correspond à votre recherche." if search.strip()
                 else "Aucun prestataire. Cliquez sur « Nouveau prestataire ».")
        liste = ft.Column(rows, spacing=8) if rows else ft.Text(empty, color=MUTED)

        def on_page(idx):
            self.pr_page = idx
            self._refresh_prestataires()

        self.pr_results.content = self._card(liste)
        self.pr_pager.content = self._pagination(self.pr_page, total, on_page)
        self.page.update()

    def _prestataire_row(self, p: "repo.Prestataire") -> ft.Control:
        sub = " · ".join(filter(None, [p.email, p.telephone])) or "—"
        avatar = ft.CircleAvatar(
            content=ft.Icon(ft.Icons.STOREFRONT, color=NAVY, size=18), bgcolor=TEAL, radius=18)
        infos = ft.Column(
            [ft.Text(p.display, weight=ft.FontWeight.W_600, color=TEXT),
             ft.Text(sub, size=12, color=MUTED)],
            spacing=2, expand=True)
        return ft.Container(
            content=ft.Row(
                [avatar, infos, ft.Text(f"#{p.id}", color=MUTED, size=12),
                 ft.Icon(ft.Icons.CHEVRON_RIGHT, color=MUTED)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10, border_radius=10, ink=True,
            on_click=lambda e, pid=p.id: self.show_prestataire_detail(pid),
        )

    def show_prestataire_detail(self, prestataire_id: int,
                                conn: sqlite3.Connection | None = None) -> None:
        conn = conn or self.conn
        p = repo.get_prestataire(conn, prestataire_id)
        if not p:
            return self.show_prestataires()
        if not self.current_prestataire or self.current_prestataire.id != prestataire_id:
            self.detail_pr_factures_page = 0
            self.detail_pr_depenses_page = 0
        self.current_view = "prestataire_detail"  # Echap revient a la liste
        self.current_prestataire = p

        fac_total = repo.count_factures_for_prestataire(conn, prestataire_id)
        dep_total = repo.count_depenses_for_prestataire(conn, prestataire_id)
        self.detail_pr_factures_page = self._clamp_page(self.detail_pr_factures_page, fac_total)
        self.detail_pr_depenses_page = self._clamp_page(self.detail_pr_depenses_page, dep_total)
        factures = repo.list_factures(
            conn, prestataire_id, limit=PAGE_SIZE, offset=self.detail_pr_factures_page * PAGE_SIZE)
        depenses = repo.list_depenses(
            conn, prestataire_id, limit=PAGE_SIZE, offset=self.detail_pr_depenses_page * PAGE_SIZE)
        # Totaux du prestataire (toutes ses depenses, non pagine : peu de lignes).
        all_dep = repo.list_depenses(conn, prestataire_id)
        du = sum(d.montant or 0 for d in all_dep)
        regle = sum(d.montant_regle or 0 for d in all_dep)
        reste = max(0.0, du - regle)

        async def _on_import(e):
            await self._pick_and_import(p)

        header = ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.show_prestataires()),
            ft.Text(p.display, size=24, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Container(expand=True),
            self._btn("Modifier", lambda e: self._prestataire_dialog(p), icon=ft.Icons.EDIT,
                      primary=False, shortcut=SC_EDIT, busy=False),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        infos = self._card(ft.Column([
            self._kv_copy("Email", p.email),
            self._kv_copy("Téléphone", p.telephone),
            _kv("Adresse", p.adresse or "—"),
            _kv("Notes", p.notes or "—"),
        ], spacing=6))

        summary = self._money_summary([
            ("Total dû", du, TEXT),
            ("Réglé", regle, GREEN),
            ("Reste à payer", reste, AMBER),
        ])

        fac_col = ft.Column(
            [self._facture_row(f) for f in factures] or [ft.Text("Aucune facture.", color=MUTED)],
            spacing=8)
        dep_col = ft.Column(
            [self._depense_list_row(d, p, from_fiche=True) for d in depenses]
            or [ft.Text("Aucune dépense.", color=MUTED)],
            spacing=8)

        def on_fac_page(idx):
            self.detail_pr_factures_page = idx
            self.show_prestataire_detail(prestataire_id)

        def on_dep_page(idx):
            self.detail_pr_depenses_page = idx
            self.show_prestataire_detail(prestataire_id)

        fac_pager = (self._pagination(self.detail_pr_factures_page, fac_total, on_fac_page)
                     if fac_total > PAGE_SIZE else ft.Container())
        dep_pager = (self._pagination(self.detail_pr_depenses_page, dep_total, on_dep_page)
                     if dep_total > PAGE_SIZE else ft.Container())

        self._set_body(
            header,
            infos,
            summary,
            ft.Row([
                ft.Text("Factures", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Container(expand=True),
                self._btn("Importer une facture", _on_import, icon=ft.Icons.UPLOAD_FILE,
                          primary=False, shortcut=SC_IMPORT, busy=False),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._card(fac_col),
            fac_pager,
            ft.Row([
                ft.Text("Dépenses", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Container(expand=True),
                self._btn("Nouvelle dépense", lambda e: self._depense_dialog(p),
                          icon=ft.Icons.ADD, primary=False, shortcut=SC_NEW, busy=False),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self._card(dep_col),
            dep_pager,
        )

    def _facture_row(self, f: "repo.Facture") -> ft.Control:
        info = " · ".join(filter(None, [
            f.created_at or "",
            f"{f.montant:.2f}" if f.montant else "",
        ])) or "—"
        return ft.Row([
            ft.Icon(ft.Icons.RECEIPT_LONG, color=TEAL_DARK),
            ft.Column([
                ft.Text(f.nom_original or Path(f.fichier).name, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(info, size=12, color=MUTED),
            ], spacing=2, expand=True),
            ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Ouvrir le fichier",
                          on_click=lambda e, ff=f: self._open_path(ff.fichier)),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Supprimer la facture", icon_color=RED,
                          on_click=lambda e, ff=f: self._delete_facture_dialog(ff)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _open_path(self, path: str) -> None:
        """Ouvre un fichier archive avec l'application par defaut du systeme."""
        import os
        try:
            if not path or not Path(path).exists():
                self._toast("Fichier introuvable.", ok=False); return
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess; subprocess.Popen(["open", path])
            else:
                import subprocess; subprocess.Popen(["xdg-open", path])
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Ouverture impossible : {exc}", ok=False)

    def _delete_facture_dialog(self, f: "repo.Facture") -> None:
        def confirm(e):
            try:
                if f.fichier and Path(f.fichier).exists():
                    Path(f.fichier).unlink()
            except OSError:
                pass  # fichier verrouille/absent : on supprime quand meme l'enregistrement
            repo.delete_facture(self.conn, f.id)
            repo.log_audit(self.conn, "facture_supprimee",
                           f"#{f.id} (prestataire #{f.prestataire_id})")
            self._close_dialog()
            self._toast("Facture supprimée.")
            if self.current_prestataire:
                self.show_prestataire_detail(self.current_prestataire.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer la facture"),
            content=ft.Text(
                f"Supprimer définitivement « {f.nom_original or Path(f.fichier).name} » ? "
                "Les dépenses liées sont conservées (déliées du fichier)."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Supprimer", confirm, icon=ft.Icons.DELETE_OUTLINE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _prestataire_dialog(self, p: "repo.Prestataire | None" = None) -> None:
        is_edit = p is not None
        nom = ft.TextField(label="Nom / Raison sociale *", value=p.nom if p else "", autofocus=True)
        prenom = ft.TextField(label="Prénom (optionnel)", value=(p.prenom if p else "") or "")
        email = ft.TextField(label="Email", value=(p.email if p else "") or "")
        tel = ft.TextField(label="Téléphone", value=(p.telephone if p else "") or "")
        adresse = ft.TextField(label="Adresse", value=(p.adresse if p else "") or "",
                               multiline=True, min_lines=1, max_lines=3)
        notes = ft.TextField(label="Notes", value=(p.notes if p else "") or "",
                             multiline=True, min_lines=1, max_lines=3)
        warn = ft.Text("", color=NAVY, size=12)

        def on_save(e):
            if not nom.value.strip():
                warn.value = "Le nom est obligatoire."
                self.page.update()
                return
            if not is_edit:
                matches = repo.find_prestataire_matches(self.conn, nom.value, prenom.value)
                if matches and not getattr(on_save, "_confirmed", False):
                    warn.value = (f"⚠ Un prestataire « {matches[0].display} » (#{matches[0].id}) "
                                  "existe déjà. Cliquez de nouveau sur Enregistrer pour "
                                  "créer quand même un doublon.")
                    on_save._confirmed = True
                    self.page.update()
                    return
            data = dict(
                nom=nom.value, prenom=prenom.value or "", email=email.value or None,
                telephone=tel.value or None, adresse=adresse.value or None,
                notes=notes.value or None,
            )
            if is_edit:
                for k, v in data.items():
                    setattr(p, k, v)
                repo.update_prestataire(self.conn, p)
                repo.log_audit(self.conn, "prestataire_modifie", f"#{p.id} {p.display}")
                self._close_dialog()
                self._toast("Prestataire mis à jour.")
                self.show_prestataire_detail(p.id)
            else:
                new = repo.create_prestataire(self.conn, repo.Prestataire(id=None, **data))
                repo.log_audit(self.conn, "prestataire_cree", f"#{new.id} {new.display}")
                self._close_dialog()
                self._toast("Prestataire créé.")
                self.show_prestataire_detail(new.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier le prestataire" if is_edit else "Nouveau prestataire"),
            content=ft.Container(
                ft.Column([nom, prenom, email, tel, adresse, notes, warn],
                          tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=420, height=440,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Import d'une facture (upload + extraction IA du montant) --------------
    async def _pick_and_import(self, prestataire: "repo.Prestataire") -> None:
        """Ouvre le sélecteur de fichier (API async Flet) puis le dialog d'import."""
        try:
            files = await self.file_picker.pick_files(
                allow_multiple=False, allowed_extensions=["pdf", "jpg", "jpeg", "png"])
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Sélecteur de fichier indisponible : {exc}", ok=False)
            return
        if not files:
            return  # annulé
        path = getattr(files[0], "path", None)
        if not path:
            self._toast("Fichier non accessible (sélection web non supportée).", ok=False)
            return
        self._import_facture_dialog(prestataire, str(path))

    def _import_facture_dialog(self, prestataire: "repo.Prestataire", src_path: str) -> None:
        src = Path(src_path)
        cfg = None
        ia_ok = False
        try:
            from src.ai.factory import provider_for_feature
            from src.config import load_config
            cfg = load_config()
            ia_ok = provider_for_feature(cfg, "facture_montant") is not None
        except Exception:  # noqa: BLE001
            ia_ok = False

        montant = ft.TextField(label="Montant total (TTC)", value="",
                               keyboard_type=ft.KeyboardType.NUMBER)
        ia_status = ft.Text("", size=12, color=MUTED)
        ech_row, ech = self._date_field("Échéance (optionnelle)", "")
        add_dep = ft.Checkbox(label="Ajouter une ligne de dépense", value=True)
        avance_type = ft.Dropdown(
            value="montant", width=150, color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key="montant", text="Montant"),
                     ft.dropdown.Option(key="pourcent", text="Pourcentage")])
        avance_val = ft.TextField(label="Part déjà payée (avance)", value="",
                                  keyboard_type=ft.KeyboardType.NUMBER)
        motif = ft.TextField(label="Motif (ex. Avance)", value="")
        status = ft.Text("", color=RED, size=12)

        def run_ia(e=None):
            if not ia_ok:
                return
            ia_status.value = "Lecture de la facture par IA…"
            ia_status.color = MUTED
            self.page.update()

            def work():
                from src.ai.features.facture_montant import extract_facture_montant
                val = extract_facture_montant(cfg, str(src))

                def apply():
                    if val is not None:
                        montant.value = f"{val:.2f}"
                        ia_status.value = "Montant lu par IA — vérifiez avant d'importer."
                        ia_status.color = GREEN
                    else:
                        ia_status.value = "IA : montant non trouvé, saisissez-le manuellement."
                        ia_status.color = AMBER
                    self.page.update()
                self._run_on_ui(apply)

            threading.Thread(target=work, daemon=True).start()

        def on_save(e):
            m = generator.parse_montant_str(montant.value)
            ech_iso, ech_ok = _fr_to_iso(ech.value)
            if not ech_ok:
                status.value = "Échéance invalide (format attendu : JJ/MM/AAAA)."
                self.page.update(); return
            if add_dep.value and (m is None or m <= 0):
                status.value = "Renseignez un montant total (> 0) pour créer la dépense."
                self.page.update(); return
            try:
                fac = generator.import_facture(
                    self.conn, prestataire, str(src), montant=m, libelle=src.name)
            except Exception as exc:  # noqa: BLE001
                status.value = f"Échec de l'import : {exc}"
                self.page.update(); return
            repo.log_audit(self.conn, "facture_importee",
                           f"#{fac.id} {src.name} (prestataire #{prestataire.id})")
            if add_dep.value and m and m > 0:
                paye = 0.0
                raw = generator.parse_montant_str(avance_val.value)
                if raw and raw > 0:
                    paye = round(m * raw / 100.0, 2) if (avance_type.value == "pourcent") else raw
                    paye = max(0.0, min(paye, m))
                dep = repo.create_depense(
                    self.conn, prestataire.id, m, montant_regle=paye,
                    motif=(motif.value or None), facture_id=fac.id, date_echeance=ech_iso)
                repo.log_audit(self.conn, "depense_creee",
                               f"#{dep.id} {m:.2f} (avance {paye:.2f}) prestataire #{prestataire.id}")
            self._close_dialog()
            self._toast("Facture importée.")
            self.show_prestataire_detail(prestataire.id)

        montant_row = (ft.Row([montant, self._btn("Relire (IA)", run_ia,
                                                   icon=ft.Icons.AUTO_AWESOME,
                                                   primary=False, busy=False)],
                              vertical_alignment=ft.CrossAxisAlignment.CENTER)
                       if ia_ok else montant)
        if not ia_ok:
            ia_status.value = "Extraction IA non configurée — saisie manuelle du montant."
            ia_status.color = MUTED

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Importer une facture — {prestataire.display}"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"Fichier : {src.name}", color=MUTED, size=12),
                    montant_row,
                    ia_status,
                    ech_row,
                    ft.Divider(),
                    add_dep,
                    ft.Row([avance_type, avance_val],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    motif,
                    status,
                ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=460, height=500),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Importer", on_save, icon=ft.Icons.UPLOAD_FILE, busy=False),
            ],
        )
        self._show_dialog(dlg)
        if ia_ok:
            run_ia()  # auto-extraction a l'ouverture (montant editable ensuite)

    def _depense_dialog(self, prestataire: "repo.Prestataire | None" = None) -> None:
        """Cree une depense manuellement, SANS facture (cas sans justificatif).

        Depuis une fiche prestataire (`prestataire` fourni, fixe) ou la vue
        Finances > Depenses (selecteur de prestataire). La depense est creee avec
        `facture_id=None` ; une facture reste rattachable plus tard via l'import.
        """
        prestataires = [] if prestataire else repo.list_prestataires(self.conn)
        if prestataire is None and not prestataires:
            self._toast("Aucun prestataire. Créez-en un d'abord.", ok=False)
            self.show_prestataires()
            return
        pr_dd = None
        if prestataire is None:
            pr_dd = ft.Dropdown(
                label="Prestataire *",
                color=TEXT, text_style=ft.TextStyle(color=TEXT),
                options=[ft.dropdown.Option(key=str(pp.id), text=pp.display)
                         for pp in prestataires],
                value=str(prestataires[0].id),
            )

        montant = ft.TextField(label="Montant total (TTC) *", value="",
                               keyboard_type=ft.KeyboardType.NUMBER, autofocus=True)
        libelle = ft.TextField(label="Libellé (ex. Loyer, Fournitures)", value="")
        ech_row, ech = self._date_field("Échéance (optionnelle)", "")
        avance_type = ft.Dropdown(
            value="montant", width=150, color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key="montant", text="Montant"),
                     ft.dropdown.Option(key="pourcent", text="Pourcentage")])
        avance_val = ft.TextField(label="Part déjà payée (avance)", value="",
                                  keyboard_type=ft.KeyboardType.NUMBER)
        status = ft.Text("", color=RED, size=12)

        def on_save(e=None):
            if prestataire is not None:
                pr = prestataire
            elif pr_dd and pr_dd.value:
                pr = repo.get_prestataire(self.conn, int(pr_dd.value))
            else:
                pr = None
            if pr is None:
                status.value = "Choisissez un prestataire."; self.page.update(); return
            m = generator.parse_montant_str(montant.value)
            if m is None or m <= 0:
                status.value = "Renseignez un montant total (> 0)."
                self.page.update(); return
            ech_iso, ech_ok = _fr_to_iso(ech.value)
            if not ech_ok:
                status.value = "Échéance invalide (format attendu : JJ/MM/AAAA)."
                self.page.update(); return
            paye = 0.0
            raw = generator.parse_montant_str(avance_val.value)
            if raw and raw > 0:
                paye = round(m * raw / 100.0, 2) if (avance_type.value == "pourcent") else raw
                paye = max(0.0, min(paye, m))
            lib = (libelle.value or "").strip() or None
            try:
                dep = repo.create_depense(
                    self.conn, pr.id, m, montant_regle=paye,
                    motif=lib, libelle=lib, facture_id=None, date_echeance=ech_iso)
            except Exception as exc:  # noqa: BLE001
                status.value = f"Échec : {exc}"; self.page.update(); return
            repo.log_audit(
                self.conn, "depense_creee",
                f"#{dep.id} {m:.2f} (sans facture, avance {paye:.2f}) prestataire #{pr.id}")
            self._close_dialog()
            self._toast("Dépense ajoutée.")
            if prestataire is not None:
                self.show_prestataire_detail(pr.id)
            else:
                self._refresh_depenses()

        fields: list[ft.Control] = []
        if pr_dd is not None:
            fields.append(pr_dd)
        fields += [
            montant, libelle, ech_row,
            ft.Text("Avance déjà réglée (optionnelle)", size=12, color=MUTED),
            ft.Row([avance_type, avance_val],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            status,
        ]
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nouvelle dépense" if prestataire is None
                          else f"Nouvelle dépense — {prestataire.display}"),
            content=ft.Container(
                ft.Column(fields, tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=440, height=430),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Ajouter la dépense", on_save, icon=ft.Icons.ADD, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Dialogues ------------------------------------------------------------
    def _patient_dialog(self, p: Patient | None = None) -> None:
        is_edit = p is not None
        nom = ft.TextField(label="Nom *", value=p.nom if p else "", autofocus=True)
        prenom = ft.TextField(label="Prénom *", value=p.prenom if p else "")
        email = ft.TextField(label="Email", value=(p.email if p else "") or "")
        tel = ft.TextField(label="Téléphone", value=(p.telephone if p else "") or "")
        ddn_row, ddn = self._date_field(
            "Date de naissance", (p.date_naissance if p else "") or "", editable=True)
        adresse = ft.TextField(label="Adresse", value=(p.adresse if p else "") or "", multiline=True, min_lines=1, max_lines=3)
        notes = ft.TextField(label="Notes", value=(p.notes if p else "") or "", multiline=True, min_lines=1, max_lines=3)
        warn = ft.Text("", color=NAVY, size=12)

        def on_save(e):
            if not nom.value.strip() or not prenom.value.strip():
                warn.value = "Nom et prénom sont obligatoires."
                self.page.update()
                return
            ddn_iso, ddn_ok = _fr_to_iso(ddn.value)
            if not ddn_ok:
                warn.value = "Date de naissance invalide (format attendu : JJ/MM/AAAA)."
                self.page.update()
                return
            # Detection de doublon a la creation
            if not is_edit:
                matches = repo.find_matches(self.conn, nom.value, prenom.value)
                if matches and not getattr(on_save, "_confirmed", False):
                    warn.value = (f"⚠ Un patient « {matches[0].display} » (#{matches[0].id}) existe déjà. "
                                  "Cliquez de nouveau sur Enregistrer pour créer quand même un doublon.")
                    on_save._confirmed = True
                    self.page.update()
                    return
            data = dict(
                nom=nom.value, prenom=prenom.value, email=email.value or None,
                telephone=tel.value or None, date_naissance=ddn_iso,
                adresse=adresse.value or None, notes=notes.value or None,
            )
            if is_edit:
                for k, v in data.items():
                    setattr(p, k, v)
                changed = repo.update_patient(self.conn, p)
                repo.log_audit(self.conn, "fiche_modifiee",
                               {"champs": changed}, patient_id=p.id)
                self._close_dialog()
                self._toast("Patient mis à jour.")
                self.show_patient_detail(p.id)
            else:
                new = repo.create_patient(self.conn, Patient(id=None, **data))
                repo.log_audit(self.conn, "fiche_creee",
                               {"display": new.display}, patient_id=new.id)
                self._close_dialog()
                self._toast("Patient créé.")
                self.show_patient_detail(new.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier le patient" if is_edit else "Nouveau patient"),
            content=ft.Container(
                ft.Column([nom, prenom, email, tel, ddn_row, adresse, notes, warn],
                          tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=420, height=460,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _resolve_fields(self, template: templates.Template) -> list[TemplateField]:
        """Variables a demander pour un template : config enregistree, sinon auto-detection.

        Exclut les balises auto-remplies depuis la fiche patient.
        """
        fields = repo.list_template_fields(self.conn, template.name)
        if fields:
            return [f for f in fields if f.tag.upper() not in generator.AUTO_PATIENT_TAGS]
        out: list[TemplateField] = []
        for tag in extract_placeholders(template.path):
            if tag in generator.AUTO_PATIENT_TAGS:
                continue
            out.append(TemplateField(template.name, tag, _humanize(tag), _guess_type(tag), ""))
        return out

    def _is_multiline_template(self, template: templates.Template) -> bool:
        """Vrai si le modèle est une « note multi-lignes » (≥ 1 balise de ligne <L_*>)."""
        try:
            _, line_tags = classify_placeholders(template.path)
        except Exception:  # noqa: BLE001
            return False
        return bool(line_tags)

    def _multiline_fields(self, p: Patient, saved_lignes: "list[dict] | None"):
        """Éditeur « note multi-lignes » : sélection des actes existants du patient
        (groupés, pré-cochés) + ajout de **nouveaux actes isolés** via le même
        formulaire que l'ajout d'acte (carte avec référentiel + odontogramme). Renvoie
        `(control, commit, recap)` ; `commit()` **crée** en base les nouveaux actes
        isolés (donc tracés dans la dette et visibles dans l'onglet Actes) et renvoie
        les lignes BRUTES retenues. Le total est recalculé en direct.

        `saved_lignes` (reprise d'un brouillon) restitue la (dé)sélection des actes ;
        None ⇒ création (tous les actes existants pré-cochés). Ordre déterministe :
        actes isolés, puis par plan, puis les nouveaux actes saisis.
        """
        has_saved = saved_lignes is not None
        saved = saved_lignes or []
        saved_acte_ids = {l.get("prestation_id") for l in saved if l.get("source") == "acte"}

        actes_ref = repo.list_actes(self.conn)  # référentiel pour pré-remplir les cartes
        isoles = repo.list_prestations(self.conn, p.id, plan_id=None)
        plans = repo.list_plans(self.conn, p.id)
        plan_groups = [(pl, repo.list_prestations(self.conn, p.id, plan_id=pl.id))
                       for pl in plans]

        acte_state: list = []  # [(checkbox, prestation)] dans l'ordre d'affichage
        cards: list = []       # handles _acte_card (nouveaux actes isolés à créer)
        cards_col = ft.Column([], tight=True, spacing=10)
        count_text = ft.Text("0 ligne(s) retenue(s)", color=MUTED, size=12)
        # Récapitulatif rempli via _money_summary (même carte que la fiche patient,
        # fond blanc) ; placé en bas du dialogue par _generate_dialog.
        recap_holder = ft.Container()

        def refresh_total():
            du = sum((pres.montant or 0) for cb, pres in acte_state if cb.value)
            regle = sum((pres.montant_regle or 0) for cb, pres in acte_state if cb.value)
            nb = sum(1 for cb, _ in acte_state if cb.value)
            for c in cards:
                if not c.blank():
                    du += c.montant()
                    nb += 1  # un nouvel acte = réglé 0
            reste = du - regle
            count_text.value = f"{nb} ligne(s) retenue(s)"
            recap_holder.content = self._money_summary([
                ("Total dû", du, TEXT),
                ("Réglé", regle, GREEN),
                ("Reste à payer", reste, AMBER),
            ])
            self.page.update()

        def acte_row(pres) -> ft.Control:
            checked = (pres.id in saved_acte_ids) if has_saved else True
            cb = ft.Checkbox(value=checked, on_change=lambda e: refresh_total())
            acte_state.append((cb, pres))
            bits = [b for b in [generator._ligne_date_fr(pres.date_acte), pres.libelle,
                                generator.format_montant(pres.montant or 0)] if b]
            label = "  ·  ".join(bits)
            if pres.reste and abs(pres.reste - (pres.montant or 0)) > 1e-9:
                label += f"  (reste {generator.format_montant(pres.reste)})"
            return ft.Row([cb, ft.Text(label, color=TEXT, expand=True)],
                          vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)

        groups: list[ft.Control] = []

        def add_group(title: str, pres_list: list):
            if not pres_list:
                return
            groups.append(ft.Text(f"{title} ({len(pres_list)})", color=NAVY,
                                  weight=ft.FontWeight.BOLD, size=12))
            for pres in pres_list:
                groups.append(acte_row(pres))

        add_group("Actes isolés", isoles)
        for pl, pres_list in plan_groups:
            add_group(pl.titre, pres_list)
        if not acte_state:
            groups.append(ft.Text("Aucun acte existant pour ce patient.",
                                  color=MUTED, size=12))

        # --- Nouveaux actes isolés (réutilise la carte d'ajout d'acte) -----------
        def remove_card(h):
            if h in cards:
                cards.remove(h)
                cards_col.controls = [c.control for c in cards]
                refresh_total()

        def add_card(e=None):
            h = self._acte_card(actes=actes_ref, on_change=refresh_total,
                                on_remove=remove_card, date_naissance=p.date_naissance)
            cards.append(h)
            cards_col.controls = [c.control for c in cards]
            self.page.update()
            refresh_total()

        def commit() -> list:
            """Crée les nouveaux actes isolés (plan_id=NULL) et renvoie les lignes
            brutes retenues (actes cochés + actes créés). Lève ValueError si une carte
            est invalide (AVANT toute création). Idempotent en cas de re-tentative :
            une carte déjà créée (pres_id) est mise à jour, pas dupliquée."""
            process = [c for c in cards if not c.blank()]
            data = [c.read() for c in process]  # valide tout d'abord (peut lever)
            lignes = [generator.prestation_to_ligne(pres)
                      for cb, pres in acte_state if cb.value]
            for c, d in zip(process, data):
                if getattr(c, "pres_id", None):  # déjà créé (re-tentative) : mise à jour
                    repo.update_prestation(
                        self.conn, c.pres_id, libelle=d["libelle"], montant=d["montant"],
                        plan_id=None, acte_id=d["acte_id"], date_acte=d["date_acte"],
                        dents=d["dents"], note=d["note"])
                    pres = repo.get_prestation(self.conn, c.pres_id)
                else:
                    pres = repo.create_prestation(
                        self.conn, p.id, d["libelle"], d["montant"], plan_id=None,
                        acte_id=d["acte_id"], date_acte=d["date_acte"],
                        dents=d["dents"], note=d["note"])
                    c.pres_id = pres.id
                    repo.log_audit(self.conn, "acte_cree",
                                   {"prestation_id": pres.id, "libelle": pres.libelle,
                                    "origine": "note_honoraires"}, patient_id=p.id)
                lignes.append(generator.prestation_to_ligne(pres))
            return lignes

        control = ft.Column([
            ft.Text("Actes à facturer", color=TEXT, weight=ft.FontWeight.BOLD),
            ft.Column(groups, tight=True, spacing=4),
            ft.Divider(height=8),
            ft.Row([ft.Text("Nouveaux actes", color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True), count_text],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text("Créés comme actes isolés (suivis dans la dette, visibles dans "
                    "l'onglet Actes).", color=MUTED, size=11),
            cards_col,
            ft.TextButton("+ Ajouter un acte", icon=ft.Icons.ADD, on_click=add_card),
        ], tight=True, spacing=8)
        refresh_total()
        return control, commit, recap_holder

    def _generate_dialog(self, p: Patient, draft: Document | None = None,
                         category: str | None = None) -> None:
        """Génère un document (brouillon → Word → JPG/PDF). Ne crée **plus aucun
        paiement** : le suivi du dû passe par les actes (plans-de-traitement D13).

        `category` non nul ⇒ mode « note d'honoraires » : seuls les modèles de cette
        catégorie sont proposés. Sinon (générique), les modèles de la catégorie des
        notes d'honoraires sont **exclus** (ils ont leur propre bouton). En édition
        d'un brouillon, tous les modèles restent listés."""
        is_note = category is not None
        note_cat = repo.get_setting(self.conn, NOTE_CAT_KEY) or NOTE_CAT_DEFAULT
        all_tpls = templates.list_templates()
        if draft is not None:
            tpls = all_tpls
        elif is_note:
            tpls = [t for t in all_tpls
                    if _cat_eq(repo.get_template_category(self.conn, t.name), category)]
        elif note_cat:
            tpls = [t for t in all_tpls
                    if not _cat_eq(repo.get_template_category(self.conn, t.name), note_cat)]
        else:
            tpls = all_tpls
        if not tpls:
            if is_note:
                self._toast(
                    f"Aucun modèle n'a la catégorie « {category} ». Dans Paramétrage › "
                    f"Modèles, cliquez l'icône « Catégorie » d'un modèle de note et "
                    f"saisissez exactement : {category}", ok=False)
            else:
                self._toast("Aucun modèle disponible. Créez-en un dans « Modèles ».",
                            ok=False)
            return
        # Edition d'un brouillon : pre-remplir depuis les saisies memorisees.
        draft_vars: dict[str, str] = {}
        if draft and draft.variables:
            try:
                draft_vars = json.loads(draft.variables)
            except (ValueError, TypeError):
                draft_vars = {}
        tpl_names = [t.name for t in tpls]
        init_tpl = (draft.template if (draft and draft.template in tpl_names)
                    else tpls[0].name)
        tpl_dd = ft.Dropdown(
            label="Modèle / type de document",
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key=t.name, text=t.label) for t in tpls],
            value=init_tpl,
        )
        fmt = ft.Dropdown(label="Format", value=(draft.output_format if draft else "jpg"),
                          color=TEXT, text_style=ft.TextStyle(color=TEXT),
                          options=[ft.dropdown.Option("jpg"), ft.dropdown.Option("pdf")])
        status = ft.Text("", color=RED, size=12)
        fields_col = ft.Column([], tight=True, spacing=10)
        # Récap multi-lignes : placé tout en bas du dialogue (rempli par build_fields).
        recap_col = ft.Column([], tight=True)
        getters: dict[str, callable] = {}
        ml_commit = None  # défini par build_fields si le modèle est multi-lignes

        def build_fields():
            getters.clear()
            nonlocal ml_commit
            ml_commit = None
            recap_col.controls = []
            controls = []
            tpl = templates.get_template(tpl_dd.value)
            # Modèle « note multi-lignes » (≥ 1 balise <L_*>) : éditeur d'actes
            # (sélection + ajout d'actes isolés), au lieu du formulaire mono-valeur
            # (3.1). La reprise d'un brouillon restitue la sélection depuis `__lignes__`.
            if tpl and self._is_multiline_template(tpl):
                saved = draft_vars.get(generator.LIGNES_KEY) if draft is not None else None
                ml_control, ml_commit, ml_recap = self._multiline_fields(
                    p, saved if isinstance(saved, list) else None)
                fields_col.controls = [ml_control]
                recap_col.controls = [ml_recap]
                self.page.update()
                return
            for f in (self._resolve_fields(tpl) if tpl else []):
                # En edition, la valeur memorisee du brouillon prime sur le defaut.
                init = draft_vars.get(f.tag, f.default_value or "")
                if f.type == "date":
                    row, field = self._date_field(f.label or f.tag, init)
                    controls.append(row)
                    getters[f.tag] = (lambda fld=field: fld.value)
                elif f.type == "paragraph":
                    tf = ft.TextField(
                        label=f.label or f.tag, value=init,
                        multiline=True, min_lines=3, max_lines=8,
                    )
                    controls.append(tf)
                    getters[f.tag] = (lambda c=tf: c.value)
                else:
                    tf = ft.TextField(
                        label=f.label or f.tag, value=init,
                        keyboard_type=ft.KeyboardType.NUMBER if f.type == "number" else None,
                    )
                    controls.append(tf)
                    getters[f.tag] = (lambda c=tf: c.value)
            if not controls:
                controls.append(ft.Text("Aucune variable à saisir pour ce modèle.",
                                        color=MUTED, size=12))
            fields_col.controls = controls
            self.page.update()

        def on_tpl_change(e):
            build_fields()

        tpl_dd.on_select = on_tpl_change

        is_edit = draft is not None

        def persist() -> Document:
            """Enregistre/maj le brouillon et renvoie le doc (AUCUN paiement créé).

            Etape rapide commune aux trois actions (brouillon / generer /
            generer+imprimer). Leve en cas d'echec ; l'appelant gere le statut.
            """
            tpl = templates.get_template(tpl_dd.value)
            if not tpl:
                raise ValueError("Modèle introuvable.")
            if ml_commit is not None:
                # Note multi-lignes : commit() crée les nouveaux actes isolés (tracés
                # dans la dette) et renvoie les lignes brutes retenues, sérialisées
                # sous la clé réservée `__lignes__` (totaux/formats recalculés au rendu).
                variables = {generator.LIGNES_KEY: ml_commit()}
            else:
                variables = {tag: (get() or "") for tag, get in getters.items()}
            if draft is not None:
                generator.update_draft(
                    self.conn, draft, variables=variables, output_format=fmt.value)
                repo.log_audit(self.conn, "brouillon_modifie",
                               {"document_id": draft.id, "modele": tpl.name},
                               patient_id=p.id)
                return draft
            doc = generator.save_draft(
                self.conn, p, tpl, variables=variables, output_format=fmt.value)
            repo.log_audit(self.conn, "brouillon_cree",
                           {"document_id": doc.id, "modele": tpl.name}, patient_id=p.id)
            return doc

        def on_save_draft(e=None):
            """Action secondaire : enregistre le brouillon SANS generer (rapide)."""
            try:
                persist()
            except Exception as exc:  # noqa: BLE001
                status.value = f"Échec : {exc}"; status.color = RED
                self.page.update(); return
            self._close_dialog()
            self._toast("Brouillon mis à jour." if is_edit else "Brouillon enregistré.")
            self.show_patient_detail(p.id)

        def on_generate(button: ft.Control, do_print: bool):
            """Genere le document a la volee (Word), puis l'imprime si demande.

            La generation lance Word (lent) : travail en arriere-plan via
            `_run_busy` (spinner + anti double-clic), comme l'envoi email.
            """
            printer = None
            if do_print:  # verifier l'imprimante AVANT de lancer le travail
                printer = repo.get_setting(self.conn, PRINTER_KEY)
                if not printer:
                    status.value = ("Aucune imprimante configurée "
                                    "(Paramétrage › Imprimante).")
                    status.color = RED; self.page.update(); return
                try:
                    available = printing.list_printers()
                except Exception:  # noqa: BLE001
                    available = []
                if available and printer not in available:
                    status.value = (f"Imprimante « {printer} » indisponible "
                                    "(Paramétrage › Imprimante).")
                    status.color = RED; self.page.update(); return

            def work():
                doc = persist()
                generator.render_document(self.conn, doc)
                repo.log_audit(
                    self.conn,
                    "note_honoraires_generee" if is_note else "document_genere",
                    {"document_id": doc.id, "type": doc.type, "modele": doc.template},
                    patient_id=p.id)
                if do_print:
                    cfg = print_settings.get_settings_for(self.conn, doc.type)
                    paper, color = cfg["paper"], cfg["color"]
                    printing.print_file(Path(doc.file_path or ""), printer,
                                        paper=paper, color=color)
                    repo.log_audit(self.conn, "document_imprime",
                                   {"document_id": doc.id, "type": doc.type,
                                    "imprimante": printer}, patient_id=p.id)
                self._close_dialog()
                self._toast(f"Document généré et envoyé à « {printer} »." if do_print
                            else "Document généré.")
                self.show_patient_detail(p.id)

            self._run_busy(button, status, work)

        build_fields()
        body_controls = [tpl_dd, fields_col, fmt, status, recap_col]

        # Brouillon = action secondaire ; Générer (et imprimer) = actions primaires.
        # Les boutons de generation pilotent eux-memes `_run_busy` (busy=False ici)
        # et capturent leur propre bouton (robuste au Ctrl+Entree ou e est None).
        # Raccourcis : Générer = Ctrl+Entrée ; Générer et imprimer = Ctrl+P ;
        # Enregistrer (brouillon) = Ctrl+S (cf. shortcuts du dialogue ci-dessous).
        draft_label = "Enregistrer" if is_edit else "Enregistrer en brouillon"
        btn_draft = self._btn(draft_label, on_save_draft, primary=False, busy=False)
        btn_draft.tooltip = f"{draft_label} ({SC_SAVE})"
        btn_gen = self._btn("Générer", None,
                            icon=ft.Icons.PLAY_CIRCLE_OUTLINE, busy=False)
        btn_gen.tooltip = f"Générer ({SC_SUBMIT})"
        btn_print = self._btn("Générer et imprimer", None,
                              icon=ft.Icons.PRINT, busy=False)
        btn_print.tooltip = f"Générer et imprimer ({SC_PRINT})"
        btn_gen.on_click = lambda e=None: on_generate(btn_gen, False)
        btn_print.on_click = lambda e=None: on_generate(btn_print, True)

        if is_edit:
            dlg_title = f"Modifier le brouillon — {p.display}"
        elif is_note:
            dlg_title = f"Note d'honoraires — {p.display}"
        else:
            dlg_title = f"Nouveau document — {p.display}"
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(dlg_title),
            content=ft.Container(
                ft.Column(body_controls, tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                width=460, height=480,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                btn_draft, btn_gen, btn_print,
            ],
        )
        # Ctrl+Entrée (et Entrée depuis un champ) -> Générer ; Ctrl+P -> Générer et
        # imprimer ; Ctrl+S -> Enregistrer en brouillon.
        self._show_dialog(
            dlg, submit=lambda e=None: on_generate(btn_gen, False),
            shortcuts={"P": lambda e=None: on_generate(btn_print, True),
                       "S": on_save_draft})

    def _note_dialog(self, p: Patient) -> None:
        """Bouton dédié « Note d'honoraires » : génère depuis les modèles de la
        catégorie configurée (Paramétrage › Modèles), sans aucun paiement."""
        cat = repo.get_setting(self.conn, NOTE_CAT_KEY) or NOTE_CAT_DEFAULT
        self._generate_dialog(p, category=cat)

    def _note_category_selector(self) -> ft.Control:
        """Carte de Paramétrage › Modèles : choisit la catégorie dédiée aux notes
        d'honoraires (mémorisée dans `meta`, clé `NOTE_CAT_KEY`)."""
        cats = repo.list_categories(self.conn)
        current = repo.get_setting(self.conn, NOTE_CAT_KEY) or ""
        # Catégorie effective = réglage si défini, sinon la convention par défaut.
        # On présélectionne la catégorie existante qui lui correspond (tolérant).
        effective = current or NOTE_CAT_DEFAULT
        match = next((c.nom for c in cats if _cat_eq(c.nom, effective)), "")
        dd = ft.Dropdown(
            label="Notes d'honoraires", width=320,
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            value=match,
            options=[ft.dropdown.Option(key="", text=f"— Défaut (« {NOTE_CAT_DEFAULT} ») —")]
            + [ft.dropdown.Option(key=c.nom, text=c.nom) for c in cats],
            on_select=lambda e: self._set_note_category(e.control.value),
        )
        hint = (f"Par défaut « {NOTE_CAT_DEFAULT} ». Les modèles de cette catégorie "
                "alimentent le bouton « Note d'honoraires » de la fiche patient ; la "
                "génération générique les exclut.") if cats else (
            f"Rangez vos modèles de note dans une catégorie « {NOTE_CAT_DEFAULT} » "
            "(icône Catégorie d'un modèle) : ils alimenteront le bouton "
            "« Note d'honoraires ».")
        return self._card(ft.Row([
            ft.Icon(ft.Icons.RECEIPT_LONG, color=NAVY),
            dd,
            ft.Text(hint, size=12, color=MUTED, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12))

    def _set_note_category(self, value: str) -> None:
        repo.set_setting(self.conn, NOTE_CAT_KEY, value or "")
        self._toast(f"Notes d'honoraires : catégorie « {value} »." if value
                    else f"Notes d'honoraires : catégorie par défaut « {NOTE_CAT_DEFAULT} ».")

    def _paiement_dialog(self, p: Patient) -> None:
        montant = ft.TextField(label="Montant", value="0", autofocus=True)
        echeance_row, echeance = self._date_field("Échéance", "")
        notes = ft.TextField(label="Libellé", value="")
        status = ft.Text("", color=RED, size=12)

        def on_add(e):
            try:
                montant_val = float((montant.value or "0").replace(",", "."))
            except ValueError:
                status.value = "Montant invalide."; self.page.update(); return
            if montant_val <= 0:
                status.value = "Le montant doit être strictement supérieur à 0."
                self.page.update(); return
            ech_iso, ech_ok = _fr_to_iso(echeance.value)
            if not ech_ok:
                status.value = "Échéance invalide (format attendu : JJ/MM/AAAA)."
                self.page.update(); return
            repo.create_paiement(self.conn, Paiement(
                id=None, patient_id=p.id, montant=montant_val, statut="en_attente",
                date_echeance=ech_iso, notes=notes.value or None,
            ))
            self._close_dialog()
            self._toast("Paiement ajouté.")
            self.show_patient_detail(p.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nouveau paiement"),
            content=ft.Container(ft.Column([montant, echeance_row, notes, status], tight=True, spacing=10), width=380),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Ajouter", on_add, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Categorie de modele : champ libre + suggestions ----------------------
    def _cat_color(self, nom: str | None) -> str:
        """Couleur d'une categorie (depuis `categories`), ou gris si aucune/inconnue."""
        if not nom:
            return MUTED
        c = repo.get_category(self.conn, nom)
        return c.couleur if (c and c.couleur) else NAVY

    def _cat_pastille(self, nom: str | None, count: int | None = None) -> ft.Control:
        """En-tete visuel d'une categorie : pastille couleur + icone + nom (+ compteur)."""
        col = self._cat_color(nom)
        label = nom or "Sans catégorie"
        children = [
            ft.Icon(ft.Icons.FOLDER if nom else ft.Icons.FOLDER_OPEN, color=col, size=18),
            ft.Text(label, weight=ft.FontWeight.BOLD, color=TEXT),
        ]
        if count is not None:
            children.append(ft.Container(
                ft.Text(str(count), size=11, color=col),
                bgcolor=ft.Colors.with_opacity(0.14, col),
                padding=ft.Padding.symmetric(vertical=2, horizontal=8),
                border_radius=20,
            ))
        return ft.Row(children, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _category_input(self, current: str | None = None) -> tuple[ft.Control, ft.TextField]:
        """Champ catégorie : texte libre + suggestions cliquables (catégories connues).

        Renvoie (contrôle à insérer dans le dialogue, TextField dont `.value` porte
        la saisie). La valeur reste arbitraire ; cliquer une suggestion la remplit.
        """
        tf = ft.TextField(label="Catégorie (facultatif)", value=current or "",
                          hint_text="ex. Radiologie, Ordonnances")
        cats = repo.list_categories(self.conn)
        body: list[ft.Control] = [tf]
        if cats:
            chips: list[ft.Control] = []
            for c in cats:
                col = c.couleur or NAVY

                def pick(e, name=c.nom):
                    tf.value = name
                    self.page.update()

                chips.append(ft.Container(
                    ft.Text(c.nom, size=12, color=col),
                    bgcolor=ft.Colors.with_opacity(0.12, col),
                    padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                    border_radius=20, ink=True, on_click=pick,
                ))
            body.append(ft.Text("Suggestions :", size=11, color=MUTED))
            body.append(ft.Row(chips, wrap=True, spacing=6, run_spacing=6))
        return ft.Column(body, tight=True, spacing=6), tf

    def _new_template_dialog(self) -> None:
        name = ft.TextField(label="Nom du modèle (ex. devis, recu)", autofocus=True)
        cat_ctrl, cat_tf = self._category_input()
        status = ft.Text("", color=RED, size=12)

        def on_create(e):
            try:
                t = templates.create_template(name.value or "")
            except Exception as exc:  # noqa: BLE001
                status.value = str(exc); self.page.update(); return
            # Categorie (facultative) portee par le modele, pas par le .docx.
            repo.set_template_category(self.conn, t.name, cat_tf.value)
            self._close_dialog()
            self._toast("Modèle créé. Ouverture dans Word…")
            templates.open_in_word(t)
            self.show_templates()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Nouveau modèle"),
            content=ft.Container(ft.Column([name, cat_ctrl, status], tight=True, spacing=10), width=360),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Créer et ouvrir", on_create, busy=False),
            ],
        )
        self._show_dialog(dlg)

    # --- Actions --------------------------------------------------------------
    def _edit_template(self, t: templates.Template) -> None:
        try:
            templates.open_in_word(t)
            self._toast(f"Ouverture de « {t.label} » dans Word…")
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Impossible d'ouvrir : {exc}", ok=False)

    def _rename_template_dialog(self, t: templates.Template) -> None:
        name = ft.TextField(label="Nouveau nom du modèle", value=t.name, autofocus=True)
        current_cat = repo.get_template_category(self.conn, t.name)
        cat_ctrl, cat_tf = self._category_input(current_cat)
        status = ft.Text("", color=RED, size=12)

        def on_rename(e):
            new_name = (name.value or "").strip()
            if not new_name:
                status.value = "Le nom ne peut pas être vide."; self.page.update(); return
            try:
                # Ne renomme le .docx QUE si le nom a reellement change : sinon
                # `_safe_name` re-normaliserait un nom deja non canonique (espace,
                # accent) et renommerait le fichier a tort en cassant les documents
                # et la categorie qui le referencent par son nom actuel.
                new_t = templates.rename_template(t, new_name) if new_name != t.name else t
            except Exception as exc:  # noqa: BLE001
                status.value = str(exc); self.page.update(); return
            # Reporte la categorie de l'ancien nom (anti-orphelin) puis applique la
            # valeur eventuellement editee dans le champ.
            repo.rename_template_meta(self.conn, t.name, new_t.name)
            repo.set_template_category(self.conn, new_t.name, cat_tf.value)
            self._close_dialog()
            self._toast("Modèle renommé.")
            self.show_templates()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Renommer « {t.label} »"),
            content=ft.Container(ft.Column([name, cat_ctrl, status], tight=True, spacing=10), width=360),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Renommer", on_rename, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _set_template_category_dialog(self, t: templates.Template) -> None:
        """Assigne/retire la catégorie d'un modèle SANS le renommer.

        Cle = nom de fichier exact du modele (`t.name`), pour que la generation
        (`get_template_category`) et le regroupement la retrouvent. Champ vide =
        modele sans categorie.
        """
        current = repo.get_template_category(self.conn, t.name)
        cat_ctrl, cat_tf = self._category_input(current)
        status = ft.Text("", color=RED, size=12)

        def on_save(e):
            repo.set_template_category(self.conn, t.name, cat_tf.value)
            self._close_dialog()
            self._toast("Catégorie mise à jour.")
            self.show_templates()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Catégorie de « {t.label} »"),
            content=ft.Container(ft.Column(
                [ft.Text("Range les documents générés dans un sous-dossier dédié et "
                         "regroupe modèles et documents. Laisser vide = sans catégorie.",
                         size=12, color=MUTED),
                 cat_ctrl, status],
                tight=True, spacing=10), width=360),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Enregistrer", on_save, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _rename_category_dialog(self) -> None:
        """Renomme une catégorie partout (modèles, et en option documents générés)."""
        cats = repo.list_categories(self.conn)
        if not cats:
            self._toast("Aucune catégorie à renommer.", ok=False)
            return
        # Pas d'expand=True ici : dans une Column verticale, expand etire le Dropdown
        # EN HAUTEUR et gonfle le dialogue. La largeur est geree par STRETCH (cf. content).
        old_dd = ft.Dropdown(
            label="Catégorie à renommer", value=cats[0].nom,
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(c.nom) for c in cats])
        new_tf = ft.TextField(label="Nouveau nom", autofocus=True)
        # Label court (les libellés de Checkbox Flet ne se replient pas et débordent) ;
        # l'explication va dans une ligne grise qui, elle, se replie dans la largeur.
        reclass = ft.Checkbox(label="Reclasser les documents existants", value=False)
        reclass_hint = ft.Text(
            "Déplace aussi les fichiers déjà générés vers le nouveau sous-dossier.",
            size=11, color=MUTED)
        status = ft.Text("", color=RED, size=12)

        def on_rename(e=None):
            old = old_dd.value or ""
            new = (new_tf.value or "").strip()
            if not new:
                status.value = "Le nouveau nom ne peut pas être vide."
                self.page.update(); return

            def work():
                reclasses = repo.rename_category(
                    self.conn, old, new, reclasser_documents=reclass.value)
                moved = 0
                if reclass.value and reclasses:
                    moved = generator.move_documents_to_category(self.conn, reclasses, new)
                repo.log_audit(
                    self.conn, "categorie_renommee",
                    f"{old} -> {new} (reclasser={reclass.value}, {moved} fichier(s))")
                self._close_dialog()
                msg = f"Catégorie « {old} » renommée en « {new} »."
                if reclass.value:
                    msg += f" {moved} fichier(s) déplacé(s)."
                self._toast(msg)
                self.show_templates()

            self._run_busy(rename_btn, None, work)

        rename_btn = self._btn("Renommer", on_rename, busy=False)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Renommer une catégorie"),
            content=ft.Container(ft.Column(
                [old_dd, new_tf,
                 ft.Column([reclass, reclass_hint], tight=True, spacing=2),
                 status],
                tight=True, spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH), width=380),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                rename_btn,
            ],
        )
        self._show_dialog(dlg)

    def _delete_template_dialog(self, t: templates.Template) -> None:
        def on_delete(e):
            try:
                templates.delete_template(t)
            except Exception as exc:  # noqa: BLE001
                self._close_dialog()
                self._toast(f"Suppression impossible : {exc}", ok=False)
                return
            self._close_dialog()
            self._toast("Modèle supprimé.")
            self.show_templates()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer le modèle"),
            content=ft.Text(f"Supprimer définitivement le modèle « {t.label} » ? "
                            "Le fichier Word sera effacé."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Supprimer", on_delete, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _open_file(self, d: Document) -> None:
        import os
        path = d.file_path or ""
        if path and Path(path).exists():
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                self._toast(f"Ouverture impossible : {exc}", ok=False)
        else:
            self._toast("Fichier introuvable.", ok=False)

    def _print_file(self, e: ft.ControlEvent, d: Document) -> None:
        """Imprime un document genere sur l'imprimante configuree (Parametrage).

        L'impression part de la machine ou tourne l'application (cote serveur en
        mode web), vers l'imprimante reseau choisie une fois pour toutes.
        """
        path = d.file_path or ""
        if not (path and Path(path).exists()):
            self._toast("Fichier introuvable.", ok=False)
            return
        printer = repo.get_setting(self.conn, PRINTER_KEY)
        if not printer:
            self._toast("Aucune imprimante configurée. Choisissez-en une dans "
                        "Paramétrage › Imprimante.", ok=False)
            self.show_parametrage("printer")
            return
        try:
            available = printing.list_printers()
        except Exception:  # noqa: BLE001
            available = []
        if available and printer not in available:
            self._toast(f"L'imprimante « {printer} » n'est plus disponible. "
                        "Choisissez-en une autre dans Paramétrage › Imprimante.", ok=False)
            self.show_parametrage("printer")
            return

        cfg = print_settings.get_settings_for(self.conn, d.type)
        paper, color = cfg["paper"], cfg["color"]

        def work():
            printing.print_file(Path(path), printer, paper=paper, color=color)
            repo.log_audit(self.conn, "document_imprime",
                           {"document_id": d.id, "type": d.type, "imprimante": printer},
                           patient_id=d.patient_id)
            self._toast(f"Envoyé à l'imprimante « {printer} ».")

        self._run_busy(e.control, None, work)

    def _send_dialog(self, d: Document) -> None:
        mtemplates = repo.list_mail_templates(self.conn)
        if not mtemplates:
            self._toast("Aucun modèle d'email. Ajoutez-en un dans l'onglet « Emails ».", ok=False)
            self.show_mail_templates()
            return

        default = repo.get_default_mail_template(self.conn)
        tpl_dd = ft.Dropdown(
            label="Modèle d'email",
            color=TEXT, text_style=ft.TextStyle(color=TEXT),
            options=[ft.dropdown.Option(key=str(t.id), text=f"{t.name}  (#{t.mailjet_template_id})")
                     for t in mtemplates],
            value=str(default.id) if default else str(mtemplates[0].id),
        )
        status = ft.Text("", color=RED, size=12)
        by_id = {str(t.id): t for t in mtemplates}

        def on_send(e):
            chosen = by_id.get(tpl_dd.value)
            if not chosen:
                status.value = "Choisissez un modèle."; self.page.update(); return
            try:
                from src.config import load_config
                config = load_config()
            except Exception as exc:  # noqa: BLE001
                status.value = f"config.ini invalide : {exc}"; self.page.update(); return

            def work():
                generator.send_document(
                    self.conn, d, config, template_id=chosen.mailjet_template_id
                )
                repo.log_audit(self.conn, "document_envoye",
                               {"document_id": d.id, "type": d.type, "email": d.email},
                               patient_id=d.patient_id)
                self._close_dialog()
                self._toast("Email envoyé.")
                self._after_doc_change()

            self._run_busy(e.control, status, work)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Envoyer par email"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"Destinataire : {d.email}", color=MUTED, size=13),
                    tpl_dd, status,
                ], tight=True, spacing=12),
                width=400,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Envoyer", on_send, icon=ft.Icons.SEND, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _encaisser(self, pa: Paiement, back_to_paiements: bool = False) -> None:
        """Ouvre un dialog pour saisir le mode de reglement, puis encaisse."""
        mode = ft.RadioGroup(
            value=pa.mode or "especes",
            content=ft.Column(
                [ft.Radio(value=k, label=v) for k, v in _MODE_LABELS.items()],
                tight=True, spacing=2,
            ),
        )
        warn = ft.Text("", color=RED, size=12)

        def confirm(e):
            if not mode.value:
                warn.value = "Sélectionnez un mode de paiement."
                self.page.update()
                return
            repo.mark_paiement_encaisse(self.conn, pa.id, mode=mode.value)
            repo.log_audit(
                self.conn, "paiement_encaisse",
                {"paiement_id": pa.id, "montant": pa.montant, "mode": mode.value,
                 "libelle": pa.notes}, patient_id=pa.patient_id)
            self._close_dialog()
            self._toast("Paiement encaissé.")
            if back_to_paiements:
                self.show_paiements()
            elif self.current_patient:
                self.show_patient_detail(self.current_patient.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Encaisser le paiement"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"Montant : {pa.montant:.2f}", color=MUTED),
                    ft.Text("Mode de règlement", weight=ft.FontWeight.BOLD, color=TEXT),
                    mode, warn,
                ], tight=True, spacing=10),
                width=320,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close_dialog()),
                self._btn("Encaisser", confirm, icon=ft.Icons.CHECK_CIRCLE, busy=False),
            ],
        )
        self._show_dialog(dlg)

    def _annuler_paiement(self, pa: Paiement, back_to_paiements: bool = False) -> None:
        """Confirme puis supprime un paiement en attente (annulation)."""
        def confirm(e):
            repo.delete_paiement(self.conn, pa.id)
            repo.log_audit(
                self.conn, "paiement_annule",
                {"paiement_id": pa.id, "montant": pa.montant, "libelle": pa.notes},
                patient_id=pa.patient_id)
            self._close_dialog()
            self._toast("Paiement annulé.")
            if back_to_paiements:
                self.show_paiements()
            elif self.current_patient:
                self.show_patient_detail(self.current_patient.id)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Annuler le paiement"),
            content=ft.Text(
                f"Annuler définitivement ce paiement en attente de "
                f"{pa.montant:.2f} ({pa.notes or 'Paiement'}) ?"),
            actions=[
                ft.TextButton("Retour", on_click=lambda e: self._close_dialog()),
                self._btn("Annuler le paiement", confirm,
                          icon=ft.Icons.CANCEL, busy=False),
            ],
        )
        self._show_dialog(dlg)


# --- Helpers de presentation --------------------------------------------------

def _initials(p: Patient) -> str:
    a = (p.prenom[:1] or "").upper()
    b = (p.nom[:1] or "").upper()
    return (b + a) or "?"


def _doc_label(d: Document) -> str:
    base = d.type.replace("_", " ").capitalize()
    if d.montant:
        return f"{base} — {d.montant:.2f}"
    return base


def _kv(key: str, value: str) -> ft.Control:
    return ft.Row([
        ft.Text(key, color=MUTED, width=150),
        ft.Text(value, color=TEXT, expand=True, selectable=True),
    ])


def _humanize(tag: str) -> str:
    return tag.replace("_", " ").strip().capitalize()


def _audit_val(v) -> str:
    """Valeur avant/apres pour l'historique : « — » si vide/absente, sinon texte."""
    return "—" if v is None or v == "" else str(v)


def _audit_montant(v) -> str:
    """Montant formate (2 decimales) pour l'historique, tolerant si non numerique."""
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return _audit_val(v)


def _guess_type(tag: str) -> str:
    t = tag.upper()
    if "DATE" in t:
        return "date"
    if any(k in t for k in ("MONTANT", "PRIX", "TARIF")):
        return "number"
    return "text"


def _asset(name: str) -> str:
    """Chemin absolu d'un fichier ressource (logo, etc.).

    En mode gele (PyInstaller), les ressources embarquees sont extraites dans
    sys._MEIPASS ; en dev, elles sont a la racine du projet.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return str(base / name)


# --- Point d'entree -----------------------------------------------------------

def _show_db_too_new(page: ft.Page, err: SchemaTooNewError) -> None:
    """Ecran bloquant : la base vient d'une version plus recente que cet exe.

    On refuse d'ouvrir (et donc d'ecrire avec un schema plus ancien) pour ne pas
    risquer de perdre des donnees. L'utilisateur doit installer la derniere
    version de l'application.
    """
    page.add(
        ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            padding=40,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=AMBER, size=64),
                    ft.Text(
                        "Base de données plus récente que l'application",
                        size=22, weight=ft.FontWeight.BOLD, color=TEXT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"La base a été créée ou mise à jour par une version plus "
                        f"récente (schéma v{err.disk_version}) que cette application "
                        f"(schéma v{err.app_version}).\n\n"
                        "Pour éviter toute perte de données, l'ouverture est bloquée. "
                        "Veuillez installer la dernière version de l'application.",
                        size=15, color=MUTED, text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )
    )
    page.update()


def main(page: ft.Page) -> None:
    page.title = f"Cabinet Dr Aslem Gouiaa — {version.app_version_full()}"
    page.bgcolor = BG
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed=NAVY, font_family="Segoe UI")
    # L'app est entierement concue en clair (cartes/fonds blancs explicites).
    # On force le mode clair pour que les modales, leurs champs et leurs
    # dropdowns ne basculent pas en sombre quand Windows est en theme sombre.
    page.theme_mode = ft.ThemeMode.LIGHT
    # Taille de repli si l'utilisateur restaure la fenetre (bouton "Restaurer").
    page.window.width = 1100
    page.window.height = 760
    # Demarrage agrandi au maximum, en gardant la barre de titre Windows
    # (boutons reduire / restaurer / fermer visibles).
    page.window.maximized = True
    page.window.icon = _asset("logo.ico")  # icone de la fenetre (barre des taches)

    # Sauvegarde horodatee AVANT toute migration (best-effort) : connect() peut
    # migrer la base, donc on capture l'etat d'avant. connect() ajoute en plus
    # une copie etiquetee non purgee dans backups/pre-migration/ si le schema
    # change, et refuse d'ouvrir une base plus recente que cet exe (anti-downgrade).
    backup.backup_db()
    try:
        conn = connect()
    except SchemaTooNewError as e:
        _show_db_too_new(page, e)
        return

    # Un job 'en_cours' ne survit pas a une fermeture : le marquer interrompu
    # (a faire AVANT tout lancement de job dans cette session).
    repo.mark_stale_jobs_interrupted(conn)
    repo.log_audit(conn, "demarrage", "Ouverture de l'application")

    # Amorce : reprend le template Mailjet de config.ini comme modele par defaut.
    if not repo.list_mail_templates(conn):
        try:
            from src.config import load_config

            tid = load_config().mail.template_id
            if tid:
                repo.create_mail_template(conn, repo.MailTemplate(
                    id=None, name="Par défaut", mailjet_template_id=tid, is_default=True))
        except Exception:  # noqa: BLE001
            pass

    CrmApp(page, conn)


def run() -> None:
    """Lance l'app.

    Par defaut : fenetre desktop native. Pour servir l'app en web (accessible
    depuis Chrome), definir CRM_WEB=1 (et au besoin CRM_PORT / CRM_HOST) :

        CRM_WEB=1 python -m crm          # http://localhost:8550
        CRM_WEB=1 CRM_PORT=9000 ...      # port choisi
        CRM_WEB=1 CRM_HOST=0.0.0.0 ...   # accessible depuis le reseau (LAN)
    """
    import os

    if os.environ.get("CRM_WEB") in ("1", "true", "True"):
        ft.run(
            main,
            view=ft.AppView.WEB_BROWSER,
            host=os.environ.get("CRM_HOST"),
            port=int(os.environ.get("CRM_PORT", "8550")),
        )
    else:
        ft.run(main)


if __name__ == "__main__":
    run()
