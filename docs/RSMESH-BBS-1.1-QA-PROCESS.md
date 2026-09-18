# RSMesh BBS 1.1 — QA Process

Release target: **1.1**  
Document purpose: operator checklist for full regression testing before release sign-off.  

**Phases:** 1 Install/upgrade → 2 User mesh → 3 Sysadmin + admin → 4 rsv1 peer setup → 5 rsv1 sync → **6 RSMesh ↔ TC² interop**

Companion docs: [UPGRADING.md](UPGRADING.md), [RSMESH-BBS-SYSOP-GUIDE.md](RSMESH-BBS-SYSOP-GUIDE.md), [RSMESH-BBS-USER-GUIDE.md](RSMESH-BBS-USER-GUIDE.md)

---

## Test environment

| Item                                | Machine A      | Machine B         |
| ----------------------------------- | -------------- | ----------------- |
| Host name / label                   | msh-rpi01      | msh-rpi02         |
| Meshtastic node ID                  | !9e9d8704      | !3369e6e4         |
| Short name                          | RSNA           | RSNT              |
| Board name (`bbs.board_name`)       | MeshBBS01      | MeshBBS02         |
| Install path                        | /opt/rsmesh    | /opt/tc2-mesh-bbs |
| Branch tested (record per phase)    |                |                   |
| Radio connection (`serial` / `tcp`) | /dev/ttyUSB0   | /dev/ttyUSB0      |
| Phase 6 role                        | RSMesh **1.1** | Stock **TC²-BBS** |

**Mesh client identities** (for Phases 2–3; `config_client.yml` per workstation):

| Role          | Node ID   | Short name | Sysadmin? |
| ------------- | --------- | ---------- | --------- |
| Regular user  | !66983fe3 | RSM1       | No        |
| Sysadmin user | !3369f68c | RSN1       | Yes       |

**Notes (environment setup):**

```
Run as user: bbs

sudo useradd -m -s /bin/bash bbs

sudo usermod -a -G dialout bbs

sudo chown -R bbs:bbs /opt/TC2-BBS-mesh

sudo chown -R bbs:bbs /opt/rsmesh-bbs

sudo -i

su - bbs
```

---

## Conventions

- `[ ]` = not tested / failed — leave unchecked until pass
- Record failures inline under **Notes**; include date, branch, and log snippet if helpful
- **Admin** = `rsmesh-bbs_admin.py`
- **Client** = `rsmesh-bbs_client.py --fast` (add `-v` when debugging silent paths)
- **Server** = `rsmesh-bbs_server.py` with venv activated
- After admin changes to sync peers or sysadmin nodes, confirm the running server picks them up (next mesh message or worker cycle)

---

## Phase 1 — Install and upgrade paths

Goal: validate TC² migration, 1.0 → 1.1 upgrade, and fresh TC² → 1.1 on two independent systems.

### 1.1 Baseline — reinstall TC² on both machines

