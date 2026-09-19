"""Upgrade installed RSMesh-BBS deployments between release versions (1.0 -> 1.1)."""

import logging
from pathlib import Path

import yaml

from .config_init import (
    DATABASE_VERSION_KEY,
    DATABASE_VERSION_SECTION,
    DEFAULT_CONFIG_FILE,
    get_example_config_path,
    load_config,
)
from .version import VERSION

RELEASE_1_0 = "1.0"
RELEASE_1_1 = "1.1"
RELEASE_1_2 = "1.2"

RELEASE_ORDER = (RELEASE_1_0, RELEASE_1_1, RELEASE_1_2)

_pending_finalize = False


def merge_release_config_yaml(config_file=None) -> bool:
    """Add missing example_config.yml keys (1.1) to config.yml without overwriting values."""
    config_file = config_file or DEFAULT_CONFIG_FILE
    path = Path(config_file)
    if not path.is_file():
        return False
    config = load_config(str(path))
    example = load_config(str(get_example_config_path()))
    updated = False
    for section, values in example.items():
        if not isinstance(values, dict):
            continue
        section_dict = config.setdefault(section, {})
        for key, default_value in values.items():
            if key not in section_dict:
                section_dict[key] = default_value
                updated = True
    if updated:
        with path.open("w", encoding="utf-8") as handle:
            yaml.dump(config, handle, default_flow_style=False, sort_keys=False)
    return updated


def prepare_release_upgrade(config_file=None):
    """Run pre-database 1.0 -> 1.1 config.yml upgrade steps."""
    config_file = config_file or DEFAULT_CONFIG_FILE
    migrated = False
    if merge_release_config_yaml(config_file):
        logging.info("Merged release 1.1 keys into %s.", config_file)
        migrated = True
    return migrated


def apply_database_upgrades(conn=None):
    """Run upgrade-path database work, then indexes and version stamp for all installs."""
    if conn is None:
        from .db_operations import get_db_connection

        conn = get_db_connection()
    c = conn.cursor()
    from .tc2_migration import migrate_tc2_database

    migrate_tc2_database(c)
    migrate_release_database(c)
    from .db_operations import _ensure_database_indexes

    _ensure_database_indexes(c)
    conn.commit()


def migrate_release_database(c):
    """Apply 1.0 -> 1.1 database migrations and stamp the installed database version."""
    global _pending_finalize

    stored = get_stored_database_version(c)
    if stored == VERSION:
        return False

    migrated = False
    if _needs_1_0_to_1_1_migration(c, stored):
        _migrate_1_0_to_1_1_database(c)
        _pending_finalize = True
        migrated = True

    if stored != VERSION:
        set_stored_database_version(c, VERSION)
        migrated = True

    return migrated


def finalize_release_upgrade(quiet=False):
    """Run post-config steps after sys_config has been seeded (for example main menu)."""
    global _pending_finalize
    if not _pending_finalize:
        return False

    from .mesh_ui import request_main_menu_regeneration

    request_main_menu_regeneration()
    _pending_finalize = False
    message = f"RSMesh-BBS database upgraded to release {VERSION}."
    if quiet:
        logging.info(message)
    else:
        print(message)
    return True


def get_stored_database_version(c):
    if not _table_exists(c, "sys_config"):
        return None
    row = c.execute(
        "SELECT cfg_value FROM sys_config WHERE cfg_section = ? AND cfg_key = ?",
        (DATABASE_VERSION_SECTION, DATABASE_VERSION_KEY),
    ).fetchone()
    return row[0] if row else None


def set_stored_database_version(c, version):
    row = c.execute(
        "SELECT 1 FROM sys_config WHERE cfg_section = ? AND cfg_key = ?",
        (DATABASE_VERSION_SECTION, DATABASE_VERSION_KEY),
    ).fetchone()
    if row:
        c.execute(
            "UPDATE sys_config SET cfg_value = ? WHERE cfg_section = ? AND cfg_key = ?",
            (version, DATABASE_VERSION_SECTION, DATABASE_VERSION_KEY),
        )
    else:
        c.execute(
            "INSERT INTO sys_config (cfg_section, cfg_key, cfg_value) VALUES (?, ?, ?)",
            (DATABASE_VERSION_SECTION, DATABASE_VERSION_KEY, version),
        )


