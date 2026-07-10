#!/usr/bin/env python3
# Tracker-side periodic ESB soft-restart (nRF54L only).
#
# Root-cause evidence: nRF54L(PTX) -> nRF52(PRX) link delivers data for ~2s then
# the receiver stops getting this tracker's packets. Power-cycling the dongle does
# NOT recover it; only REBOOTING THE TRACKER does. With noack=true the tracker gets
# no ACK feedback (tx_err stays 0) so it cannot detect the wedge -> must reset blindly.
# A tracker reboot resets the ESB PID counter (starts at 0); the receiver then accepts
# the pipe again. esb_deinitialize()+esb_initialize(true) reproduces that PID reset
# WITHOUT a full reboot. Addresses are static globals set at pairing, so the paired
# link is preserved. HFXO stays on during streaming (patch_esbhalt), so this touches
# only the RADIO peripheral -> Errata 39 / MLTPAN-20 safe. Matches Nordic DevZone
# 121251 guidance ("you may need to restart the radio") for nRF54L ESB lockups.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
if "esb_reinit_thread" in s:
    print("patch_esbreinit: already applied"); sys.exit(0)
add = ("\n"
       "#if defined(NRF54L15_XXAA)\n"
       "static void esb_reinit_thread(void)\n"
       "{\n"
       "\twhile (1)\n"
       "\t{\n"
       "\t\tk_msleep(1000);\n"
       "\t\tif (!esb_paired || !esb_initialized)\n"
       "\t\t\tcontinue;\n"
       "\t\tesb_deinitialize();\n"
       "\t\tesb_initialize(true);\n"
       "\t}\n"
       "}\n"
       "K_THREAD_DEFINE(esb_reinit_thread_id, 512, esb_reinit_thread, NULL, NULL, NULL, ESB_THREAD_PRIORITY, 0, 0);\n"
       "#endif /* defined(NRF54L15_XXAA) */\n")
open(f, "w", encoding="utf-8").write(s + add)
print("patch_esbreinit: appended nRF54L periodic ESB soft-restart (1s)")
sys.exit(0)
