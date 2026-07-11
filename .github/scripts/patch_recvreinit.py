#!/usr/bin/env python3
# Receiver-side ESB RX recovery watchdog.
#
# Known nRF52840 ESB issue (DevZone 76946): the PRX radio's per-pipe RX wedges
# after some packets (esp. from a different-radio PTX like nRF54L) -> it keeps
# ACKing at HW level but stops delivering RX events for that pipe. The documented
# fix is to reset/re-init the radio. The receiver already has this exact sequence
# in timer.c's TDMA handler (esb_disable(); esb_initialize(false); esb_start_rx();)
# but the timer is disabled by default. Here we run that re-init on a plain
# periodic watchdog so a wedged pipe recovers without needing TDMA.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
marker = "esb_recover_thread"
add = ("\n"
       "static void esb_recover_thread(void)\n"
       "{\n"
       "\twhile (1)\n"
       "\t{\n"
       "\t\tk_msleep(1000);\n"
       "\t\tif (!esb_paired || esb_pairing)\n"
       "\t\t\tcontinue;\n"
       "\t\tesb_stop_rx();\n"
       "\t\tesb_disable();\n"
       "\t\tesb_initialized = false;\n"
       "\t\tesb_initialize(false);\n"
       "\t\tesb_start_rx();\n"
       "\t}\n"
       "}\n"
       "K_THREAD_DEFINE(esb_recover_thread_id, 1024, esb_recover_thread, NULL, NULL, NULL, 7, 0, 0);\n")
if marker in s:
    print("patch_recvreinit: already applied")
else:
    open(f, "w", encoding="utf-8").write(s + add)
    print("patch_recvreinit: appended periodic ESB RX re-init watchdog (1s)")
sys.exit(0)