def ensure_release_1_1_schema(c):
    """Idempotent 1.1 schema completion for 1.0 upgrades (not used on fresh 1.1 installs)."""
    if not _table_exists(c, "bulletins"):
        return

    _upgrade_bulletins_schema(c)
    _upgrade_mail_schema(c)
    _upgrade_channels_schema(c)
    _upgrade_sync_peers_schema(c)
    _upgrade_node_catalog_schema(c)
    _upgrade_modules_schema(c)
    _create_release_1_1_support_tables(c)


def _upgrade_bulletins_schema(c):
    _add_column_if_missing(c, "bulletins", "deleted", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "bulletins", "delete_reconcile", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "bulletins", "synced", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "bulletins", "pinned", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "bulletins", "from_sync", "TEXT NOT NULL DEFAULT 'N'")


def _upgrade_mail_schema(c):
    if not _table_exists(c, "mail"):
        return

    _add_column_if_missing(c, "mail", "synced", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "mail", "read", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "mail", "recipient_short_name", "TEXT")
    _migrate_mail_recipient_nullable(c)
    _backfill_mail_recipient_short_names(c)


def _upgrade_channels_schema(c):
    if not _table_exists(c, "channels"):
        return

    _add_column_if_missing(c, "channels", "publish", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "channels", "synced", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "channels", "unique_id", "TEXT")
    _add_column_if_missing(c, "channels", "deleted", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "channels", "delete_reconcile", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "channels", "from_sync", "TEXT NOT NULL DEFAULT 'N'")


def _node_catalog_public_key_is_nullable(c):
    for _cid, name, _type, notnull, _dflt, _pk in c.execute(
        "PRAGMA table_info(node_catalog)"
    ).fetchall():
        if name == "public_key":
            return notnull == 0
    return True


def _upgrade_modules_schema(c):
    if not _table_exists(c, "modules"):
        return

    _add_column_if_missing(
        c,
        "modules",
        "main_menu_visible",
        "TEXT NOT NULL DEFAULT 'N'",
    )


def _upgrade_node_catalog_schema(c):
    if not _table_exists(c, "node_catalog"):
        return
    if _node_catalog_public_key_is_nullable(c):
        return

    c.execute(
        """CREATE TABLE node_catalog_rsmesh (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               long_name TEXT NOT NULL,
               short_name TEXT NOT NULL,
               node_hex_username TEXT NOT NULL,
               mesh_admin TEXT NOT NULL DEFAULT 'N',
               bbs_admin TEXT NOT NULL DEFAULT 'N',
               bbs_mail_forward_to TEXT,
               has_gps TEXT NOT NULL DEFAULT 'N',
               public_key TEXT,
               private_key TEXT,
               ble_pin TEXT NOT NULL DEFAULT '123456',
               hardware TEXT,
               comment TEXT,
               created TEXT NOT NULL,
               updated TEXT NOT NULL
           )"""
    )
    c.execute(
        """INSERT INTO node_catalog_rsmesh (
               id, long_name, short_name, node_hex_username, mesh_admin, bbs_admin,
               bbs_mail_forward_to, has_gps, public_key, private_key, ble_pin,
               hardware, comment, created, updated
           )
           SELECT
               id, long_name, short_name, node_hex_username, mesh_admin, bbs_admin,
               bbs_mail_forward_to, has_gps, public_key, private_key, ble_pin,
               hardware, comment, created, updated
           FROM node_catalog"""
    )
    c.execute("DROP TABLE node_catalog")
    c.execute("ALTER TABLE node_catalog_rsmesh RENAME TO node_catalog")
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_node_catalog_node "
        "ON node_catalog(node_hex_username)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_node_catalog_short_name "
        "ON node_catalog(short_name)"
    )


