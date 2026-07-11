#!/usr/bin/env python3
# TEMPORARY nRF54L ESB debug. Prints a once-per-second summary from esb_write so
# it never floods the UART. nRF52 is untouched (whole block is #if NRF54L15_XXAA).
# Remove this patch (and its workflow line) once the ESB interop is understood.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()

anchor = "\tsend_data = true;\n}"
block = (
    "\tsend_data = true;\n"
    "#if defined(NRF54L15_XXAA)\n"
    "\t{\n"
    "\t\tstatic int64_t dbg_t = 0;\n"
    "\t\tstatic uint32_t dbg_n = 0;\n"
    "\t\tdbg_n++;\n"
    "\t\tint64_t dbg_now = k_uptime_get();\n"
    "\t\tif (dbg_now - dbg_t >= 1000) {\n"
    "\t\t\tLOG_INF(\"[dbg] tx/s=%u type=%02X len=%u pipe=%u seq=%u tx_err=%u id=%u b0-7=%02X %02X %02X %02X %02X %02X %02X %02X\",\n"
    "\t\t\t\tdbg_n, data[0], tx_payload.length, tx_payload.pipe, data[20], (unsigned)tx_errors, paired_addr[1],\n"
    "\t\t\t\tdata[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7]);\n"
    "\t\t\tLOG_INF(\"[dbg] addr0=%02X.%02X.%02X.%02X addr1=%02X.%02X.%02X.%02X prefix0=%02X prefix1=%02X\",\n"
    "\t\t\t\tbase_addr_0[0], base_addr_0[1], base_addr_0[2], base_addr_0[3],\n"
    "\t\t\t\tbase_addr_1[0], base_addr_1[1], base_addr_1[2], base_addr_1[3],\n"
    "\t\t\t\taddr_prefix[0], addr_prefix[1]);\n"
    "\t\t\tdbg_n = 0; dbg_t = dbg_now;\n"
    "\t\t}\n"
    "\t}\n"
    "#endif\n"
    "}"
)

if "[dbg] tx/s=" in s:
    print("patch_esbdebug: already applied")
elif anchor in s:
    open(f, "w", encoding="utf-8").write(s.replace(anchor, block, 1))
    print("patch_esbdebug: nRF54L per-second ESB debug added")
else:
    print("patch_esbdebug: WARNING anchor not found (upstream changed?)", file=sys.stderr)
sys.exit(0)
