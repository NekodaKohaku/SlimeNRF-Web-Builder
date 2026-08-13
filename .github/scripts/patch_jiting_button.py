#!/usr/bin/env python3
# jiting tracker: 単押し = 再起動 (旧 upstream 挙動) を廃止し、現行公式に合わせる。
# 公式 main は該当行をコメントアウト済み (誤押しリブートは再同期問題も誘発する)。
# 多押しアクション (ZRO 校正/ペアリングリセット等) は CONFIG_USER_EXTRA_ACTIONS の
# まま、長押し 1 秒の電源オフも従来どおり。再起動はコンソール `reboot` で可能。
import sys

MARK = "SLIMENRF_BTN_NO_REBOOT"
f = "src/system/system.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_jiting_button: already applied"); sys.exit(0)

old = ("\t\t\t} else if (num_presses == 1) {\n"
       "\t\t\t\tif (test_mode_get()) {\n"
       "\t\t\t\t\tLOG_INF(\"Button reboot blocked by test mode\");\n"
       "\t\t\t\t} else {\n"
       "\t\t\t\t\tsys_request_system_reboot(false);\n"
       "\t\t\t\t}\n"
       "\t\t\t}\n").replace("\n", NL)
new = ("\t\t\t} else if (num_presses == 1) {\n"
       "\t\t\t\t/* " + MARK + ": align with current upstream official -\n"
       "\t\t\t\t * single press no longer reboots (accidental presses caused\n"
       "\t\t\t\t * reboot + re-pair churn). Use console `reboot` instead. */\n"
       "\t\t\t\tLOG_INF(\"Single press ignored (single-press reboot disabled)\");\n"
       "\t\t\t}\n").replace("\n", NL)

if old not in s:
    sys.exit("patch_jiting_button: FAILED, single-press reboot anchor not found in system.c")
s = s.replace(old, new, 1)
open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_jiting_button: system.c OK (single-press reboot removed)")