def _upgrade_sync_peers_schema(c):
    if not _table_exists(c, "sync_peers"):
        return

    _add_column_if_missing(c, "sync_peers", "sync_mesh_nodes", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "sync_peers", "ingest_bulletins", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "sync_peers", "ingest_channels", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "sync_peers", "rs_version_alert", "TEXT NOT NULL DEFAULT 'N'")
    _add_column_if_missing(c, "sync_peers", "rs_wire_version_seen", "INTEGER")
    _add_column_if_missing(c, "sync_peers", "enabled", "TEXT NOT NULL DEFAULT 'Y'")
    _add_column_if_missing(c, "sync_peers", "allow_resync", "TEXT NOT NULL DEFAULT 'Y'")
    c.execute(
        "UPDATE sync_peers SET sync_mesh_nodes = 'N' WHERE sync_protocol = 'tc2'"
    )


def _create_release_1_1_support_tables(c):
    c.execute(
        """CREATE TABLE IF NOT EXISTS mesh_nodes (
               node_id TEXT PRIMARY KEY,
               short_name TEXT,
               long_name TEXT,
               last_heard INTEGER,
               last_updated INTEGER NOT NULL
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS pending_sync_deletes (
               record_type TEXT NOT NULL,
               record_key TEXT NOT NULL,
               created TEXT NOT NULL,
               PRIMARY KEY (record_type, record_key)
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS pending_urgent_alerts (
               unique_id TEXT NOT NULL PRIMARY KEY,
               sender_short_name TEXT NOT NULL,
               subject TEXT NOT NULL,
               created TEXT NOT NULL
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS pending_resync_requests (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               target_bbs_node TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'pending',
               created TEXT NOT NULL
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS peer_resync_outbound (
               requester_bbs_node TEXT NOT NULL PRIMARY KEY,
               stage TEXT NOT NULL,
               stage_cursor INTEGER NOT NULL DEFAULT 0,
               mesh_batch_index INTEGER NOT NULL DEFAULT 0,
               updated INTEGER NOT NULL
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS sync_peer_modules (
               peer_id INTEGER NOT NULL,
               module_id INTEGER NOT NULL,
               sync_out TEXT NOT NULL DEFAULT 'Y',
               ingest_in TEXT NOT NULL DEFAULT 'Y',
               PRIMARY KEY (peer_id, module_id),
               FOREIGN KEY (peer_id) REFERENCES sync_peers(id) ON DELETE CASCADE,
               FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
           )"""
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_peer_modules_module "
        "ON sync_peer_modules(module_id)"
    )


def _mail_recipient_is_nullable(c):
    for _cid, name, _type, notnull, _dflt, _pk in c.execute("PRAGMA table_info(mail)").fetchall():
        if name == "recipient":
            return notnull == 0
    return False


def _migrate_mail_recipient_nullable(c):
    if _mail_recipient_is_nullable(c):
        return

    c.execute(
        """CREATE TABLE mail_rsmesh (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               sender TEXT NOT NULL,
               sender_short_name TEXT NOT NULL,
               recipient TEXT,
               recipient_short_name TEXT,
               date TEXT NOT NULL,
               subject TEXT NOT NULL,
               content TEXT NOT NULL,
               unique_id TEXT NOT NULL,
               synced TEXT NOT NULL DEFAULT 'N',
               read TEXT NOT NULL DEFAULT 'N'
           )"""
    )
    c.execute(
        """INSERT INTO mail_rsmesh (
               id, sender, sender_short_name, recipient, recipient_short_name,
               date, subject, content, unique_id, synced, read
           )
           SELECT
               id, sender, sender_short_name, recipient, recipient_short_name,
               date, subject, content, unique_id, synced, read
           FROM mail"""
    )
    c.execute("DROP TABLE mail")
    c.execute("ALTER TABLE mail_rsmesh RENAME TO mail")


def _backfill_mail_recipient_short_names(c):
    from .node_resolution import is_hex_node_id

    rows = c.execute(
        "SELECT id, recipient FROM mail WHERE recipient_short_name IS NULL OR recipient_short_name = ''"
    ).fetchall()
    for mail_id, recipient in rows:
        recipient = (recipient or "").strip()
        if not recipient:
            continue
        if is_hex_node_id(recipient):
            continue
        c.execute(
            "UPDATE mail SET recipient_short_name = ?, recipient = NULL WHERE id = ?",
            (recipient, mail_id),
        )


