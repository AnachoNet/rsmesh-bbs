import uuid
from datetime import datetime

import pytest

from rsmesh_bbs import db_operations
from rsmesh_bbs.mock_interface import MockMeshInterface


def _add_catalog_node(short_name, node_hex, forward_to=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db_operations.get_db_connection()
    conn.execute(
        "INSERT INTO node_catalog "
        "(long_name, short_name, node_hex_username, bbs_mail_forward_to, created, updated) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (short_name, short_name, node_hex, forward_to, now, now),
    )
    conn.commit()


class TestMailForwarding:
    def test_forwards_mail_to_catalog_target(self, temp_db):
        _add_catalog_node("ALICE", "!alice01", "!bob01")
        _add_catalog_node("BOB", "!bob01", None)

        recipient_id, content = db_operations.apply_mail_forwarding(
            "!alice01", "Hello there", interface=None
        )
        assert recipient_id == "!bob01"
        assert content.endswith("Sent to ALICE")

    def test_unresolved_forward_target_delivers_to_original(self, temp_db):
        _add_catalog_node("ALICE", "!alice01", "UNKNOWN")

        recipient_id, content = db_operations.apply_mail_forwarding(
            "!alice01", "Hello", interface=None
        )
        assert recipient_id == "!alice01"
        assert content == "Hello"

    def test_add_mail_applies_forwarding(self, temp_db):
        _add_catalog_node("ALICE", "!alice01", "!bob01")
        _add_catalog_node("BOB", "!bob01", None)
        unique_id = str(uuid.uuid4())

        db_operations.add_mail(
            "!sender01",
            "SND",
            "!alice01",
            "Subject",
            "Packet",
            [],
            None,
            unique_id=unique_id,
        )

        conn = db_operations.get_db_connection()
        row = conn.execute(
            "SELECT recipient, content FROM mail WHERE unique_id = ?", (unique_id,)
        ).fetchone()
        assert row[0] == "!bob01"
        assert "Sent to ALICE" in row[1]


class TestMailRecipientNotification:
    def test_local_add_mail_notifies_recipient(self, temp_db, monkeypatch):
        interface = MockMeshInterface()
        interface.add_node("!recipient01", 42, "RCPT")
        sent = []

        def _capture(text, destination_id, iface):
            sent.append((destination_id, text))
            return True

        monkeypatch.setattr(db_operations, "send_message", _capture)
        monkeypatch.setattr(db_operations, "sync_mail_record", lambda *args, **kwargs: None)

        db_operations.add_mail(
            "!sender01",
            "SNDR",
            "!recipient01",
            "Subject",
            "Body",
            [],
            interface,
            defer_sync=True,
        )

        assert len(sent) == 1
        assert sent[0][0] == "!recipient01"
        assert sent[0][1] == "New mail from SNDR. Send RM to read new mail."

    def test_sync_ingest_does_not_notify_recipient(self, temp_db, monkeypatch):
        interface = MockMeshInterface()
        interface.add_node("!recipient01", 42, "RCPT")

        def _fail_if_called(*_args, **_kwargs):
            pytest.fail("send_message should not run for sync ingest")

        monkeypatch.setattr(db_operations, "send_message", _fail_if_called)

        db_operations.add_mail(
            "!sender01",
            "SNDR",
            "!recipient01",
            "Subject",
            "Body",
            [],
            interface,
            unique_id=str(uuid.uuid4()),
            from_sync=True,
        )
