#!/usr/bin/env python3
# nRF54L HFXO (32 MHz crystal) needs several ms to stabilize. clocks_start() in
# esb.c only polls 10 x 100us = 1ms before giving up and returning -EAGAIN
# WITHOUT starting the HF clock. The callers (esb.c:408/487) ignore that return
# and the ESB radio then operates with no HFCLK -> BUS FAULT in the radio ISR
# (intermittent, depends on crystal startup time). Raise the poll limit so the
# clock is actually running before the radio is used. Harmless on nRF52 (clock
# starts fast, loop exits early).
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
o = "++fetch_attempts > 10)"
n = "++fetch_attempts > 500)"
if o in s:
    open(f, "w", encoding="utf-8").write(s.replace(o, n, 1))
    print("patch_esbclk: HF clock poll limit 10 -> 500 (1ms -> 50ms)")
elif n in s:
    print("patch_esbclk: already applied")
else:
    print("patch_esbclk: WARNING anchor not found (upstream changed?)", file=sys.stderr)
sys.exit(0)
