#!/usr/bin/env python3
# connection_thread() also stops the HF clock -- the second clocks_stop() we missed.
#
# patch_esbhalt gated the clocks_stop() calls inside the ESB event_handler, but
# connection_thread() (connection.c) independently calls connection_clocks_request_stop()
# -> clocks_stop(), so on nRF54L the HFXO/PLL is STILL being cycled while streaming.
#
# Cost: every subsequent esb_write() must clocks_start() again, and clocks_start() is a
# spinwait (`do { k_usleep(100); ... } while (err);`) plus, on nRF54L only, an extra
# NRF_CLOCK_TASK_PLLSTART. nRF52 waits for HFXO alone and is cheap; nRF54L waits for
# HFXO *and* PLL and is not. connection.c is fully shared (no chip ifdefs), which is why
# the identical loop yields ~150-190 tx/s on nRF52 but only ~55 tx/s on nRF54L.
# Rapid HFXO/PLL cycling is also exactly what Errata 39 / MLTPAN-20 says not to do.
#
# Fix: on nRF54L, don't stop the clock from connection_thread. It stays up while the
# tracker is awake and streaming; real power-down still happens via system sleep.
import sys
f = "src/connection/connection.c"
s = open(f, encoding="utf-8").read()
old = ("void connection_clocks_request_stop(void)\n"
       "{\n"
       "\tclocks_stop();\n"
       "}\n")
new = ("void connection_clocks_request_stop(void)\n"
       "{\n"
       "#if !defined(NRF54L15_XXAA)\n"
       "\tclocks_stop();\n"
       "#endif\n"
       "}\n")
if "#if !defined(NRF54L15_XXAA)\n\tclocks_stop();" in s:
    print("patch_connclk: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_connclk: nRF54L no longer stops HF clock from connection_thread")
else:
    print("patch_connclk: WARNING hunk not matched (upstream changed?)", file=sys.stderr)
sys.exit(0)
