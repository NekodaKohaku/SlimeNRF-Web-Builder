#!/usr/bin/env python3
# TEMPORARY nRF54L fusion-output debug: print the fusion quaternion once per
# second, straight from connection_update_sensor_data (before ESB). Lets us see
# whether the fusion output FREEZES (same q while moving -> server sees stale
# pose -> "freeze then drop") or keeps changing (freeze is downstream/RF).
# nRF52 untouched (#if NRF54L15_XXAA).
import sys
f = "src/connection/connection.c"
s = open(f, encoding="utf-8").read()
anchor = "\tquat_update_time = k_uptime_get();\n\tif (sleep)"
block = ("\tquat_update_time = k_uptime_get();\n"
         "#if defined(NRF54L15_XXAA)\n"
         "\t{\n"
         "\t\tstatic int64_t qdbg_t = 0;\n"
         "\t\tint64_t qdbg_now = k_uptime_get();\n"
         "\t\tif (qdbg_now - qdbg_t >= 1000) {\n"
         "\t\t\tLOG_INF(\"[qdbg] fusion q= %d %d %d %d (x1000)\", (int)(q[0]*1000), (int)(q[1]*1000), (int)(q[2]*1000), (int)(q[3]*1000));\n"
         "\t\t\tqdbg_t = qdbg_now;\n"
         "\t\t}\n"
         "\t}\n"
         "#endif\n"
         "\tif (sleep)")
if "[qdbg] fusion q=" in s:
    print("patch_quatdebug: already applied")
elif anchor in s:
    open(f, "w", encoding="utf-8").write(s.replace(anchor, block, 1))
    print("patch_quatdebug: applied")
else:
    print("patch_quatdebug: WARNING anchor not found", file=sys.stderr)
sys.exit(0)
