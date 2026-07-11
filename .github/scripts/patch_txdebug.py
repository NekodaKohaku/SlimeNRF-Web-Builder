#!/usr/bin/env python3
# TEMP: per-second TX rate from esb_write, on BOTH chips (the old one was nRF54L-only).
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
if "[txdbg]" in s:
    print("patch_txdebug: already applied"); sys.exit(0)
anchor = ("void esb_write(uint8_t *data)\n"
          "{\n"
          "\tif (!esb_initialized || !esb_paired)\n"
          "\t\treturn;\n")
if anchor not in s:
    print("patch_txdebug: anchor not found", file=sys.stderr); sys.exit(1)
inject = anchor + (
    "\t{\n"
    "\t\tstatic uint32_t _n = 0;\n"
    "\t\tstatic int64_t _t = 0;\n"
    "\t\t_n++;\n"
    "\t\tint64_t _now = k_uptime_get();\n"
    "\t\tif (_now - _t >= 1000) {\n"
    "\t\t\tLOG_INF(\"[txdbg] tx/s=%u tx_err=%u type=%02X seq=%u\", _n, (unsigned)tx_errors,\n"
    "\t\t\t\t(unsigned)data[0], (unsigned)data[20]);\n"
    "\t\t\t_n = 0; _t = _now;\n"
    "\t\t}\n"
    "\t}\n")
open(f, "w", encoding="utf-8").write(s.replace(anchor, inject, 1))
print("patch_txdebug: per-second tx/s + tx_err (both chips)")
sys.exit(0)
