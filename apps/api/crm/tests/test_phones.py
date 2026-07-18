"""Tests unitaires du module `crm.phones` (normalisation E.164 + lien wa.me).

Logique pure, sans DB — les cas limites sont les plus importants :
- Formes locales / internationales / `00` / `+`
- Retrait du `0` de tête
- Bornes de longueur (min/max)
- Espaces et séparateurs
- Encodage URL du message
"""
import pytest

from crm.phones import DEFAULT_COUNTRY_CODE, build_whatsapp_link, normalize_phone

# -----------------------------------------------------------------------------
# Cas valides
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phone,country,expected",
    [
        # Numéro local tunisien (indicatif par défaut)
        ("0612345678", "+216", "+216612345678"),
        ("612345678", "+216", "+216612345678"),
        ("98765432", "+216", "+21698765432"),
        # Déjà international avec '+'
        ("+33612345678", "+216", "+33612345678"),
        ("+21698765432", "+216", "+21698765432"),
        # Forme '00' (préfixe international alternatif)
        ("0033612345678", "+216", "+33612345678"),
        ("0021698765432", "+216", "+21698765432"),
        # Séparateurs (espaces, points, tirets) — nettoyés
        ("06 12 34 56 78", "+216", "+216612345678"),
        ("06.12.34.56.78", "+216", "+216612345678"),
        ("+33 6 12 34 56 78", "+216", "+33612345678"),
        # Indicatif pays sans '+' passé en paramètre
        ("612345678", "216", "+216612345678"),
        # Espaces de tête/trailing
        ("  0612345678  ", "+216", "+216612345678"),
        # Numéro à la borne minimale (6 chiffres)
        ("123456", "+216", "+216123456"),
        ("+123456", "+216", "+123456"),
    ],
)
def test_normalize_phone_valid(phone, country, expected):
    assert normalize_phone(phone, country) == expected


def test_normalize_phone_default_country():
    # Sans second arg, utilise DEFAULT_COUNTRY_CODE (+216)
    assert normalize_phone("98765432") == "+216" + "98765432"
    assert DEFAULT_COUNTRY_CODE == "+216"


# -----------------------------------------------------------------------------
# Cas invalides
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phone",
    [
        "",
        "   ",
        None,
    ],
)
def test_normalize_phone_empty(phone):
    with pytest.raises(ValueError):
        normalize_phone(phone, "+216")


@pytest.mark.parametrize(
    "phone,country",
    [
        # Trop court (< 6 chiffres après normalisation)
        ("+123", "+216"),  # 3 chiffres
        ("12", "+216"),  # +21612 = 5 chiffres
        # Trop long (> 15 chiffres)
        ("+1234567890123456", "+216"),  # 16 chiffres
        ("01234567890123456", "+216"),  # +216 + 16 = 18 chiffres
    ],
)
def test_normalize_phone_out_of_bounds(phone, country):
    with pytest.raises(ValueError):
        normalize_phone(phone, country)


# -----------------------------------------------------------------------------
# build_whatsapp_link
# -----------------------------------------------------------------------------


def test_build_whatsapp_link_basic():
    url = build_whatsapp_link("0612345678", "Bonjour", "+216")
    # Numéro sans le '+' (format wa.me), message URL-encodé
    assert url == "https://wa.me/216612345678?text=Bonjour"


def test_build_whatsapp_link_empty_message():
    url = build_whatsapp_link("0612345678", "", "+216")
    assert url == "https://wa.me/216612345678?text="


def test_build_whatsapp_link_none_message():
    url = build_whatsapp_link("0612345678", None, "+216")  # type: ignore[arg-type]
    assert url == "https://wa.me/216612345678?text="


def test_build_whatsapp_link_special_chars():
    # Espaces, accents, ponctuation, sauts de ligne → URL-encodés (safe="")
    url = build_whatsapp_link("98765432", "Bonjour M. Dupont, àientôt !", "+216")
    # Vérifie qu'aucun caractère réservé brut n'est présent
    assert " " not in url
    assert "é" not in url
    assert url.startswith("https://wa.me/21698765432?text=")
    # Le texte est décodable et retrouve sa forme originale
    from urllib.parse import parse_qs, urlparse

    query = urlparse(url).query
    assert parse_qs(query)["text"][0] == "Bonjour M. Dupont, àientôt !"


def test_build_whatsapp_link_multiline():
    msg = "Ligne 1\nLigne 2"
    url = build_whatsapp_link("98765432", msg, "+216")
    # Le saut de ligne doit être encodé (%0A)
    assert "%0A" in url
    assert "\n" not in url.split("text=")[1]


def test_build_whatsapp_link_invalid_phone():
    with pytest.raises(ValueError):
        build_whatsapp_link("+123", "msg", "+216")  # trop court


def test_build_whatsapp_link_plus_international():
    # Numéro déjà international passé tel quel (sans le '+' dans l'URL)
    url = build_whatsapp_link("+33612345678", "Hello", "+216")
    assert url == "https://wa.me/33612345678?text=Hello"