- [x] Remove or archive prior RSMesh install (keep backup if needed)
- [x] Install stock [TC²-BBS-Mesh](https://github.com/TheCommsChannel/TC2-BBS-mesh) on **Machine A**
- [x] Install stock TC² on **Machine B**
- [x] Confirm each TC² server starts and accepts mesh/client traffic
- [x] Seed distinctive test data on each (at least one bulletin, one mail message, one channel if supported)

**Notes:**

```

```

### 1.2 Upgrade Machine A to release 1.0

- [x] Clone/checkout `1.0` branch; create venv; `pip install -r requirements.txt`
- [x] Place existing TC² `config.ini` and `bulletins.db` in project directory
- [x] Start server; confirm migration messages (`config.ini` → `config.yml`, `bulletins.db` → `rsmesh-bbs.db`)
- [x] Verify migrated bulletins and config values
- [x] Confirm `[sync] bbs_nodes` imported to `sync_peers` with **all sync flags N** (sync disabled until admin enables)
- [x] Confirm `[allow_list]` imported to `sysadmin_nodes` where applicable
- [x] Smoke-test server starts cleanly after restart

**Notes:**

```

```

### 1.3 Upgrade both machines to release 1.1

**Machine A (from 1.0):**

- [x] Pull/checkout `1.1`; reinstall dependencies if `requirements.txt` changed
- [x] Start server; confirm 1.1 schema/sys_config seeding (no data loss)
- [x] Confirm new default modules appear (Node Info, Fortune, BBS List, Example Hello row)
- [x] Confirm `mesh_ui/main_menu.txt` regenerated or valid
- [x] Confirm `admin.server_log_file` seeded (`rsmesh-bbs.log`); log file created on server start
- [x] Review [changelog.txt](../changelog.txt) items relevant to upgrade

**Machine B (TC² → 1.1 direct):**

- [x] Fresh `1.1` install over TC² files (no prior RSMesh DB)
- [x] Confirm TC² migration path same as UPGRADING.md
- [x] Confirm 1.1-only features present (core services, module sync tables, etc.)
- [x] Smoke-test server starts cleanly after restart

**Notes:**

```
On 1.1 direct upgrade from TC2: Screen flash when exporting config.yml.

Notes to operators: On upgrades may want to disable sync peers before upgrade and until protocol changes, etc. are complete. After upgrades, sync traffic might be heavy, particularly node updates (if node sync enabled). Also, check BBS and Interface configs for unset values (values absent on previous deployment).
```

### 1.4 Phase 1 exit criteria

- [x] Both machines run **1.1** server without errors
- [x] Admin tool opens on both; splash shows expected counts
- [x] **System Status → [V]iew server log** works (Ctrl-C returns); log shows startup lines
- [x] No unintended overwrite of pre-existing `config.yml` / `rsmesh-bbs.db` on re-run

**Notes:**

```

```

---

## Phase 2 — Mesh client testing (regular user)

Goal: exercise every core service and shipped module menu path as a **non-sysadmin** handset. Use **Client** with the regular-user identity.

**Preparation:**

- [x] Enable all core services: **Admin → Core Services** (Bulletins, Mail, Channels = Enabled)
- [x] Enable shipped modules: Node Info, Fortune, BBS List (Example Hello optional)
- [x] Confirm main menu shows `[B]`, `[C]`, `[M]`, M[o]dules (`O`), `E[X]IT`
- [x] Do **not** grant sysadmin to the test client node yet

### 2.1 Main menu and help

- [x] Send any message to open main menu
- [x] Confirm menu matches `mesh_ui/main_menu.txt` / board name banner
- [x] `X` or invalid key behavior acceptable
- [x] `?` / help if applicable

**Notes:**

```
Lost messages can leave user confused. 
Possible to have message with only "?" repeat last message sent?
```

### 2.2 Bulletins (user)

- [x] `B` → board menu: General, Info, News, Urgent visible
- [x] `G` / `I` / `N` → Read: list, open bulletin, `X` back
- [x] Post to **General**: subject + multi-line body, `END` terminator
- [x] Post to **Info** and **News**
- [x] **Urgent**: confirm regular user **denied** (sysadmin required)
- [x] Confirm **no** `[D]elete` option for regular user
- [x] Pinned vs aged bulletin display (if test data spans `bulletin_display_age_days`)

**Admin visibility (no action yet — observe later):**

- [x] New posts appear in **Admin → Bulletins → List**

**Notes:**

```

```

### 2.3 Mail (user)

- [x] `M` → `R` Read: empty inbox message vs populated inbox
- [x] Read message: `K` keep, `D` delete own mail, `R` reply flow
- [x] `M` → `S` Send: recipient by short name; multi-line body + `END`
- [x] Send to peer short name (second client identity on other machine optional in Phase 2)
- [x] Empty inbox returns to mail submenu (not main menu)

**Admin visibility:**

- [x] Sent/received mail in **Admin → Mail → List**

**Notes:**

```
After "No messages.", send mail menu again.
Handset will receive 
"New mail from RSN3. Type HELP and press R to read mail.", however,
typing "HELP" gets main menu, and R is not a valid option by default. 
Maybe restore/add "RM" as quick command to read mail.
Consider compact list for read mail.  Separate msgs will be painful
with large mailboxes.
```

### 2.4 Channels (user)

- [x] `C` → View (`V`): list published channels only
- [x] View detail: name + PSK shown
- [x] Post (`P`): submit name + PSK for operator review
- [x] Confirm posted channel **not** visible in mesh View until published

**Admin visibility (Phase 3):**

- [x] Unpublished channel in **Admin → Channels → List** (`publish=N`)

**Notes:**

```

```

### 2.5 Modules — Fortune (`F`)

- [x] `O` → `F`: fortune displayed on entry
- [x] Any message fetches another fortune
- [x] `X` exits to modules or main menu

**Notes:**

```

```

### 2.6 Modules — Node Info (`I`)

- [x] `O` → `I`: `[N]odes` counts by time window
- [x] `[H]ardware` model counts
- [x] `[R]oles` role counts
- [x] Confirm **no** `[L]ist Nodes` (sysadmin only)
- [x] `X` exits

**Notes:**

```

```

### 2.7 Modules — BBS List (`L`)

- [x] `O` → `L`: All boards list (`A` if needed)
- [x] `[S]ync` list shows sync-interested only; `*` marker on interested rows
- [x] Enter **list ID** → detail view
- [x] `?` help, `X` exit

**Notes:**

```
Remove "?" option.  Make "x" from bbs detail re-display list.  Make
"x" return to menu.
```

### 2.8 Optional — Example Hello (if enabled)

- [x] Enable in **Admin → Modules** temporarily
- [x] Mesh entry greets; visit recorded
- [x] Disable again if not part of release scope

**Notes:**

```

```

### 2.9 Core Services toggles (mesh menu visibility)

Repeat a subset after each toggle; restore all enabled at end.

- [x] Disable **Mail** → `[M]ail` hidden on mesh main menu; re-enable
- [x] Disable **Bulletins** → `[B]ulletins` hidden; re-enable
- [x] Disable **Channels** → `[C]hannels` hidden; re-enable
- [x] Toggle **Display Mail commands on Main Menu** → `[R]`/`[S]` on main menu vs `[M]` submenu

**Notes:**

```
NOTE: Toggle R/S on main menu will require edit to menu text, or 
regenerate menu.
```

### 2.10 Phase 2 exit criteria

- [x] All checked paths work without server traceback in `rsmesh-bbs.log`
- [x] User guide behavior matches observation ([RSMESH-BBS-USER-GUIDE.md](RSMESH-BBS-USER-GUIDE.md))

**Notes:**

```
See notes for issues/feature gaps.
```

---

## Phase 3 — Sysadmin mesh + admin tool

Goal: grant sysadmin; test elevated mesh actions and every admin screen needed for **approval, visibility, and configuration**.

### 3.1 Grant sysadmin

- [x] **Admin → Sysadmin Nodes → Add** regular-user node (Phase 2 client)
- [x] Optionally set `bbs.superuser_node` in **System Configuration → BBS** if testing Urgent + superuser combo
- [x] Restart client; confirm sysadmin menus appear on mesh

**Notes:**

```

```

### 3.2 Bulletins (sysadmin mesh)

- [x] Post to **Urgent** board succeeds
- [x] `[D]elete` on board → select bulletin → soft-delete
- [ ] If `send_urgent_alert_local=true`: urgent post triggers primary-channel alert (or queued for server)

**Admin follow-up:**

- [x] **List Bulletins** shows deleted flag / sync label
- [x] **Edit Bulletin**: pin/unpin; confirm sync label changes to pending (rsv1)
- [x] **Delete Bulletins** (admin) soft-deletes
- [ ] **Review Reconcile Bulletins** (after Phase 5 delete sync) — defer if empty

**Notes:**

```
Feature: Make it possible to send to channels other than PRIMARY for
Urgent bulletins.  Bug: Bulletin delete in admin: message is truncated:
"Bulletin(s) with ID(s) 6 marked for deletion. The BBS server will purge and"
 - Should break to 2 lines.
 BUG: Seen on test server: Note duplicate guid.
 News:
  ID: 3  Poster: RSN1  Subject: News Bulletin RSNA  Date: 2026-09-13 05:11
    UID: 64155208-389b-40d2-bda1-63ed4bc822ed  Del: N  Pinned: N  Reconcile: N
  ID: 7  Poster: RSN1  Subject: News Bulletin RSNA  Date: 2026-09-13 17:29
    UID: 64155208-389b-40d2-bda1-63ed4bc822ed  Del: N  Pinned: N  Reconcile: N
BUG?: Review reconcile did not show data deleted on distant server.  
Delete was processed on sync peer without approval.
```

### 3.3 Channels (admin approval)

- [x] Approve user-posted channel: **Edit Channel** → `publish=Y`
- [x] Mesh View now shows channel
- [x] **Add Channel** directly with publish Y/N
- [x] **Delete Channels** / **Export / Import CSV** smoke test
- [ ] **Review Reconcile Channels** when applicable

**Notes:**

```
Channels added in admin tool do not display "Publish" prompt.  Default
to "y".  Channel delete on sync peer skipped in processing for duplicate
unique id.  Did not appear in reconcile list.
```

### 3.4 Mail (admin)

- [x] **List / Send / Edit / Delete** mail
- [x] Forwarding test if `mail_forward_to` configured in node catalog

**Notes:**

```

```

### 3.5 Node Catalog and Mesh Nodes (admin)

- [x] **Node Catalog**: add, edit, delete, export/import CSV
- [x] Confirm `bbs_admin=Y` on catalog row syncs sysadmin when applicable
- [x] **Mesh Nodes**: list, add, edit, delete, purge, export/import CSV

**Notes:**

```
Mesh node reference by hex node id is cumbersome.
```

### 3.6 Modules (admin)

- [x] **List Modules** — flags match expected defaults
- [x] **Edit Module Flags**: enable/disable, schedule, **Show on main menu**
- [x] **Suppress Modules Submenu** (only when all enabled modules promoted)
- [x] **Regenerate Main Menu** after hand-editing `mesh_ui/main_menu.txt`
- [x] **Node Info → List Node Info** (view-only)
- [x] **BBS List admin**: Register This BBS, Add, Edit (paginated ID pick), Delete, List Sync Interested

**Notes:**

```
Edit module should show module name on input screen.
Moving all modules to main menu does not suppress modules option.
Update to main menu text requires regenerate (moving modules to main as
well as suppressing sub-menu).
List nodes (sysadmin) may be too heavy with manu nodes.  Consider 
filtering.
```

### 3.7 System Configuration and Core Services

- [x] **System Configuration**: edit BBS, Interface, Schedule keys (type-aware editors)
- [x] **Export Configuration to config.yml** (confirm overwrite prompt)
- [x] **Core Services**: toggle each service; leave all **Enabled** before Phase 4
- [x] **Backup** creates zip under `backup/`

**Notes:**

```
Export to yaml has screen flash.
```

### 3.8 System Status and logging

- [x] **System Status** counts match splash / database
- [x] Sync peer list shown when configured (Phase 4)
- [x] **[V]iew server log (Ctrl-C to return)** tails `rsmesh-bbs.log`
- [ ] Sync alert summary line (RS version / module peers) when applicable

**Notes:**

```
Sync peer status shows no pending, but review/reconcile seems to have
issues, so this test may not be valid.
```

### 3.9 Phase 3 exit criteria

- [x] Sysadmin mesh capabilities match user guide
- [x] All admin menus navigable; no crashes
- [x] Channel approval workflow complete (mesh post → admin publish → mesh view)

**Notes:**

```
Reconcile seems to have issues.
```

---

## Phase 4 — Sync peer configuration

Goal: pair Machine A and Machine B as **rsv1** peers with all sync options enabled. Complete on **both** machines.

### 4.1 Peer definitions

On **Machine A**, add peer = Machine B:

- [x] **Admin → Sync Peers → Add**
- [x] BBS node ID = Machine B node
- [x] Protocol = **rsv1**
- [x] Enabled = **Y**
- [x] Out: bulletins **Y**, channels **Y**, mail **Y**, mesh nodes **Y**
- [x] In: bulletins **Y**, channels **Y**
- [x] Per-module: **BBS List** sync out **Y**, ingest in **Y** (and any other registered sync modules)
- [x] Repeat mirror config on **Machine B** → Machine A

**Notes:**

```

```

### 4.2 Pre-sync verification

- [x] **List Sync Peers** — four lines per peer; `Modules: Y` on line 3 for rsv1
- [ ] **List Unsynced Data** — baseline snapshot (existing local records may show pending)
- [ ] Clear stale module sync state if re-testing BBS List:  
  `DELETE FROM record_sync_peers WHERE record_type = 'module:bbs_list';` (both sides, only if needed)
- [x] Server running on both; radios reach each other
- [x] Note `peer_sync_minutes` (default 5) and mesh node delay (~90s after other sync)

**Notes:**

```
Sync peer list is actually 3 lines.  List unsynched data may be bugged.
See other notes regarding review/reconcile.
```

### 4.3 Phase 4 exit criteria

- [x] Both peers listed, enabled, rsv1, all flags Y
- [x] Server logs show sync worker started on both

**Notes:**

```

```

---

## Phase 5 — Sync testing (core + modules)

Goal: verify bidirectional sync, deletes, reconcile, and module wire types. Monitor **server logs** on both sides during tests.

### 5.1 Bulletins (rsv1)

**A → B:**

- [x] Post bulletin on A; within sync cycle appears on B (mesh or admin list)
- [x] **Edit** bulletin on A (subject or **Pinned**); update appears on B (rsv1 upsert)
- [x] Admin **List Bulletins** sync label → `Y` when complete

**B → A:**

- [x] Repeat reverse direction

**Delete + reconcile:**

- [ ] Delete bulletin on A (mesh sysadmin or admin); after purge cycle B marks reconcile
- [ ] **Admin → Review Reconcile Bulletins** on B: restore or confirm delete
- [ ] **List Unsynced Data** empty for that record when fully synced

**Notes:**

```
Delete + reconcile: Distant peer seems to process immediately.  Change
does not display in review/reconcile, and action is taken on distant
peer as though change has been approved.
```

### 5.2 Mail

- [x] Send mail A → B; appears in B inbox (mesh + admin)
- [x] Send mail B → A
- [x] Delete mail on one side; delete sync received on peer
- [x] Sync labels on admin mail list

**Notes:**

```

```

### 5.3 Channels

- [x] Publish channel on A; ingests on B as **unpublished** (`publish=N`)
- [x] Admin publish on B; visible on B mesh
- [ ] Delete channel on A; reconcile on B
- [ ] **Review Reconcile Channels** workflow

**Notes:**

```
Review/reconcile issues.
```

### 5.4 Mesh nodes (NODES batch, deferred)

- [x] Ensure nodes heard on each system (live traffic or manual mesh node rows)
- [x] Wait full cycle: core/module sync first, log line `Waiting 90 seconds before mesh nodes sync`, then `Mesh nodes sync to ... N batch(es)`
- [x] Peer receives **NODES** ingest; **Admin → Mesh Nodes** updated
- [x] Duplicate node IDs dedupe (newest `last_heard` wins) if testable

**Notes:**

```

```

### 5.5 BBS List module sync

- [x] **Register This BBS** on A and B (local entries)
- [x] Server log: `Sent BBS_LIST_SYNC` on sender; `Received message` + `Processing BBS_LIST_SYNC` + `Ingested` on receiver
- [x] Mesh **BBS List** on peer shows remote board
- [x] Edit local entry on A; re-syncs to B
- [x] Inbound echo of own local entry does **not** mark peer synced incorrectly (no stuck “already synced”)
- [x] **List Unsynced Data → Modules** section when pending
- [ ] Module sync restrictions: set BBS List out=N on one peer; confirm no send

**Notes:**

```
BUG: Sync flag missing from edit module flags screen.
```

### 5.6 Sync health and edge cases

- [ ] **List Sync Peers** RS version alert if wire mismatch simulated (optional)
- [x] Disable peer **Enabled=N**; confirm sync pauses; re-enable resumes
- [x] Disable core service (e.g. Mail); confirm mail sync skipped inbound/outbound
- [ ] Urgent ingest: with `send_urgent_alert_from_sync=true`, urgent from peer triggers alert (optional)

**Notes:**

```
If one peer has sync on and the other has sync off, peer with sync
on marks items sycned.  Not sure if this can be addressed in-line.
Consider possibility of forced re-sync with peer - maybe just for 
items within a particular timeframe.
```

### 5.7 Phase 5 exit criteria

- [x] All enabled record types sync bidirectionally
- [ ] Deletes and reconcile paths verified
- [x] BBS List module sync reliable across restarts
- [x] No unexplained gaps in server logs for send without receive
- [x] **List Unsynced Data** accurate after steady-state

**Notes:**

```
Reconcile has issues.
```

---

## Phase 6 — RSMesh 1.1 ↔ TC² interop

Goal: verify **tc2** pipe-delimited sync between **RSMesh 1.1** (Machine A) and a stock **TC²-BBS** peer (Machine B). This is the expected production pattern — operators are not expected to run tc2 between two RSMesh nodes.

Run after Phase 5, or on a dedicated TC² install of Machine B while Machine A keeps its 1.1 peer list.

**tc2 expectations on the RSMesh side:**

| Feature                      | TC² peer                                                                    |
| ---------------------------- | --------------------------------------------------------------------------- |
| Wire format                  | `BULLETIN\|`, `MAIL\|`, `CHANNEL\|`, `DELETE_*` (single 200-byte packet)    |
| Bulletins                    | **Create-only** by `unique_id` — edits and pin changes do **not** propagate |
| Channels                     | Ingest always **unpublished** on RSMesh; operator must publish locally      |
| Mail                         | Bidirectional create/delete sync                                            |
| Mesh nodes                   | **Not supported** (forced **N** on tc2 peer)                                |
| Module sync (BBS List, etc.) | **Not supported** (`Module sync: N/A`)                                      |

**Topology:**

| Machine | Software          | Phase 6 role                |
| ------- | ----------------- | --------------------------- |
| **A**   | RSMesh **1.1**    | tc2 sync peer → TC² node    |
| **B**   | Stock **TC²-BBS** | tc2 sync peer → RSMesh node |

**Notes:**

```

```

### 6.1 Peer setup (both sides)

**RSMesh (Machine A):**

- [ ] Complete Phase 5 first **or** add a **second** sync peer row for TC² (leave rsv1 peer intact if reusing hardware)
- [ ] **Admin → Sync Peers → Add** (or Edit if replacing test peer)
- [ ] BBS node = TC² node ID; protocol = **tc2**
- [ ] Enabled = **Y**; bulletins/mail/channels in/out = **Y** as needed
- [ ] Confirm **Mesh nodes: N** and **Module sync: N/A (rsv1 only)**
- [ ] **List Sync Peers** — protocol `tc2`, no module restriction line

**TC² (Machine B):**

- [ ] `config.ini` → `[sync]` `bbs_nodes` includes RSMesh node ID
- [ ] Enable sync flags per TC² documentation (bulletins, mail, channels)
- [ ] Restart TC² server; confirm it sees RSMesh as sync peer
- [ ] Note TC² sync interval / behavior for timing expectations

**Notes:**

```

```

### 6.2 Bulletins — create-only (tc2)

Use a **new** bulletin with a known `unique_id` (RSMesh admin list shows UID).

**RSMesh → TC²:**

- [ ] Post bulletin on RSMesh (mesh or admin); appears on TC² within sync cycle
- [ ] RSMesh log: outbound pipe `BULLETIN|` (not `RS|1|BULLETIN`)
- [ ] **Edit** or **pin** bulletin on RSMesh; wait sync cycle
- [ ] Confirm TC² still shows **original** content (create-only — no upsert)

**TC² → RSMesh:**

- [ ] Post bulletin on TC²; ingests on RSMesh (admin **List Bulletins** or mesh read)
- [ ] RSMesh log: pipe ingest (not RS decoder)
- [ ] Edit on TC² (if supported); confirm RSMesh copy unchanged

**Duplicate ingest:**

- [ ] Re-send same `unique_id`; RSMesh does not duplicate row

**Notes:**

```

```

### 6.3 Bulletins — delete and reconcile

**RSMesh deletes → TC²:**

- [ ] Soft-delete bulletin on RSMesh; `DELETE_BULLETIN|` reaches TC²
- [ ] Verify TC² handling (reconcile or remove per TC² behavior)

**TC² deletes → RSMesh:**

- [ ] Delete bulletin on TC²; RSMesh marks **delete_reconcile=Y**
- [ ] **Admin → Review Reconcile Bulletins** on RSMesh: **Restore**, then **Confirm delete**

**Notes:**

```

```

### 6.4 Mail (tc2)

- [ ] Send mail RSMesh → TC²; appears on TC² (mesh or TC² admin)
- [ ] Send mail TC² → RSMesh; appears in RSMesh inbox (mesh + admin)
- [ ] Delete mail on RSMesh; TC² copy removed (or note TC² behavior)
- [ ] Delete mail on TC²; RSMesh copy removed
- [ ] Keep bodies short (tc2 single-packet 200-byte limit); note failures on long content

**Notes:**

```

```

### 6.5 Channels (tc2)

- [ ] Publish channel on RSMesh (`publish=Y`); ingests on TC² per TC² rules
- [ ] Post/publish channel on TC²; ingests on RSMesh with **publish=N**
- [ ] RSMesh mesh **View** does not show channel until RSMesh admin sets `publish=Y`
- [ ] Delete channel on one side; reconcile or delete behavior on the other

**Notes:**

```

```

### 6.6 RSMesh-only features (must not sync to TC²)

- [ ] **No** mesh-node rows added on RSMesh from TC² peer traffic
- [ ] **No** `BBS_LIST_SYNC` or other module wire traffic to TC² peer
- [ ] **List Unsynced Data** on RSMesh — no **Modules** section pending for TC² peer
- [ ] BBS List **Register This BBS** on RSMesh does not appear on TC²
- [ ] RSMesh does **not** send `RS|1|…` wire to tc2 peer (logs show pipes only)

**Notes:**

```

```

### 6.7 Phase 6 exit criteria

- [ ] Bulletin **create** syncs both directions; **edit/pin do not** cross the link
- [ ] Delete + reconcile (or TC²-equivalent) verified for bulletins
- [ ] Mail send and delete work both directions within packet limits
- [ ] Channel ingest/publish rules correct on RSMesh side
- [ ] No RSMesh module or mesh-node leakage to TC² peer
- [ ] No errors/tracebacks in `rsmesh-bbs.log` during tc2 cycles
- [ ] Document any TC²-side quirks or timing differences for the sysop guide

**Notes:**

```

```

---

## Release sign-off

| Area                       | Tester | Date | Pass? |
| -------------------------- | ------ | ---- | ----- |
| Phase 1 — Upgrade          |        |      |       |
| Phase 2 — User mesh        |        |      |       |
| Phase 3 — Sysadmin + admin |        |      |       |
| Phase 4 — Peer setup       |        |      |       |
| Phase 5 — rsv1 sync        |        |      |       |
| Phase 6 — RSMesh ↔ TC²     |        |      |       |

**Open issues / doc updates needed:**

```

```

**Approved for 1.1 release:** _______________  **Date:** _______________

---

## Quick reference — admin actions triggered by mesh testing

| Mesh / user action              | Admin screen to verify                                        |
| ------------------------------- | ------------------------------------------------------------- |
| User posts channel              | Channels → List (`publish=N`)                                 |
| User posts bulletin             | Bulletins → List                                              |
| User sends mail                 | Mail → List                                                   |
| Sysadmin deletes bulletin       | Bulletins → List (`Del: Y`); later reconcile on peer          |
| Register BBS List entry         | Modules → BBS List → List                                     |
| Sync pending                    | Sync Peers → List Unsynced Data                               |
| Module sync pending             | List Unsynced Data → Modules section                          |
| Peer delete bulletin/channel    | Review Reconcile on receiving system                          |
| Urgent admin add                | Server log / radio alert (not admin-sent)                     |
| TC² peer on RSMesh              | List Sync Peers: protocol `tc2`, mesh nodes N, no module sync |
| RSMesh bulletin edit toward TC² | TC² copy unchanged (create-only)                              |
| TC² channel → RSMesh            | Channels → List `publish=N` until RSMesh operator publishes   |

---

*After QA is complete, update [RSMESH-BBS-SYSOP-GUIDE.md](RSMESH-BBS-SYSOP-GUIDE.md) and other operator docs with any corrections found during testing.*
