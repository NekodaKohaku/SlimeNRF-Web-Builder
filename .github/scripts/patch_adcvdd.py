#!/usr/bin/env python3
# battery.c / test54l dts: the "measure the supply rail internally" path is
# nRF52-only and silently breaks on nRF54L.
#
# io-channels = <&adc 12> is the firmware's convention for "internal supply
# rail", and battery.c turns it into NRF_SAADC_VDDHDIV5 (VDDH/5). VDDH is the
# high-voltage supply of the nRF52840/nRF5340, which take up to 5.5 V on a
# separate pin. The nRF54L15 has no VDDH domain at all - it runs from a single
# 1.7-3.6 V VDD - so nrfx does not define the input:
#
#   #if defined(SAADC_CH_PSELP_PSELP_VDDHDIV5)
#   #define NRF_SAADC_HAS_INPUT_VDDHDIV5 1   ... else 0
#
# Writing the VDDHDIV5 shim value anyway makes adc_channel_setup() reject the
# channel, battery_ok stays false and the tracker reports no battery.
#
# nRF54L can still measure its own supply: NRF_SAADC_VDD reads VDD through an
# internal divider (confirmed by Nordic on DevZone case 345172). That is the
# right substitute, so select it whenever VDDHDIV5 does not exist.
#
# The board node needs fixing too. test54l_nrf54l15_cpuapp.dts was copied from
# promicro and reads:
#
#   io-channels = <&adc 12>;   // Measure VDDHDIV5
#   output-ohms = <1>;
#   full-ohms   = <2>;         // promicro correctly uses 5 for VDDH/5
#
# Two bugs in three lines: a channel this SoC does not have, and a ratio that
# matches neither VDDH/5 nor a real divider. Since the substitute input reads
# VDD directly there is no ratio to undo, so switch the node to the firmware's
# own "no divider" encoding (output-ohms = 0), which also makes divider_setup()
# assume a 3.6 V full-scale range and pick the correct gain on nRF54L.
#
# Run from the firmware tree root. Idempotent.
import os
import sys

MARK = "SLIMENRF_ADC_VDD_NO_VDDH"
n = 0

# ---- 1. battery.c: never select VDDHDIV5 on a SoC that lacks it ----------
f = "src/system/battery.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"

if MARK in s:
    print("patch_adcvdd: battery.c already applied")
else:
    old = ("\tif (iocp->channel == 12) { // VDDHDIV5\n"
           "\t\taccp->input_positive = 128 + 4; // NCS 3.2: NRF_SAADC_VDDHDIV5\n")
    new = ("\tif (iocp->channel == 12) { // internal supply rail\n"
           "\t\t/* " + MARK + ": VDDH only exists on SoCs with a high-voltage\n"
           "\t\t * domain (nRF52840/nRF5340). nRF54L runs from a single VDD and\n"
           "\t\t * nrfx does not define the input there, so the shim value would\n"
           "\t\t * be rejected by adc_channel_setup(). Read VDD instead - it goes\n"
           "\t\t * through an internal divider and needs no external parts. */\n"
           "#if NRF_SAADC_HAS_INPUT_VDDHDIV5\n"
           "\t\taccp->input_positive = 128 + 4; // NRF_SAADC_VDDHDIV5\n"
           "#else\n"
           "\t\taccp->input_positive = 128 + 0; // NRF_SAADC_VDD\n"
           "#endif\n")
    o = old.replace("\n", NL)
    if o not in s:
        sys.exit("patch_adcvdd: FAILED, channel 12 anchor not found "
                 "(run patch_adc32.py first)")
    s = s.replace(o, new.replace("\n", NL), 1)

    # NRF_SAADC_HAS_INPUT_VDDHDIV5 comes from the nrfx HAL header.
    inc = "#include <zephyr/drivers/adc.h>"
    if inc in s and "hal/nrf_saadc.h" not in s:
        s = s.replace(inc, inc + NL + "#include <hal/nrf_saadc.h>", 1)
    open(f, "w", encoding="utf-8", newline="").write(s)
    n += 1
    print("patch_adcvdd: battery.c OK (VDDHDIV5 guarded, falls back to VDD)")

# ---- 2. test54l board: the node describes hardware that does not exist ----
d = "boards/nordic/test54l/test54l_nrf54l15_cpuapp.dts"
if not os.path.isfile(d):
    print("patch_adcvdd: %s not present, skipping board fix" % d)
else:
    t = open(d, encoding="utf-8", newline="").read()
    TNL = "\r\n" if "\r\n" in t else "\n"
    if MARK in t:
        print("patch_adcvdd: test54l dts already applied")
    else:
        old = ("\t\tio-channels = <&adc 12>; // Measure VDDHDIV5\n"
               "\t\toutput-ohms = <1>;\n"
               "\t\tfull-ohms = <2>;\n")
        new = ("\t\t/* " + MARK + ": copied from promicro, but nRF54L has no VDDH\n"
               "\t\t * and the ratio matched neither VDDH/5 nor a real divider.\n"
               "\t\t * output-ohms = 0 is the firmware's \"no divider, read the\n"
               "\t\t * supply directly\" encoding: it selects NRF_SAADC_VDD and\n"
               "\t\t * assumes a 3.6 V full scale, which picks the right gain. */\n"
               "\t\tio-channels = <&adc 12>; // internal supply rail\n"
               "\t\toutput-ohms = <0>;\n"
               "\t\tfull-ohms = <0>;\n")
        o = old.replace("\n", TNL)
        if o not in t:
            sys.exit("patch_adcvdd: FAILED, test54l battery-divider anchor not found")
        t = t.replace(o, new.replace("\n", TNL), 1)
        open(d, "w", encoding="utf-8", newline="").write(t)
        n += 1
        print("patch_adcvdd: test54l dts OK (battery-divider -> internal VDD)")

print("patch_adcvdd: applied %d change(s)" % n)
