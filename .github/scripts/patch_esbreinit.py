#!/usr/bin/env python3
# Tracker-side periodic ESB soft-restart (nRF54L only).
#
# Confirmed root cause (v43 test): nRF54L(PTX)->nRF52(PRX) link wedges after ~2s;
# only rebooting the TRACKER recovers it (dongle power-cycle does not). A soft ESB
# re-init resets the ESB PID counter, reproducing the reboot's effect without a full
# reboot -> receiver accepts the pipe again (rx==fwd restored, permanent stall gone).
#
# v44: v43 used esb_deinitialize()+esb_initialize() every 1s. That removed the
# permanent stall but the rate was erratic (re-wedged within the 1s window during bad
# periods). Make the reset LIGHTER (drop esb_deinitialize's k_msleep(10) pending-TX
# wait -- noack PTX has nothing to wait for) and MORE FREQUENT (300ms, well ahead of
# the ~2s wedge) so the pipe never stays wedged. HFXO stays on (patch_esbhalt) so this
# touches only the RADIO peripheral -> Errata 39 / MLTPAN-20 safe.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
if "esb_reinit_thread" in s:
    print("patch_esbreinit: already applied"); sys.exit(0)
add = ("\n"
       "#if defined(NRF54L15_XXAA)\n"
       "#define ESB_REINIT_INTERVAL_MS 300\n"
       "static void esb_reinit_thread(void)\n"
       "{\n"
       "\twhile (1)\n"
       "\t{\n"
       "\t\tk_msleep(ESB_REINIT_INTERVAL_MS);\n"
       "\t\tif (!esb_paired || !esb_initialized)\n"
       "\t\t\tcontinue;\n"
       "\t\tesb_initialized = false;\n"
       "\t\tesb_disable();\n"
       "\t\tesb_initialize(true);\n"
       "\t}\n"
       "}\n"
       "K_THREAD_DEFINE(esb_reinit_thread_id, 512, esb_reinit_thread, NULL, NULL, NULL, ESB_THREAD_PRIORITY, 0, 0);\n"
       "#endif /* defined(NRF54L15_XXAA) */\n")
open(f, "w", encoding="utf-8").write(s + add)
print("patch_esbreinit: appended nRF54L light ESB soft-restart (300ms)")
sys.exit(0)
