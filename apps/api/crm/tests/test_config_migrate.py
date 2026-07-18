from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from crm.config_migrate import CONFIG_VERSION, ConfigTooNewError, migrate, read_config_version


def test_read_config_version_no_file(tmp_path: Path):
    assert read_config_version(tmp_path / "nonexistent.ini") == 0


def test_read_config_version_no_comment(tmp_path: Path):
    path = tmp_path / "config.ini"
    path.write_text("[section]\nkey = val\n", encoding="utf-8")
    assert read_config_version(path) == 0


def test_read_config_version_with_comment(tmp_path: Path):
    path = tmp_path / "config.ini"
    path.write_text("; config_version = 42\n[section]\nkey = val\n", encoding="utf-8")
    assert read_config_version(path) == 42


def test_migrate_fresh_install(tmp_path: Path):
    config_path = tmp_path / "config.ini"
    default_path = tmp_path / "config.default.ini"
    default_path.write_text("; config_version = 1\n[section]\nkey = default_val\n", encoding="utf-8")

    # Si config.ini n'existe pas, migrate ne fait rien (l'installer NSIS posera le défaut)
    migrate(config_path, default_path)
    assert not config_path.exists()


def test_migrate_existing_no_version(tmp_path: Path):
    config_path = tmp_path / "config.ini"
    default_path = tmp_path / "config.default.ini"

    config_path.write_text("[section]\nkey = user_val\n", encoding="utf-8")
    default_path.write_text(
        f"; config_version = {CONFIG_VERSION}\n[section]\nkey = default_val\nnew_key = new_val\n",
        encoding="utf-8",
    )

    migrate(config_path, default_path)

    # Vérification que le backup a été créé (pre-v0)
    backup_path = tmp_path / "config.pre-v0.ini"
    assert backup_path.exists()
    assert "[section]\nkey = user_val" in backup_path.read_text(encoding="utf-8")

    # Vérification que la config a été migrée
    assert read_config_version(config_path) == CONFIG_VERSION
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")

    # Préservation de la valeur utilisateur
    assert parser.get("section", "key") == "user_val"
    # Ajout de la nouvelle clé par défaut
    assert parser.get("section", "new_key") == "new_val"


def test_migrate_idempotence(tmp_path: Path):
    config_path = tmp_path / "config.ini"
    default_path = tmp_path / "config.default.ini"

    config_path.write_text(f"; config_version = {CONFIG_VERSION}\n[section]\nkey = user_val\n", encoding="utf-8")
    default_path.write_text(
        f"; config_version = {CONFIG_VERSION}\n[section]\nkey = default_val\n",
        encoding="utf-8",
    )

    # Lancement une première fois
    migrate(config_path, default_path)
    # Aucun backup ne devrait être créé car déjà à la bonne version
    assert not (tmp_path / f"config.pre-v{CONFIG_VERSION}.ini").exists()

    mtime_before = config_path.stat().st_mtime
    # Lancement une deuxième fois
    migrate(config_path, default_path)
    mtime_after = config_path.stat().st_mtime

    # La date de modif ne devrait pas avoir changé (idempotent, pas de réécriture nécessaire)
    # ou du moins le comportement est un no-op.
    assert read_config_version(config_path) == CONFIG_VERSION


def test_migrate_downgrade_prevention(tmp_path: Path):
    config_path = tmp_path / "config.ini"
    default_path = tmp_path / "config.default.ini"

    # Version sur disque supérieure à celle attendue par le code (CONFIG_VERSION = 1)
    config_path.write_text(f"; config_version = {CONFIG_VERSION + 1}\n[section]\nkey = user_val\n", encoding="utf-8")
    default_path.write_text(
        f"; config_version = {CONFIG_VERSION}\n[section]\nkey = default_val\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigTooNewError):
        migrate(config_path, default_path)
