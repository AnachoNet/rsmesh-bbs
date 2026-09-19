"""rsv1 peer resync requests (admin-queued inbound requests, rate-limited outbound replay)."""

from __future__ import annotations

import logging
import time

from .db_operations import (
    PEER_ALLOW_RESYNC_INDEX,
    get_db_connection,
    get_mesh_nodes_for_sync,
    get_sync_protocol_for_peer,
    _core_sync_enabled,
)
from .sync_wire import (
    dedupe_mesh_node_entries,
    encode_resync_request_message,
    is_rs_sync_protocol,
    plan_nodes_sync_batches,
)
from .utils import (
    filter_peers_for_record_type,
    get_sync_peer_by_bbs_node,
    peer_sync_enabled,
    send_bulletin_to_sync_peers,
    send_channel_to_bbs_nodes,
    send_mail_to_bbs_nodes,
    send_mesh_nodes_batch_to_peer,
    send_sync_message,
    sync_peer_protocol,
    _peer_id_from_peer,
)

RESYNC_OUTBOUND_STEP_DELAY_SECONDS = 2.0
_RESYNC_STAGES = ("bulletins", "mail", "channels", "mesh_nodes", "modules", "done")


def peer_allow_resync(peer) -> bool:
    if peer is None:
        return False
    if len(peer) <= PEER_ALLOW_RESYNC_INDEX:
        return True
    return (peer[PEER_ALLOW_RESYNC_INDEX] or "Y").strip().upper() == "Y"


def queue_peer_resync_request(target_bbs_node: str) -> bool:
    target_bbs_node = (target_bbs_node or "").strip()
    if not target_bbs_node:
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO pending_resync_requests (target_bbs_node, status, created) "
        "VALUES (?, 'pending', datetime('now'))",
        (target_bbs_node,),
    )
    conn.commit()
    return True


def _fetch_pending_resync_requests():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, target_bbs_node FROM pending_resync_requests "
        "WHERE status = 'pending' ORDER BY id"
    )
    return c.fetchall()


def _mark_resync_request_status(request_id, status):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE pending_resync_requests SET status = ? WHERE id = ?",
        (status, request_id),
    )
    conn.commit()


def process_pending_resync_requests(interface) -> None:
    if interface is None:
        return
    sync_peers = getattr(interface, "sync_peers", None) or []
    for request_id, target_bbs_node in _fetch_pending_resync_requests():
        peer = get_sync_peer_by_bbs_node(target_bbs_node, sync_peers)
        if peer is None:
            _mark_resync_request_status(request_id, "skipped")
            continue
        protocol = sync_peer_protocol(peer)
        if not is_rs_sync_protocol(protocol):
            _mark_resync_request_status(request_id, "skipped")
            continue
        try:
            message = encode_resync_request_message(protocol)
        except ValueError:
            _mark_resync_request_status(request_id, "failed")
            continue
        if send_sync_message(
            message,
            target_bbs_node,
            interface,
            sync_protocol=protocol,
        ):
            _mark_resync_request_status(request_id, "sent")
            logging.info("Sent RESYNC_REQUEST to peer %s.", target_bbs_node)
        else:
            logging.warning(
                "RESYNC_REQUEST to %s failed; will retry while pending.",
                target_bbs_node,
            )


def handle_inbound_resync_request(sender_node_id, interface) -> None:
    if interface is None:
        return
    if not is_rs_sync_protocol(get_sync_protocol_for_peer(sender_node_id) or "tc2"):
        logging.info(
            "Ignoring RESYNC_REQUEST from non-RS peer %s.",
            sender_node_id,
        )
        return
    sync_peers = getattr(interface, "sync_peers", None) or []
    peer = get_sync_peer_by_bbs_node(sender_node_id, sync_peers)
    if peer is None:
        logging.info(
            "Ignoring RESYNC_REQUEST from unknown peer %s.",
            sender_node_id,
        )
        return
    if not peer_allow_resync(peer):
        logging.info(
            "RESYNC_REQUEST from %s denied (allow_resync=N).",
            sender_node_id,
        )
        return
    _start_outbound_resync_job(sender_node_id)
    logging.info(
        "Accepted RESYNC_REQUEST from %s; outbound resync queued (rate-limited).",
        sender_node_id,
    )


