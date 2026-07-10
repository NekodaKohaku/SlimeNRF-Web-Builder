#!/usr/bin/env python3
# nRF54L data TX used noack=true to work around the old "esb halts with ack and
# tx fail" bug (esb.c esb_write, #if NRF54L15_XXAA). NCS 3.2 fixes that halt
# (pairing, which uses ACK/noack=false, now works). noack=true means no
# acknowledgement / no retransmission, so the receiver dongle (which works fine
# with the nRF52 tracker using noack=false) does not get usable data. Flip the
# nRF54L data path back to noack=false so it behaves like the working nRF52.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
o = "\ttx_payload.noack = true;"
n = "\ttx_payload.noack = false;"
if o in s:
    open(f, "w", encoding="utf-8").write(s.replace(o, n, 1))
    print("patch_esbnoack: nRF54L data TX noack true -> false")
elif s.count("\ttx_payload.noack = false;") >= 2:
    print("patch_esbnoack: already applied")
else:
    print("patch_esbnoack: WARNING anchor not found (upstream changed?)", file=sys.stderr)
sys.exit(0)
