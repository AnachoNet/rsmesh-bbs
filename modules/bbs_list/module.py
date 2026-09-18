import logging

from rsmesh_bbs.module_loader import MODULE_RESULT_CONTINUE, MODULE_RESULT_EXIT
from rsmesh_bbs.module_sync import (
    ModuleSyncRegistration,
    get_pending_sync_peers,
    mark_sync_peers_synced,
    reset_record_sync_peers,
)
from rsmesh_bbs.sync_wire import build_rs_message
from rsmesh_bbs.utils import (
    filter_peers_for_record_type,
    get_sync_peer_by_bbs_node,
    send_sync_message,
    sync_peer_bbs_node,
    sync_peer_protocol,
)

from bbs_list import storage

LIST_MENU_PROMPT = "List: [A]ll  [S]ync-Interested  E[X]IT"
BROWSE_FOOTER = "Enter list ID for details. [R]eturn  E[X]IT"
DETAIL_FOOTER = "[R]eturn  E[X]IT"


class Module:
    def __init__(self):
        self._ui_phase = {}

    def on_load(self, ctx):
        storage.configure(ctx.module_dir)
        ctx.register_sync(
            ModuleSyncRegistration(
                module_id=ctx.id,
                record_type=storage.RECORD_TYPE,
                wire_suffixes=(storage.WIRE_SUFFIX,),
                on_inbound_rs=self._ingest_bbs_list_rs,
                sync_pending=self._sync_pending_bbs_list,
                list_unsynced=storage.list_unsynced_items,
            )
        )

    def on_enter(self, sender_id, ctx):
        self._set_phase(sender_id, "menu")
        self._send_list_menu(sender_id, ctx)

    def on_message(self, sender_id, message, ctx):
        text = (message or "").strip()
        key = self._command_key(text)
        phase = self._ui_phase.get(sender_id, "menu")

        if key == "x":
            self._clear_phase(sender_id)
            return MODULE_RESULT_EXIT
        if key == "?":
            self._send_help(sender_id, ctx)
            return MODULE_RESULT_CONTINUE

        if phase == "menu":
            if key == "a":
                self._show_list(sender_id, ctx, sync_only=False)
                return MODULE_RESULT_CONTINUE
            if key == "s":
                self._show_list(sender_id, ctx, sync_only=True)
                return MODULE_RESULT_CONTINUE
            self._send_list_menu(sender_id, ctx, prefix="Choose A, S, or X.\n")
            return MODULE_RESULT_CONTINUE

        if phase == "detail":
            if key == "r":
                self._set_phase(sender_id, "menu")
                self._send_list_menu(sender_id, ctx)
                return MODULE_RESULT_CONTINUE
            ctx.send_user_message(
                sender_id,
                f"Choose R or X.\n{DETAIL_FOOTER}",
            )
            return MODULE_RESULT_CONTINUE

        if phase == "browse":
            if key == "r":
                self._set_phase(sender_id, "menu")
                self._send_list_menu(sender_id, ctx)
                return MODULE_RESULT_CONTINUE
            if text.isdigit():
                entry = storage.get_entry_by_id(text)
                if entry is not None:
                    self._show_detail(sender_id, ctx, entry)
                    return MODULE_RESULT_CONTINUE
            ctx.send_user_message(
                sender_id,
                f"Enter a valid list ID, R, or X.\n{BROWSE_FOOTER}",
            )
            return MODULE_RESULT_CONTINUE

        self._set_phase(sender_id, "menu")
        self._send_list_menu(sender_id, ctx)
        return MODULE_RESULT_CONTINUE

    @staticmethod
    def _command_key(text):
        lowered = (text or "").strip().lower()
        if len(lowered) == 2 and lowered[1] == "x":
            lowered = lowered[0]
        return lowered

    def _set_phase(self, sender_id, phase):
        self._ui_phase[sender_id] = phase

    def _clear_phase(self, sender_id):
        self._ui_phase.pop(sender_id, None)

    def _send_list_menu(self, sender_id, ctx, prefix=""):
        body = f"= {ctx.module_name} =\n"
        if prefix:
            body += prefix
        body += LIST_MENU_PROMPT
        ctx.send_user_message(sender_id, body)

    def _show_detail(self, sender_id, ctx, entry):
        self._set_phase(sender_id, "detail")
        ctx.send_user_message(
            sender_id,
            f"= {ctx.module_name} =\n"
            f"{storage.format_mesh_detail(entry)}\n"
            f"{DETAIL_FOOTER}",
        )

    def _show_list(self, sender_id, ctx, sync_only=False):
        self._set_phase(sender_id, "browse")
        entries = storage.list_entries(sync_only=sync_only)
        title = "Sync-interested boards" if sync_only else "Known boards"
        if not entries:
            ctx.send_user_message(
                sender_id,
                f"= {ctx.module_name} =\n"
                f"No {title.lower()}.\n"
                f"{LIST_MENU_PROMPT}",
            )
            self._set_phase(sender_id, "menu")
            return

        header = f"= {ctx.module_name} =\n{title} ({len(entries)})."
        body_lines = [storage.format_mesh_list_line(entry) for entry in entries]
        footer = BROWSE_FOOTER
        from rsmesh_bbs.utils import bundle_lines_for_mesh

        messages = bundle_lines_for_mesh([header] + body_lines + [footer])
        ctx.send_user_messages(sender_id, messages)

    def _send_help(self, sender_id, ctx):
        ctx.send_user_message(
            sender_id,
            f"= {ctx.module_name} =\n"
            "Directory of mesh BBS boards.\n"
            "* marks sync interest on list lines.\n"
            f"{LIST_MENU_PROMPT}\n"
            f"{BROWSE_FOOTER}\n"
            f"{DETAIL_FOOTER}\n"
            "E[X]IT return to main menu",
        )

    def _ingest_bbs_list_rs(self, msg_type, fields, sender_node_id, interface):
        node_hex = storage.normalize_node_hex(fields.get("uid"))
        existing = storage.get_entry(node_hex) if node_hex else None
        if existing and existing.get("is_local") == "Y":
            logging.info(
                "Ignored BBS_LIST_SYNC for local entry %s from %s.",
                node_hex,
                sender_node_id,
            )
            return
        if not storage.upsert_from_wire(fields):
            logging.warning(
                "Rejected BBS_LIST_SYNC from %s; invalid or incomplete payload.",
                sender_node_id,
            )
            return
        logging.info(
            "Ingested BBS_LIST_SYNC for %s from %s.",
            node_hex or fields.get("uid"),
            sender_node_id,
        )
        peer = get_sync_peer_by_bbs_node(
            sender_node_id,
            getattr(interface, "sync_peers", None),
        )
        if node_hex and peer:
            mark_sync_peers_synced(storage.RECORD_TYPE, node_hex, [peer])

    def _sync_pending_bbs_list(self, peers, interface):
        entries = storage.list_entries()
        if not entries:
            logging.info("BBS_LIST_SYNC: no entries to check.")
            return

        sent_count = 0
        for entry in entries:
            record_key = entry["node_hex"]
            pending = get_pending_sync_peers(
                storage.RECORD_TYPE,
                record_key,
                peers,
                interface,
            )
            if not pending:
                eligible = filter_peers_for_record_type(
                    peers,
                    storage.RECORD_TYPE,
                    interface,
                )
                if eligible:
                    logging.info(
                        "BBS_LIST_SYNC: %s already synced to all eligible peers.",
                        record_key,
                    )
                continue
            message = build_rs_message(1, storage.wire_type(), storage.entry_to_wire(entry))
            synced = []
            for peer in pending:
                bbs_node = sync_peer_bbs_node(peer)
                peer_name = (peer[2] or bbs_node) if len(peer) > 2 else bbs_node
                if send_sync_message(
                    message,
                    bbs_node,
                    interface,
                    sync_peer_protocol(peer),
                ):
                    logging.info(
                        "Sent BBS_LIST_SYNC for %s to %s.",
                        record_key,
                        peer_name,
                    )
                    synced.append(peer)
                    sent_count += 1
                else:
                    logging.warning(
                        "BBS_LIST_SYNC for %s to %s failed.",
                        record_key,
                        peer_name,
                    )
            if synced:
                mark_sync_peers_synced(storage.RECORD_TYPE, record_key, synced)

        if sent_count == 0:
            logging.info(
                "BBS_LIST_SYNC: checked %d entries; no pending peers.",
                len(entries),
            )


def queue_entry_sync(node_hex):
    node_hex = storage.normalize_node_hex(node_hex)
    if node_hex:
        reset_record_sync_peers(storage.RECORD_TYPE, node_hex)