def _start_outbound_resync_job(requester_bbs_node: str) -> None:
    requester_bbs_node = (requester_bbs_node or "").strip()
    if not requester_bbs_node:
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO peer_resync_outbound "
        "(requester_bbs_node, stage, stage_cursor, mesh_batch_index, updated) "
        "VALUES (?, 'bulletins', 0, 0, ?)",
        (requester_bbs_node, int(time.time())),
    )
    conn.commit()


def _load_outbound_resync_job():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT requester_bbs_node, stage, stage_cursor, mesh_batch_index "
        "FROM peer_resync_outbound ORDER BY updated LIMIT 1"
    )
    return c.fetchone()


def _save_outbound_resync_job(
    requester_bbs_node,
    stage,
    stage_cursor,
    mesh_batch_index,
):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE peer_resync_outbound SET stage = ?, stage_cursor = ?, "
        "mesh_batch_index = ?, updated = ? WHERE requester_bbs_node = ?",
        (stage, stage_cursor, mesh_batch_index, int(time.time()), requester_bbs_node),
    )
    conn.commit()


def _clear_outbound_resync_job(requester_bbs_node):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM peer_resync_outbound WHERE requester_bbs_node = ?",
        (requester_bbs_node,),
    )
    conn.commit()


def _mark_module_records_unsynced_for_peer(peer_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE record_sync_peers SET synced = 'N' "
        "WHERE peer_id = ? AND record_type LIKE 'module:%'",
        (peer_id,),
    )
    conn.commit()


def _advance_resync_stage(stage):
    try:
        index = _RESYNC_STAGES.index(stage)
    except ValueError:
        return "done"
    if index + 1 >= len(_RESYNC_STAGES):
        return "done"
    return _RESYNC_STAGES[index + 1]


