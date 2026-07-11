#!/usr/bin/env python3
# Stop the nRF54L ESB radio from halting mid-stream.
#
# event_handler() calls clocks_stop() on every TX_SUCCESS/TX_FAILED while paired,
# and esb_write() calls clocks_start() for every packet -> the HF clock (HFXO/PLL)
# is torn down and restarted ~50x/second. On nRF54L the clock start/stop path
# (MLTPAN-20 PLLSTART) is fragile: if clocks_stop() lands while a packet is still
# ramping/transmitting, the radio wedges -> no more TX events fire -> clock_status
# stays true -> esb_write() keeps queueing into a dead radio (tx_err frozen, seq
# still advancing). Symptom: tracker streams for ~1 s then the receiver goes silent.
#
# Fix: on nRF54L, do NOT stop the clock per-packet. Keep HFXO running for the whole
# active stream; it is still released when the connection goes idle via
# connection_clocks_request_stop(). nRF52 keeps its original per-packet power saving.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()

old = "\t\tif (esb_paired)\n\t\t\tclocks_stop();"
new = ("\t\tif (esb_paired)\n"
       "#if !defined(NRF54L15_XXAA)\n"
       "\t\t\tclocks_stop();\n"
       "#else\n"
       "\t\t\t(void)0; // nRF54L: keep HF clock on while streaming; per-packet stop mid-TX halts the radio (idle stop via connection_clocks_request_stop)\n"
       "#endif")

n = s.count(old)
if "#if !defined(NRF54L15_XXAA)\n\t\t\tclocks_stop();" in s:
    print("patch_esbhalt: already applied")
elif n == 2:
    open(f, "w", encoding="utf-8").write(s.replace(old, new))
    print("patch_esbhalt: nRF54L per-packet clocks_stop disabled (2 hunks)")
else:
    print(f"patch_esbhalt: WARNING expected 2 anchors, found {n}", file=sys.stderr)
sys.exit(0)
