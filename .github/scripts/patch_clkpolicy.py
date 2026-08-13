#!/usr/bin/env python3
# Single-point HF clock policy for nRF54L (replaces patch_esbhalt + patch_connclk).
#
# The hardware difference is one sentence: stopping the HF clock is cheap on nRF52 and
# expensive/unsafe on nRF54L (HFXO *and* PLL must come back up; Errata 39 / MLTPAN-20
# says they must not be rapidly cycled). Encoding that as `#if !defined(NRF54L15_XXAA)`
# at every clocks_stop() CALL SITE (esb.c event_handler x2, connection.c
# connection_clocks_request_stop, and clocks_request_stop's delayed thread) scatters the
# divergence, is easy to miss a site, and breaks whenever upstream adds a new caller.
#
# Instead put the policy in clocks_stop() itself: one ifdef, one reason, every caller
# (present and future) covered, and all call sites stay byte-identical to upstream.
# While paired/streaming the clock stays up; real power-down still happens via system
# sleep, which powers the whole chip down anyway.
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
old = ("void clocks_stop(void)\n"
       "{\n"
       "\tif (!clock_status)\n"
       "\t\treturn;\n")
new = ("void clocks_stop(void)\n"
       "{\n"
       "#if defined(NRF54L15_XXAA)\n"
       "\t/* Errata 39 / MLTPAN-20: HFXO+PLL must not be rapidly cycled. Keep the clock\n"
       "\t   up while streaming; system sleep still powers the chip down. */\n"
       "\tif (esb_paired)\n"
       "\t\treturn;\n"
       "#endif\n"
       "\tif (!clock_status)\n"
       "\t\treturn;\n")
if "Errata 39 / MLTPAN-20: HFXO+PLL must not be rapidly cycled" in s:
    print("patch_clkpolicy: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_clkpolicy: nRF54L clock policy centralised in clocks_stop()")
else:
    print("patch_clkpolicy: ERROR clocks_stop hunk not matched", file=sys.stderr); sys.exit(1)
sys.exit(0)
