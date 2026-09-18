# RSMesh BBS User Guide

Release 1.1

How to interact with the BBS from a Meshtastic handset.

Send commands as **direct messages to the BBS node**. The server ignores group-channel traffic and messages addressed to other nodes. After connecting, send any letter command or an unrecognized message to open the main menu.

Send **`??`** at any time to **redisplay the last menu or prompt** from the BBS (for example if a long reply was split across several mesh packets). If there is no prior reply yet, the BBS sends the **main menu** (same as a fresh connection). When redisplaying a saved prompt, your place in a multi-step flow is unchanged.

The following describes the menus for a standard RSMesh BBS system. Individual system operators may choose to disable some core functions, or extend the BBS with optional modules that offer additional features.

## Main Menu

Open features from the main menu with the keys described below.

**Bulletins** (`B`) — [Bulletin Boards](#bulletins): Read and post to General, Info, and News boards. Sysadmin may post to Urgent.

**Channels** (`C`) — [Channel Directory](#channel-directory): View published channels or post a new entry for operator review (Visible after approval).

**Mail** (`M`) — [Mail](#mail): Read mail sent to your device, or send mail to other devices.

**Modules** (`O`) — Optional modules enabled by the operator (for example Fortune, Node Info, or **BBS List**). Module names, menu keys, and actions vary by system. See [Modules](#modules) below.

**Exit** (`X`) — Return to the Main Menu (also available from Sub-Menus as E[X]IT).

## Bulletins

Open Bulletins from the Main Menu with **`B`**, then choose a Board.

Board menu: `[G]eneral` `[I]nfo` `[N]ews` `[U]rgent`

On a board: `[R]ead` and `[P]ost` for Users (**SysAdmin** required for `[U]rgent`), with `[D]elete` for **SysAdmin** nodes.

**Read** — Choose a bulletin number from the list, then `X` to return to the Board Menu.

**Post** — Enter a short subject, then send the body across one or more messages. Send `END` on its own line to finish.

**Delete** (SysAdmin) — Choose a bulletin number to soft-delete.

Some BBS systems broadcast Urgent bulletins as alerts on the primary (0) channel. Older bulletins may stop appearing after a time; pinned bulletins usually stay visible longer.

## Mail

Open Mail from the Main Menu with **`M`**, then **`R`** (Read) or **`S`** (Send).

**Read Mail** — Shows a summary (for example `8 message(s) - 2 new message(s)`) and `[N]ew [A]ll` to list new or all messages. The list is compact (ID, date, sender, subject) with up to three messages per mesh packet. Select a message number, then `[K]eep`, `[D]elete`, or `[R]eply`. Reply uses the same process as Sending a Mail message.

**Send Mail** — Enter the recipient **short name** (or pick from a list when several nodes match). Enter a Subject when prompted, then Body in one or more messages. Send `END` by itself to finish. While you type the body, the BBS will not reply until `END`.

### Mail quick commands

From the **main menu**, you can skip the Mail submenu with TC²-style commands (the main menu text is unchanged):

| Command | Same as |
|---------|---------|
| `RM` | Mail → Read → **New** (compact list of unread mail) |
| `SM` | Mail → **Send** |

When **new mail is delivered on this BBS** (someone sent to you from the mesh or admin), you may get a short direct message such as `New mail from RSN1. Send RM to read new mail.` Mail that arrived **only via sync from another board** does not trigger this alert.

## Channel directory

Open the Channel Directory from the Main Menu with **`C`**.

**View** (`V`) — List published channels and show the Channel Name and Public Key (PSK) for a selected entry.

**Post** (`P`) — Submit a Channel Name and Public Key (PSK) for operator review. Posts are visible after SysAdmin approval.

## Modules

Open **M[o]dules** from the main menu, then choose a module by its key.

### BBS List (when enabled)

Default menu key **`L`**. Entry menu: **`[A]ll`**, **`[S]ync-Interested`**, **`E[X]IT`**.

- **All** — Every directory entry (list ID, short name, board name, node ID, location; `*` marks sync-interested boards).
- **Sync-Interested** — Entries the operator flagged for the sync-interested filter only.

After a list, **`Enter list ID for details`**, then **`[R]eturn`** to the list-type menu or **`E[X]IT`** to the main menu.

## Shared Information

Bulletins, channels, and mail you see on a BBS may have been posted on that system or shared from another BBS on the mesh. What is available can vary from one BBS to another.

If a **remote board deletes** a bulletin or channel you still carry, your sysop may see a **reconcile** prompt only for content that **came from sync**. **Posts you (or your sysop) created on this BBS** are not removed just because a peer deleted their copy.

## SysAdmin Capabilities on the Mesh

**Sysadmin** nodes have additional options on some Menus as outlined above, including posting to Urgent, deleting bulletins, and extra actions in some modules.
