"""Fonctionnalite 1 : extraire le MONTANT d'une facture fournisseur scannee (vision).

Les factures sont des scans (JPG/PNG ou PDF image) : cette fonctionnalite est vision-only.
Point d'entree unique cote app : `extract_facture_montant(cfg, src_path)`. Ne leve jamais —
renvoie None en repli (IA off / format inconnu / echec) ; le montant pre-remplit un champ
editable, jamais auto-valide.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config import Config, app_dir

from ..base import AIError
from ..factory import provider_for_feature
from ..images import as_image_parts
from ..log import log_ai

FEATURE = "facture_montant"


def normalize_amount(raw) -> "float | None":
    """Convertit un montant ECRIT (FR/EU/US) en float, de façon déterministe.

    On ne fait JAMAIS confiance à l'arithmétique du modèle (il se trompe, p.ex.
    « 1 201,0000 » lu 1201000) : il recopie le montant tel quel et on normalise ici.

    Règles : on retire les séparateurs de milliers « espace » (normal/insécable/fin) ;
    si virgule ET point sont présents, le séparateur le plus à droite est le décimal ;
    une virgule seule est un décimal (usage FR). Renvoie None si non analysable.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r"[^\d.,\s\-]", "", s)   # vire devise / lettres / symboles
    s = re.sub(r"\s", "", s)            # milliers = espace (incl. insécable  / )
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.234,56 -> 1234.56
        else:
            s = s.replace(",", "")                     # 1,234.56 -> 1234.56
    elif "," in s:
        s = s.replace(",", ".")                        # 1201,0000 -> 1201.0000
    try:
        return float(s)
    except ValueError:
        return None


def extract_facture_montant(cfg: Config, src_path) -> "float | None":
    """Montant TTC lu sur le scan, ou None (IA off / format inconnu / echec). Ne leve jamais."""
    name = Path(src_path).name
    provider = provider_for_feature(cfg, FEATURE)
    if provider is None or not provider.supports_vision:   # cette feature exige la vision
        feat = cfg.ai.feature(FEATURE)
        if feat is None or not feat.enabled:
            reason = "fonctionnalite absente ou desactivee (config.ini)"
        elif provider is None:
            reason = "provider introuvable ou cle d'API vide (config.ini)"
        else:
            reason = f"provider '{provider.name}' ne supporte pas la vision"
        log_ai("FACTURE_MONTANT_SKIP", file=name, reason=reason)
        return None
    feat = cfg.ai.feature(FEATURE)
    log_ai("FACTURE_MONTANT_START", file=name, provider=provider.name)
    try:
        system = (app_dir() / feat.prompt_path).read_text(encoding="utf-8")
        images = as_image_parts(Path(src_path))            # JPG/PNG direct, PDF -> rasterise
        data = provider.complete_json(
            system=system,
            user="Facture scannee en piece jointe.",
            images=images,
            max_tokens=256,
        )
        # Le modèle recopie le montant tel qu'imprimé (montant_texte) ; on normalise
        # nous-mêmes. Repli sur `montant` (ancien format) si besoin.
        raw = data.get("montant_texte")
        if raw is None:
            raw = data.get("montant")
        montant = normalize_amount(raw)
        log_ai("FACTURE_MONTANT_RESULT", file=name, raw=raw, montant=montant,
               devise=data.get("devise"), confiance=data.get("confiance"))
        return montant
    except (AIError, OSError) as exc:
        log_ai("FACTURE_MONTANT_ERROR", file=name, error=str(exc))
        return None
