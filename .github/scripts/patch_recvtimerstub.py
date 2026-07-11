#!/usr/bin/env python3
# Receiver on NCS 3.2: the nrfx TIMER1 enabling changed and the timer is only used
# by the (unimplemented, default-disabled) TDMA scheme. Replace timer.c with a
# minimal stub so the receiver builds on 3.2 without nrfx timer. led_clock is kept
# (referenced by esb.c); LED sync just stays at 0 (cosmetic).
import sys
f = "src/connection/timer.c"
stub = ('#include "globals.h"\n'
        '#include "esb.h"\n'
        '\n'
        'uint16_t led_clock = 0;\n'
        '\n'
        'void timer_init(void) {}\n')
open(f, "w", encoding="utf-8").write(stub)
print("patch_recvtimerstub: timer.c replaced with stub (no nrfx timer)")
sys.exit(0)
