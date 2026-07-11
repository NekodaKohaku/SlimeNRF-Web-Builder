#!/usr/bin/env python3
# Tracker-side ESB soft-restart, coordinated inside the send path (nRF54L only).
#
# Confirmed: nRF54L(PTX)->nRF52(PRX) link wedges (~69 packets); only resetting the
# tracker's ESB (PID) clears it, receiver then accepts again (rx==fwd). Tracker can't
# detect the wedge (HW auto-ACKs regardless of app), so reset must be periodic/blind.
#
# v43/v44 ran the reset in a SEPARATE thread; it raced esb_write (reset landing mid-
# transmission) -> extra packet loss, erratic rate. v45: do the reset INLINE in
# esb_write, every ESB_REINIT_EVERY packets, right before queuing the payload
# ("reset then send"). Deterministic, no cross-thread race. HFXO stays on
# (patch_esbhalt) so only the RADIO peripheral is touched -> Errata 39 / MLTPAN-20 safe.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
if "esb_reinit_ctr" in s:
    print("patch_esbreinit: already applied"); sys.exit(0)

anchor = ("void esb_write(uint8_t *data)\n"
          "{\n"
          "\tif (!esb_initialized || !esb_paired)\n"
          "\t\treturn;\n")
if anchor not in s:
    print("patch_esbreinit: ERROR esb_write anchor not found", file=sys.stderr); sys.exit(1)

inject = (anchor +
          "#if defined(NRF54L15_XXAA)\n"
          "#define ESB_REINIT_EVERY 32\n"
          "\tstatic uint32_t esb_reinit_ctr = 0;\n"
          "\tif (++esb_reinit_ctr >= ESB_REINIT_EVERY)\n"
          "\t{\n"
          "\t\tuint32_t _rt0 = k_cycle_get_32();\n"
          "\t\tesb_reinit_ctr = 0;\n"
          "\t\tesb_disable();\n"
          "\t\tesb_initialize(true);\n"
          "\t\tLOG_INF(\"[reinit] us=%u\", k_cyc_to_us_floor32(k_cycle_get_32() - _rt0));\n"
          "\t}\n"
          "#endif /* defined(NRF54L15_XXAA) */\n")
s = s.replace(anchor, inject, 1)
open(f, "w", encoding="utf-8").write(s)
print("patch_esbreinit: inline reset every 32 packets in esb_write (no separate thread)")
sys.exit(0)
