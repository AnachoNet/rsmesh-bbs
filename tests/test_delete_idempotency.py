import uuid

from rsmesh_bbs import db_operations
from rsmesh_bbs.message_processing import _process_rs_sync_message
from rsmesh_bbs.mock_interface import MockMeshInterface
from rsmesh_bbs.sync_wire import encode_delete_channel_sync_message


def _count_rows(table, where_clause="", params=()):
    conn = db_operations.get_db_connection()
    query = f"SELECT COUNT(*) FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    return conn.execute(query, params).fetchone()[0]


class TestDeleteIdempotency:
    def test_rs_bulletin_delete_is_idempotent(self, temp_db):
        peer_node = "!rspeer01"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_bulletin(
            "general",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
        )

        assert db_operations.delete_bulletin_by_sync_identifier(unique_id, peer_node) is True
        row = db_operations.get_db_connection().execute(
            "SELECT deleted, delete_reconcile FROM bulletins WHERE unique_id = ?",
            (unique_id,),
        ).fetchone()
        assert row == ("Y", "Y")
        assert db_operations.delete_bulletin_by_sync_identifier(unique_id, peer_node) is False

    def test_tc2_bulletin_delete_marks_reconcile_idempotently(self, temp_db):
        peer_node = "!tc2peer1"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="tc2")
        db_operations.add_bulletin(
            "general",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
        )
        conn = db_operations.get_db_connection()
        bulletin_id = conn.execute(
            "SELECT id FROM bulletins WHERE unique_id = ?", (unique_id,)
        ).fetchone()[0]

        assert db_operations.delete_bulletin_by_sync_identifier(str(bulletin_id), peer_node) is True
        row = conn.execute(
            "SELECT deleted, delete_reconcile FROM bulletins WHERE id = ?", (bulletin_id,)
        ).fetchone()
        assert row == ("Y", "Y")
        assert db_operations.delete_bulletin_by_sync_identifier(str(bulletin_id), peer_node) is False

    def test_channel_delete_reconcile_is_idempotent(self, temp_db):
        peer_node = "!rspeer02"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_channel(
            "mesh-chat",
            "psk-value",
            from_sync=True,
            unique_id=unique_id,
        )

        assert db_operations.mark_channel_for_reconcile_by_sync(unique_id, peer_node) is True
        row = db_operations.get_db_connection().execute(
            "SELECT deleted, delete_reconcile FROM channels WHERE unique_id = ?",
            (unique_id,),
        ).fetchone()
        assert row == ("Y", "Y")
        assert db_operations.mark_channel_for_reconcile_by_sync(unique_id, peer_node) is False

    def test_peer_channel_delete_ignored_for_local_origin(self, temp_db):
        peer_node = "!rspeer03"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_channel(
            "mesh-chat",
            "psk-local-origin",
            unique_id=unique_id,
        )

        assert db_operations.mark_channel_for_reconcile_by_sync(unique_id, peer_node) is False
        row = db_operations.get_db_connection().execute(
            "SELECT deleted, delete_reconcile, from_sync FROM channels WHERE unique_id = ?",
            (unique_id,),
        ).fetchone()
        assert row == ("N", "N", "N")
        assert db_operations.get_reconcile_channels() == []

    def test_peer_bulletin_delete_ignored_for_local_origin(self, temp_db):
        peer_node = "!rspeer03b"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_bulletin(
            "general",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
        )

        assert db_operations.delete_bulletin_by_sync_identifier(unique_id, peer_node) is False
        row = db_operations.get_db_connection().execute(
            "SELECT deleted, delete_reconcile, from_sync FROM bulletins WHERE unique_id = ?",
            (unique_id,),
        ).fetchone()
        assert row == ("N", "N", "N")

    def test_restore_reconcile_marks_bulletin_as_local(self, temp_db):
        peer_node = "!rspeer03c"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_bulletin(
            "general",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
        )
        conn = db_operations.get_db_connection()
        bulletin_id = conn.execute(
            "SELECT id FROM bulletins WHERE unique_id = ?", (unique_id,)
        ).fetchone()[0]
        assert db_operations.delete_bulletin_by_sync_identifier(unique_id, peer_node) is True
        assert db_operations.restore_reconcile_bulletin(bulletin_id) is True

        row = conn.execute(
            "SELECT deleted, delete_reconcile, from_sync FROM bulletins WHERE id = ?",
            (bulletin_id,),
        ).fetchone()
        assert row == ("N", "N", "N")
        assert db_operations.delete_bulletin_by_sync_identifier(unique_id, peer_node) is False

    def test_rs_delete_channel_sync_marks_reconcile(self, temp_db):
        peer_node = "!rspeer04"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_channel(
            "mesh-chat",
            "psk-rs-delete",
            from_sync=True,
            unique_id=unique_id,
        )
        interface = MockMeshInterface()
        interface.bbs_nodes = [peer_node]
        db_operations.reload_sync_peers(interface)

        message = encode_delete_channel_sync_message("rsv1", unique_id)
        _process_rs_sync_message(0, message, interface, peer_node)

        row = db_operations.get_db_connection().execute(
            "SELECT deleted, delete_reconcile FROM channels WHERE unique_id = ?",
            (unique_id,),
        ).fetchone()
        assert row == ("Y", "Y")
        assert len(db_operations.get_reconcile_channels()) == 1

    def test_purge_does_not_remove_peer_reconcile_channel(self, temp_db):
        peer_node = "!rspeer05"
        unique_id = str(uuid.uuid4())
        db_operations.add_sync_peer(peer_node, sync_protocol="rsv1")
        db_operations.add_channel(
            "mesh-chat",
            "psk-purge-reconcile",
            from_sync=True,
            unique_id=unique_id,
        )
        assert db_operations.mark_channel_for_reconcile_by_sync(unique_id, peer_node) is True

        interface = MockMeshInterface()
        interface.bbs_nodes = [peer_node]
        db_operations.purge_deleted_channels(interface.bbs_nodes, interface)

        assert _count_rows("channels", "unique_id = ?", (unique_id,)) == 1

    def test_mail_delete_is_idempotent(self, temp_db):
        unique_id = str(uuid.uuid4())
        recipient_hex = "!a1b2c3d4"
        db_operations.add_mail(
            "sender-node",
            "SND",
            recipient_hex,
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
            recipient_short_name="RCP",
        )

        db_operations.delete_mail(unique_id, recipient_hex, [], None)
        assert _count_rows("mail", "unique_id = ?", (unique_id,)) == 0
        db_operations.delete_mail(unique_id, recipient_hex, [], None)
        assert _count_rows("mail", "unique_id = ?", (unique_id,)) == 0

    def test_delete_mail_from_sync_with_short_name_only_recipient(self, temp_db):
        unique_id = str(uuid.uuid4())
        conn = db_operations.get_db_connection()
        db_operations.add_mail(
            "sender-node",
            "SND",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
            recipient_short_name="ALICE",
        )
        conn.execute(
            "UPDATE mail SET recipient = NULL WHERE unique_id = ?",
            (unique_id,),
        )
        conn.commit()

        assert db_operations.delete_mail_from_sync(unique_id) is True
        assert _count_rows("mail", "unique_id = ?", (unique_id,)) == 0
        assert db_operations.delete_mail_from_sync(unique_id) is False

    def test_mesh_user_mail_delete_with_short_name_only_recipient(self, temp_db):
        unique_id = str(uuid.uuid4())
        recipient_hex = "!a1b2c3d4"
        conn = db_operations.get_db_connection()
        db_operations.upsert_mesh_node(recipient_hex, "ALICE")
        db_operations.add_mail(
            "sender-node",
            "SND",
            recipient_hex,
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
            recipient_short_name="ALICE",
        )
        conn.execute(
            "UPDATE mail SET recipient = NULL WHERE unique_id = ?",
            (unique_id,),
        )
        conn.commit()

        db_operations.delete_mail(unique_id, recipient_hex, [], None)
        assert _count_rows("mail", "unique_id = ?", (unique_id,)) == 0


