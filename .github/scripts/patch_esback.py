#!/usr/bin/env python3
# Re-enable ESB ACK mode on nRF54L (undo the upstream noack workaround).
#
# Upstream forces tx_payload.noack = true on nRF54L with the comment
# "TODO: esb halts with ack and tx fail" -- i.e. noack is only there to dodge the
# halt caused by per-packet clocks_stop() on TX_FAILED. patch_clkpolicy already fixes
# that halt (clocks_stop() is a no-op on nRF54L while paired), so the reason for noack is gone.
#
# Why this matters: ACK is ESB's collision-avoidance mechanism. Two ACK trackers that
# collide both miss their ACK, back off by retransmit_delay, and re-space themselves.
# That is why N nRF52 trackers coexist. A noack tracker is deaf: it never learns it
# collided and never backs off, so a single nRF54L steamrolls the whole channel --
# which is exactly what shows up as "Sequence missmatch" (retransmit duplicates) on
# the nRF52 trackers whenever the nRF54L is on. ACK also restores tx_err feedback.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
old = ("#if defined(NRF54L15_XXAA) // TODO: esb halts with ack and tx fail\n"
       "\ttx_payload.noack = true;\n"
       "#else\n"
       "\ttx_payload.noack = false;\n"
       "#endif\n")
new = ("\ttx_payload.noack = false; // ACK on nRF54L too: halt cause removed by patch_clkpolicy\n")
if "noack = false; // ACK on nRF54L" in s:
    print("patch_esback: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_esback: nRF54L switched to ACK mode (noack=false)")
else:
    print("patch_esback: WARNING noack hunk not matched (upstream changed?)", file=sys.stderr)
sys.exit(0)
