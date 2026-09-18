import sys
from pathlib import Path

import pytest

MODULES_DIR = Path(__file__).resolve().parent.parent / "modules"
if str(MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR))

from bbs_list import bbs_list_admin
from bbs_list import storage


@pytest.fixture
def bbs_list_db(temp_db, monkeypatch, tmp_path):
    db_path = tmp_path / "bbs_list.db"
    monkeypatch.setattr(storage, "DB_PATH", str(db_path))
    storage.setup_db()
    yield db_path


class TestBbsListEditEntry:
    def test_edit_entry_prompts_peer_sync(self, bbs_list_db, monkeypatch):
        entry_id = storage.upsert_entry(
            "Alpha BBS",
            "!aabbcc01",
            "ALPH",
            sync_interest="Y",
            peer_sync="N",
            is_local="Y",
        )
        prompts = []

        def _fake_paginate(*_args, **_kwargs):
            return 1, str(entry_id)

        def _fake_input(prompt):
            prompts.append(prompt)
            return ""

        monkeypatch.setattr(bbs_list_admin.admin_ui, "paginate_display", _fake_paginate)
        monkeypatch.setattr(bbs_list_admin.admin_ui, "begin_form_screen", lambda *_a, **_k: None)
        monkeypatch.setattr(bbs_list_admin.admin_ui, "print_bold", lambda *_a, **_k: None)
        monkeypatch.setattr(bbs_list_admin.admin_ui, "input_bold", _fake_input)
        monkeypatch.setattr(
            bbs_list_admin.admin_ui,
            "finish_action_message",
            lambda *_a, **_k: None,
        )
        monkeypatch.setattr(bbs_list_admin.bbs_list_module, "queue_entry_sync", lambda *_a: None)

        bbs_list_admin.edit_entry()

        peer_prompts = [p for p in prompts if "Sync this entry to peers" in p]
        assert len(peer_prompts) == 1
        assert "[N]" in peer_prompts[0]
