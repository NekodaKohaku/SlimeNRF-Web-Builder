#!/usr/bin/env python3
# Test: remove the per-packet esb_flush_tx() on nRF54L.
#
# esb_write() calls esb_flush_tx() before every esb_write_payload(). On nRF54L
# this is suspected of disturbing the per-pipe ESB PID sequencing, so the nRF52
# receiver's hardware duplicate-detection wedges that pipe after ~2 s (radio keeps
# ACKing, but the app stops getting packets). nRF52 does the same flush and is
# fine, so gate it: nRF54L skips the flush and lets ESB manage the PID normally.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
old = "\tesb_flush_tx(); // this will clear all transmissions even if they did not complete"
new = ("#if !defined(NRF54L15_XXAA)\n"
       "\tesb_flush_tx(); // this will clear all transmissions even if they did not complete\n"
       "#endif // nRF54L: skip per-packet flush so ESB PID advances cleanly (receiver pipe wedge)")
if "#if !defined(NRF54L15_XXAA)\n\tesb_flush_tx();" in s:
    print("patch_esbnoflush: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_esbnoflush: nRF54L per-packet esb_flush_tx removed")
else:
    print("patch_esbnoflush: WARNING anchor not found", file=sys.stderr)
sys.exit(0)
