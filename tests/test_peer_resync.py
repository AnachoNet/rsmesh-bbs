from rsmesh_bbs import db_operations
from rsmesh_bbs.message_processing import _process_rs_sync_message
from rsmesh_bbs.mock_interface import MockMeshInterface
from rsmesh_bbs.peer_resync import (
    handle_inbound_resync_request,
    peer_allow_resync,
    queue_peer_resync_request,
)
from rsmesh_bbs.sync_wire import build_rs_message, encode_resync_request_message


def _setup_rsv1_peers(interface, local="!bbs_local", remote="!bbs_remote"):
    db_operations.add_sync_peer(local, sync_protocol="rsv1", bbs_name="Local")
    db_operations.add_sync_peer(
        remote,
        sync_protocol="rsv1",
        bbs_name="Remote",
        allow_resync="Y",
    )
    interface.bbs_nodes = [local, remote]
    db_operations.reload_sync_peers(interface)
    return remote


class TestPeerResync:
    def test_queue_resync_request(self, temp_db):
        db_operations.add_sync_peer("!peer1", sync_protocol="rsv1")
        assert queue_peer_resync_request("!peer1") is True
        conn = db_operations.get_db_connection()
        row = conn.execute(
            "SELECT target_bbs_node, status FROM pending_resync_requests"
        ).fetchone()
        assert row == ("!peer1", "pending")

    def test_inbound_resync_denied_when_not_allowed(self, temp_db):
        interface = MockMeshInterface()
        remote = "!requester"
        db_operations.add_sync_peer(remote, sync_protocol="rsv1", allow_resync="N")
        interface.bbs_nodes = [remote]
        db_operations.reload_sync_peers(interface)

        handle_inbound_resync_request(remote, interface)

        conn = db_operations.get_db_connection()
        assert conn.execute("SELECT COUNT(*) FROM peer_resync_outbound").fetchone()[0] == 0

    def test_inbound_resync_starts_outbound_job(self, temp_db):
        interface = MockMeshInterface()
        remote = _setup_rsv1_peers(interface, remote="!requester")

        message = encode_resync_request_message("rsv1")
        _process_rs_sync_message(0, message, interface, remote)

        conn = db_operations.get_db_connection()
        row = conn.execute(
            "SELECT requester_bbs_node, stage FROM peer_resync_outbound"
        ).fetchone()
        assert row == (remote, "bulletins")

    def test_peer_allow_resync_reads_column(self, temp_db):
        db_operations.add_sync_peer("!p1", sync_protocol="rsv1", allow_resync="N")
        peer = db_operations.get_sync_peers()[0]
        assert peer_allow_resync(peer) is False

    def test_resync_request_wire_type(self, temp_db):
        message = encode_resync_request_message("rsv1")
        assert message.startswith("RS|1|RESYNC_REQUEST|")