def _add_column_if_missing(c, table_name, column_name, definition):
    if column_name not in _table_columns(c, table_name):
        c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _needs_1_0_to_1_1_migration(c, stored_version):
    if stored_version == RELEASE_1_1:
        return False
    if stored_version == RELEASE_1_0:
        return True
    if stored_version is not None:
        return _release_index(stored_version) < _release_index(RELEASE_1_1)
    if _database_has_legacy_content(c):
        return True
    return _database_has_legacy_schema(c)


def _database_has_legacy_schema(c):
    """True when an existing DB predates the 1.1 schema (for example interrupted upgrade)."""
    if not _table_exists(c, "bulletins"):
        return False

    bulletin_columns = _table_columns(c, "bulletins")
    for column in ("from_sync", "pinned"):
        if column not in bulletin_columns:
            return True

    if _table_exists(c, "sync_peers") and "allow_resync" not in _table_columns(c, "sync_peers"):
        return True

    if _table_exists(c, "modules") and "main_menu_visible" not in _table_columns(c, "modules"):
        return True

    if _table_exists(c, "mail") and "recipient_short_name" not in _table_columns(c, "mail"):
        return True

    if not _table_exists(c, "pending_resync_requests"):
        return True

    return False


def _table_columns(c, table_name):
    return [row[1] for row in c.execute(f"PRAGMA table_info({table_name})")]


def migrate_bbs_list_module_schema(cursor):
    """Upgrade legacy bbs_list.db rows that predate the INTEGER PRIMARY KEY id column."""
    columns = _table_columns(cursor, "bbs_entries")
    if not columns or "id" in columns:
        return
    cursor.execute(
        """CREATE TABLE bbs_entries_new (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               node_hex TEXT NOT NULL UNIQUE,
               board_name TEXT NOT NULL,
               short_name TEXT NOT NULL,
               location TEXT,
               sync_interest TEXT NOT NULL DEFAULT 'N',
               is_local TEXT NOT NULL DEFAULT 'N',
               updated INTEGER NOT NULL
           )"""
    )
    cursor.execute(
        """INSERT INTO bbs_entries_new
           (node_hex, board_name, short_name, location, sync_interest, is_local, updated)
           SELECT node_hex, board_name, short_name, location, sync_interest, is_local, updated
           FROM bbs_entries
           ORDER BY rowid"""
    )
    cursor.execute("DROP TABLE bbs_entries")
    cursor.execute("ALTER TABLE bbs_entries_new RENAME TO bbs_entries")


def _migrate_1_0_to_1_1_database(c):
    stored = get_stored_database_version(c)
    if stored == RELEASE_1_0:
        logging.info(
            "Upgrading RSMesh-BBS database from release %s to %s.",
            RELEASE_1_0,
            RELEASE_1_1,
        )
    else:
        logging.info("Completing RSMesh-BBS database schema for release %s.", RELEASE_1_1)
    ensure_release_1_1_schema(c)
    return True


def _database_has_legacy_content(c):
    """True when upgrading an existing deployment, not a fresh empty install."""
    if not _table_exists(c, "bulletins"):
        return False

    checks = (
        "SELECT 1 FROM bulletins LIMIT 1",
        "SELECT 1 FROM mail LIMIT 1",
        "SELECT 1 FROM sync_peers LIMIT 1",
        "SELECT 1 FROM sysadmin_nodes LIMIT 1",
        "SELECT 1 FROM node_catalog LIMIT 1",
        "SELECT 1 FROM channels LIMIT 1",
    )
    for query in checks:
        try:
            if c.execute(query).fetchone():
                return True
        except Exception:
            continue
    return False


def _release_index(version):
    try:
        return RELEASE_ORDER.index(version)
    except ValueError:
        return -1


def _table_exists(c, name):
    return (
        c.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        is not None
    )