class TestIngestIdempotency:
    def test_duplicate_bulletin_ingest_is_skipped(self, temp_db):
        unique_id = str(uuid.uuid4())
        db_operations.add_bulletin(
            "general",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
        )
        db_operations.add_bulletin(
            "general",
            "ALICE",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
        )
        assert _count_rows("bulletins", "unique_id = ?", (unique_id,)) == 1

    def test_duplicate_mail_ingest_is_skipped(self, temp_db):
        unique_id = str(uuid.uuid4())
        db_operations.add_mail(
            "sender-node",
            "SND",
            "recipient-node",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
            recipient_short_name="RCP",
        )
        db_operations.add_mail(
            "sender-node",
            "SND",
            "recipient-node",
            "Subject",
            "Body",
            [],
            None,
            unique_id=unique_id,
            from_sync=True,
            recipient_short_name="RCP",
        )
        assert _count_rows("mail", "unique_id = ?", (unique_id,)) == 1

    def test_duplicate_channel_ingest_is_skipped(self, temp_db):
        unique_id = str(uuid.uuid4())
        first_id = db_operations.add_channel(
            "mesh-chat",
            "psk-value",
            from_sync=True,
            unique_id=unique_id,
        )
        second_id = db_operations.add_channel(
            "mesh-chat",
            "psk-value",
            from_sync=True,
            unique_id=unique_id,
        )
        assert first_id == second_id
        assert _count_rows("channels", "unique_id = ?", (unique_id,)) == 1
