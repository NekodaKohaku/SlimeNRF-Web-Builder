#!/usr/bin/env python3
# jiting 受信機: 既知トラッカーの再同期を pairing mode なしで自動受理する。
#
# fork の設計ではトラッカーが再起動すると再ペアリング要求を送るが、受信機は
# pairing mode でなければ既知デバイスでも拒否する。トラッカー側は ACK が来ない
# ため TX FIFO が詰まり (ENOMEM -12)、リトライ嵐が他トラッカーまで妨害する。
# 復旧には手動で `pair` + トラッカー再起動が必要だった。
#
# 修正: 既知 (登録済み) トラッカーの再ペアリングは常時受理。未知デバイスは
# 従来どおり pairing mode 必須 (セキュリティ挙動は不変)。
# 2 箇所: ack_handler の応答ゲート + event_handler の受理ゲート。
import sys

MARK = "SLIMENRF_RECV_REJOIN"
f = "src/connection/esb.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_jiting_recv_rejoin: already applied"); sys.exit(0)
changed = 0

def repl(old, new):
    global s, changed
    o = old.replace("\n", NL); n = new.replace("\n", NL)
    if s.count(o) == 1:
        s = s.replace(o, n, 1); changed += 1; return True
    return False

# ---- 1) ack_handler: 既知トラッカーには pairing mode 外でも応答を許可 ----
repl(
"\t\tknown_id = esb_find_tracker(found_addr);\n"
"\n"
"\t\tif (!esb_pairing) {\n"
"\t\t\t*suppress_ack = true;\n"
"\t\t\treturn;\n"
"\t\t}\n",
"\t\tknown_id = esb_find_tracker(found_addr);\n"
"\n"
"\t\t/* " + MARK + ": known trackers may always complete the re-pair\n"
"\t\t * handshake (e.g. after reboot); only unknown devices require\n"
"\t\t * pairing mode. */\n"
"\t\tif (!esb_pairing && known_id < 0) {\n"
"\t\t\t*suppress_ack = true;\n"
"\t\t\treturn;\n"
"\t\t}\n")

# ---- 2) event_handler: 既知トラッカーは受理して従来の既知デバイス経路へ ----
repl(
"\t\t\t\t\tif (!esb_pairing) {\n"
"\t\t\t\t\t\tif (known_id >= 0) {\n"
"\t\t\t\t\t\t\tLOG_WRN(\n"
"\t\t\t\t\t\t\t\t\"Received pairing request from known tracker %d, but pairing mode inactive\",\n"
"\t\t\t\t\t\t\t\tknown_id\n"
"\t\t\t\t\t\t\t);\n"
"\t\t\t\t\t\t} else {\n"
"\t\t\t\t\t\t\tLOG_INF(\"Pairing request from unknown %012llX, pairing mode inactive\", found_addr);\n"
"\t\t\t\t\t\t}\n"
"\t\t\t\t\t\tbreak;\n"
"\t\t\t\t\t}\n",
"\t\t\t\t\tif (!esb_pairing) {\n"
"\t\t\t\t\t\tif (known_id < 0) {\n"
"\t\t\t\t\t\t\tLOG_INF(\"Pairing request from unknown %012llX, pairing mode inactive\", found_addr);\n"
"\t\t\t\t\t\t\tbreak;\n"
"\t\t\t\t\t\t}\n"
"\t\t\t\t\t\t/* " + MARK + ": fall through - known tracker re-sync\n"
"\t\t\t\t\t\t * is auto-accepted without manual pairing mode. */\n"
"\t\t\t\t\t\tLOG_INF(\"Known tracker %d re-pair auto-accepted (pairing mode inactive)\", known_id);\n"
"\t\t\t\t\t}\n")

if changed == 2:
    open(f, "w", encoding="utf-8", newline="").write(s)
    print(f"patch_jiting_recv_rejoin: esb.c {changed}/2 OK")
else:
    print(f"patch_jiting_recv_rejoin: FAILED, only {changed}/2 hunks matched", file=sys.stderr)
    sys.exit(1)
