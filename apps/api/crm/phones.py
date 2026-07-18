"""Normalisation des numéros de téléphone au format international E.164.

Module partagé par :
- `crm/rappels.py`        (construction des liens wa.me pour les rappels)
- `crm/generator.py`      (envoi WhatsApp Meta Cloud API des documents)

Les deux consommateurs historiques avaient chacun leur implémentation, avec des
règles subtilement divergentes (longueur minimale, gestion du `+`, indicatif par
défaut). Ce module unifie la logique pour qu'un même numéro soit accepté et
normalisé identiquement partout.

API publique :
  normalize_phone(phone, country_code)  → str au format E.164 (ex. +21612345678)
  build_whatsapp_link(phone, message, country_code) → URL wa.me
  DEFAULT_COUNTRY_CODE                   → "+216" (Tunisie)
"""

from __future__ import annotations

import re
import urllib.parse

# Indicatif pays par défaut (Tunisie). Paramétrable via `meta.default_country`
# (envoi documents WhatsApp) ou `meta.rappels_default_country` (rappels).
DEFAULT_COUNTRY_CODE = "+216"

# Bornes de longueur du numéro normalisé (chiffres uniquement, hors le `+`).
# 6 chiffres :某些 numéros locaux courts légitimes (ex. certains services).
# 15 chiffres : maximum ITU-T E.164.
_MIN_DIGITS = 6
_MAX_DIGITS = 15


def _digits_only(s: str) -> str:
    """Renvoie les chiffres de `s` (supprime tout le reste)."""
    return re.sub(r"\D", "", s)


def normalize_phone(phone: str, country_code: str = DEFAULT_COUNTRY_CODE) -> str:
    """Normalise un numéro vers le format international E.164 (ex. +21612345678).

    Règles :
    - Si le numéro commence par '+' → déjà international, on garde tel quel
      (après nettoyage des non-chiffres hors le `+`).
    - Si le numéro commence par '00' → remplace '00' par '+'.
    - Sinon → préfixe avec `country_code` (le `0` de tête local est retiré).
    - Longueur finale (chiffres uniquement, hors le `+`) : 6–15 chiffres.

    Lève `ValueError` si `phone` est vide ou si le résultat n'est pas normalisable
    (trop court, trop long, ou contient des caractères non numériques inattendus
    après nettoyage).
    """
    if not phone or not phone.strip():
        raise ValueError("Le numéro de téléphone est vide.")

    phone = phone.strip()

    # Déjà international (commence par '+')
    if phone.startswith("+"):
        normalized = "+" + _digits_only(phone[1:])
    elif phone.startswith("00"):
        # Forme '00' → '+' (préfixe international alternatif)
        normalized = "+" + _digits_only(phone[2:])
    else:
        digits = _digits_only(phone)
        # Retire le `0` de tête des numéros locaux (ex. 0612345678 → 612345678)
        if digits.startswith("0"):
            digits = digits[1:]
        cc_digits = _digits_only(country_code)
        normalized = "+" + cc_digits + digits

    # Vérification de longueur (chiffres uniquement, hors le `+`)
    digits_only = _digits_only(normalized)
    if len(digits_only) < _MIN_DIGITS:
        raise ValueError(
            f"Numéro trop court après normalisation : « {normalized} » "
            f"({len(digits_only)} chiffres, minimum {_MIN_DIGITS})."
        )
    if len(digits_only) > _MAX_DIGITS:
        raise ValueError(
            f"Numéro trop long après normalisation : « {normalized} » "
            f"({len(digits_only)} chiffres, maximum {_MAX_DIGITS})."
        )

    return normalized


def build_whatsapp_link(
    phone: str, message: str, country_code: str = DEFAULT_COUNTRY_CODE
) -> str:
    """Construit le lien `https://wa.me/<numero>?text=<message_urlencodé>`.

    `phone` est d'abord normalisé via `normalize_phone`. Le numéro inséré dans
    l'URL est sans le `+` (format attendu par wa.me). Le message est URL-encodé
    sans caractères réservés (`safe=""`).

    Lève `ValueError` si le numéro ne peut pas être normalisé.
    """
    normalized = normalize_phone(phone, country_code)
    # wa.me attend le numéro sans le '+' (ex. wa.me/21612345678)
    number_no_plus = normalized.lstrip("+")
    encoded_text = urllib.parse.quote(message or "", safe="")
    return f"https://wa.me/{number_no_plus}?text={encoded_text}"
