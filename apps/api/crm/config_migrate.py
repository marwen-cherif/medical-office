from __future__ import annotations

import configparser
import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_VERSION = 1


class ConfigTooNewError(RuntimeError):
    def __init__(self, disk_version: int, app_version: int) -> None:
        self.disk_version = disk_version
        self.app_version = app_version
        super().__init__(
            f"Fichier de configuration en version {disk_version}, attendu au maximum version {app_version}."
        )


def read_config_version(config_path: Path) -> int:
    """Lit la config_version en tête du fichier config_path.

    Retourne 0 si non spécifiée ou si le fichier n'existe pas.
    """
    if not config_path.exists():
        return 0
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for _ in range(10):  # Lire les 10 premières lignes max
                line = f.readline()
                if not line:
                    break
                match = re.search(r"^\s*;\s*config_version\s*=\s*(\d+)", line)
                if match:
                    return int(match.group(1))
    except Exception as e:
        logger.warning("Impossible de lire la version de la config : %s", e)
    return 0


def migrate(config_path: Path, default_path: Path) -> None:
    """Fusionne les clés manquantes de default_path vers config_path.

    Conserve les valeurs existantes, met à jour la version de config,
    et crée un backup pre-v<N>.ini avant modification.
    """
    if not config_path.exists():
        logger.info("config.ini n'existe pas. Aucune migration nécessaire (première install).")
        return

    if not default_path.exists():
        logger.warning("config.default.ini introuvable à %s", default_path)
        return

    disk_version = read_config_version(config_path)
    logger.info("Version actuelle de config.ini sur le disque : %s (attendue : %s)", disk_version, CONFIG_VERSION)

    if disk_version > CONFIG_VERSION:
        raise ConfigTooNewError(disk_version, CONFIG_VERSION)

    # Création du snapshot uniquement en cas de montée de version de configuration
    if disk_version < CONFIG_VERSION:
        try:
            backup_path = config_path.parent / f"config.pre-v{disk_version}.ini"
            shutil.copy2(config_path, backup_path)
            logger.info("Backup pré-migration créé : %s", backup_path)
        except Exception as e:
            logger.error("Impossible de créer le backup pré-migration de configuration : %s", e)

    # Lecture et fusion
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(config_path, encoding="utf-8")

        default_parser = configparser.ConfigParser(interpolation=None)
        default_parser.read(default_path, encoding="utf-8")

        modified = False
        for section in default_parser.sections():
            if not parser.has_section(section):
                parser.add_section(section)
                modified = True
            for option in default_parser.options(section):
                if not parser.has_option(section, option):
                    parser.set(section, option, default_parser.get(section, option))
                    modified = True

        # Si la version a changé, on doit réécrire pour mettre à jour la ligne de commentaire
        if disk_version < CONFIG_VERSION:
            modified = True

        if modified:
            content = []
            content.append(f"; config_version = {CONFIG_VERSION}\n\n")

            import io
            temp_io = io.StringIO()
            parser.write(temp_io)
            content.append(temp_io.getvalue())

            with open(config_path, "w", encoding="utf-8") as f:
                f.write("".join(content))

            if disk_version < CONFIG_VERSION:
                logger.info("Migration de config.ini réussie de v%s vers v%s", disk_version, CONFIG_VERSION)
            else:
                logger.info("Fusion des clés manquantes dans config.ini effectuée avec succès.")
        else:
            logger.info("config.ini est déjà à jour.")

    except Exception as e:
        logger.error("Échec de la migration de config.ini : %s", e)