def _resync_outbound_step(requester_bbs_node, stage, stage_cursor, mesh_batch_index, interface):
    sync_peers = getattr(interface, "sync_peers", None) or []
    peer = get_sync_peer_by_bbs_node(requester_bbs_node, sync_peers)
    if peer is None:
        return "done", 0, 0, True

    single_peer = [peer]
    if stage == "bulletins":
        if not _core_sync_enabled("bulletins") or not peer_sync_enabled(
            peer, "bulletins", interface
        ):
            return _advance_resync_stage(stage), 0, 0, False
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT board, sender_short_name, subject, content, unique_id, pinned "
            "FROM bulletins WHERE deleted = 'N' AND id > ? ORDER BY id LIMIT 1",
            (stage_cursor,),
        )
        row = c.fetchone()
        if row is None:
            return _advance_resync_stage(stage), 0, 0, False
        board, sender_short_name, subject, content, unique_id, pinned = row
        c.execute("SELECT id FROM bulletins WHERE unique_id = ?", (unique_id,))
        bulletin_id = c.fetchone()[0]
        ok = send_bulletin_to_sync_peers(
            board,
            sender_short_name,
            subject,
            content,
            unique_id,
            single_peer,
            interface,
            pinned=pinned or "N",
        )
        if not ok:
            return stage, stage_cursor, mesh_batch_index, True
        return stage, bulletin_id, mesh_batch_index, False

    if stage == "mail":
        if not _core_sync_enabled("mail") or not peer_sync_enabled(peer, "mail", interface):
            return _advance_resync_stage(stage), 0, 0, False
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT sender, sender_short_name, recipient, recipient_short_name, "
            "subject, content, unique_id FROM mail WHERE id > ? ORDER BY id LIMIT 1",
            (stage_cursor,),
        )
        row = c.fetchone()
        if row is None:
            return _advance_resync_stage(stage), 0, 0, False
        (
            sender_id,
            sender_short_name,
            recipient_id,
            recipient_short_name,
            subject,
            content,
            unique_id,
        ) = row
        c.execute("SELECT id FROM mail WHERE unique_id = ?", (unique_id,))
        mail_id = c.fetchone()[0]
        ok = send_mail_to_bbs_nodes(
            sender_id,
            sender_short_name,
            recipient_id,
            recipient_short_name,
            subject,
            content,
            unique_id,
            single_peer,
            interface,
        )
        if not ok:
            return stage, stage_cursor, mesh_batch_index, True
        return stage, mail_id, mesh_batch_index, False

    if stage == "channels":
        if not _core_sync_enabled("channels") or not peer_sync_enabled(
            peer, "channels", interface
        ):
            return _advance_resync_stage(stage), 0, 0, False
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id, name, psk, unique_id FROM channels "
            "WHERE publish = 'Y' AND deleted = 'N' AND id > ? ORDER BY id LIMIT 1",
            (stage_cursor,),
        )
        row = c.fetchone()
        if row is None:
            return _advance_resync_stage(stage), 0, 0, False
        channel_id, name, psk, unique_id = row
        ok = send_channel_to_bbs_nodes(
            name, psk, single_peer, interface, unique_id=unique_id
        )
        if not ok:
            return stage, stage_cursor, mesh_batch_index, True
        return stage, channel_id, mesh_batch_index, False

    if stage == "mesh_nodes":
        if not peer_sync_enabled(peer, "mesh_nodes", interface):
            return _advance_resync_stage(stage), 0, 0, False
        mesh_peers = filter_peers_for_record_type(single_peer, "mesh_nodes", interface)
        if not mesh_peers:
            return _advance_resync_stage(stage), 0, 0, False
        all_nodes = get_mesh_nodes_for_sync()
        if not all_nodes:
            return _advance_resync_stage(stage), 0, 0, False
        pending = dedupe_mesh_node_entries(
            [
                (node_id, short_name, long_name, last_heard)
                for node_id, short_name, long_name, last_heard in all_nodes
            ]
        )
        batches = plan_nodes_sync_batches(pending, sync_peer_protocol(peer))
        if mesh_batch_index >= len(batches):
            return _advance_resync_stage(stage), 0, 0, False
        batch = batches[mesh_batch_index]
        ok = send_mesh_nodes_batch_to_peer(batch, peer, interface)
        if not ok:
            return stage, stage_cursor, mesh_batch_index, True
        next_batch = mesh_batch_index + 1
        if next_batch >= len(batches):
            return _advance_resync_stage(stage), 0, 0, False
        return stage, 0, next_batch, False

    if stage == "modules":
        peer_id = _peer_id_from_peer(peer)
        if peer_id is None:
            return "done", 0, 0, True
        if stage_cursor == 0:
            _mark_module_records_unsynced_for_peer(peer_id)
        from .db_operations import _sync_module_pending_records

        before = stage_cursor
        _sync_module_pending_records(single_peer, interface)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM record_sync_peers rsp "
            "JOIN sync_peers sp ON sp.id = rsp.peer_id "
            "WHERE rsp.peer_id = ? AND rsp.record_type LIKE 'module:%' AND rsp.synced = 'N'",
            (peer_id,),
        )
        pending_modules = c.fetchone()[0]
        if pending_modules > 0:
            return stage, before + 1, 0, False
        return "done", 0, 0, False

    return "done", 0, 0, True


def advance_resync_outbound(interface, max_steps: int = 1) -> None:
    if interface is None:
        return
    for _ in range(max_steps):
        job = _load_outbound_resync_job()
        if job is None:
            return
        requester_bbs_node, stage, stage_cursor, mesh_batch_index = job
        if stage == "done":
            _clear_outbound_resync_job(requester_bbs_node)
            continue
        next_stage, next_cursor, next_mesh_batch, stop = _resync_outbound_step(
            requester_bbs_node,
            stage,
            stage_cursor,
            mesh_batch_index,
            interface,
        )
        if next_stage == "done":
            _clear_outbound_resync_job(requester_bbs_node)
            logging.info(
                "Completed outbound resync to %s.",
                requester_bbs_node,
            )
            return
        _save_outbound_resync_job(
            requester_bbs_node,
            next_stage,
            next_cursor,
            next_mesh_batch,
        )
        if stop:
            return
        time.sleep(RESYNC_OUTBOUND_STEP_DELAY_SECONDS)
