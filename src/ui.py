"""Interface terminal coloree (style Claude) : banniere, encadres, menu, resume.

Sans dependance externe : couleurs ANSI truecolor avec activation Windows via ctypes.
Si le terminal ne supporte pas la couleur, tout retombe proprement en texte simple.
"""

from __future__ import annotations

import os
import sys

# --- Detection / activation de la couleur ------------------------------------

def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        # Autorise quand meme la couleur dans la console Windows gelee (exe)
        return getattr(sys, "frozen", False)
    return True


def _enable_utf8() -> None:
    """Force la sortie console en UTF-8 (necessaire pour les encadres/symboles)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:  # noqa: BLE001
            pass


def enable_ansi() -> bool:
    """Active le traitement des sequences ANSI sur la console Windows.

    Retourne True si la couleur est utilisable.
    """
    _enable_utf8()
    if not _supports_color():
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004 sur le handle de sortie
            for handle_id in (-11, -12):  # STDOUT, STDERR
                handle = kernel32.GetStdHandle(handle_id)
                mode = ctypes.c_uint32()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:  # noqa: BLE001
            return False
    return True


_ENABLED = enable_ansi()


# --- Palette (style Claude : accent corail/orange, gris doux) -----------------

def _rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m" if _ENABLED else ""


RESET = "\033[0m" if _ENABLED else ""
BOLD = "\033[1m" if _ENABLED else ""
DIM = "\033[2m" if _ENABLED else ""
ITALIC = "\033[3m" if _ENABLED else ""

ACCENT = _rgb(217, 119, 87)    # corail Claude
ACCENT_SOFT = _rgb(198, 130, 105)
GREEN = _rgb(108, 196, 138)
RED = _rgb(224, 108, 117)
YELLOW = _rgb(229, 192, 123)
BLUE = _rgb(97, 175, 239)
MUTED = _rgb(138, 143, 152)
WHITE = _rgb(229, 229, 229)


def _c(text: str, *codes: str) -> str:
    if not _ENABLED or not codes:
        return text
    return "".join(codes) + text + RESET


# --- Largeur d'affichage ------------------------------------------------------

WIDTH = 60


def _visible_len(text: str) -> int:
    """Longueur du texte sans les sequences ANSI."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            if j == -1:
                break
            i = j + 1
            continue
        out += 1
        i += 1
    return out


# --- Composants ---------------------------------------------------------------

def banner(title: str, subtitle: str = "") -> None:
    """Banniere d'accueil encadree avec accent."""
    print()
    top = "╭" + "─" * (WIDTH - 2) + "╮"
    bottom = "╰" + "─" * (WIDTH - 2) + "╯"
    print(_c(top, ACCENT))
    _boxed_line(_c("✦ ", ACCENT) + _c(title, BOLD, WHITE))
    if subtitle:
        _boxed_line(_c(subtitle, DIM, MUTED))
    print(_c(bottom, ACCENT))
    print()


def _boxed_line(content: str) -> None:
    pad = WIDTH - 4 - _visible_len(content)
    pad = max(pad, 0)
    print(_c("│", ACCENT) + " " + content + " " * pad + " " + _c("│", ACCENT))


def rule(label: str = "") -> None:
    if label:
        line = f"── {label} "
        line += "─" * max(WIDTH - _visible_len(line), 0)
        print(_c(line, DIM, MUTED))
    else:
        print(_c("─" * WIDTH, DIM, MUTED))


def step(text: str) -> None:
    print(_c("→ ", ACCENT) + _c(text, WHITE))


def success(text: str) -> None:
    print(_c("✔ ", GREEN) + text)


def error(text: str) -> None:
    print(_c("✘ ", RED) + _c(text, RED))


def warn(text: str) -> None:
    print(_c("▲ ", YELLOW) + _c(text, YELLOW))


def info(text: str) -> None:
    print(_c("• ", BLUE) + _c(text, MUTED))


def note(text: str) -> None:
    print("  " + _c(text, DIM, MUTED))


def section(title: str) -> None:
    print()
    print(_c("▌ ", ACCENT) + _c(title, BOLD, WHITE))
    print()


def stat(label: str, value, accent: str = "") -> None:
    """Ligne de statistique alignee : label ........ valeur."""
    value_str = str(value)
    dots = WIDTH - 4 - len(label) - len(value_str)
    dots = max(dots, 1)
    color = accent or WHITE
    print(
        "  "
        + _c(label, MUTED)
        + " "
        + _c("·" * dots, DIM, MUTED)
        + " "
        + _c(value_str, BOLD, color)
    )


def menu(prompt: str, options: list[tuple[str, str]], default: str | None = None) -> str:
    """Affiche un menu et retourne la cle choisie.

    options : liste de (cle, libelle). default : cle pre-selectionnee (Entree).
    """
    print()
    print(_c("? ", ACCENT) + _c(prompt, BOLD, WHITE))
    print()
    for key, label in options:
        marker = _c(f"[{key}]", BOLD, ACCENT)
        suffix = _c("  (defaut)", DIM, MUTED) if key == default else ""
        print(f"    {marker}  {label}{suffix}")
    print()

    valid = {key for key, _ in options}
    while True:
        try:
            raw = input(_c("  ➤ Votre choix : ", ACCENT)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default or options[-1][0]
        if not raw and default is not None:
            return default
        if raw in valid:
            return raw
        warn(f"Choix invalide : tapez l'une des options {sorted(valid)}.")


def pause(text: str = "Appuyez sur Entree pour fermer...") -> None:
    print()
    try:
        input(_c("  " + text, DIM, MUTED))
    except (EOFError, KeyboardInterrupt):
        pass
