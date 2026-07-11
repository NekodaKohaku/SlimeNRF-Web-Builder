#!/usr/bin/env python3
# battery.c: SAADC input selection is still using the NCS <= 3.1 encoding.
#
# Upstream already spotted this and left the fix commented out right next to the broken
# line: on NCS <= 3.1 the nrfx enum SAADC_CH_PSELP_PSELP_AnalogInput0 == 1, so the code
# does `input_positive = 1 + channel`. From NCS 3.2 the value comes from
# <zephyr/dt-bindings/adc/nrf-saadc.h> where NRF_SAADC_AIN0 == 0, so that +1 now selects
# the WRONG analog input -- every channel is off by one.
#
# Both of our modules build against v3.2-branch, so the ADC has been reading the next pin
# up. E.g. an external divider on P0.04 (AIN2) was actually sampling AIN3 = P0.05, a
# floating pin -> "Battery not available (488 mV)". Same on nRF54L: P1.06 (AIN2) sampled
# AIN3 = P1.07, which the ME54BS01 module does not even break out.
#
# Same story for the internal rails: VDDHDIV5 and VDD now live in the 128+ shim range
# (NRF_SAADC_AIN_VDD_SHIM_OFFSET), not at the old enum values 13 and 9.
import sys
f = "src/system/battery.c"
s = open(f, encoding="utf-8").read()
if "NCS 3.2: NRF_SAADC_AIN0" in s:
    print("patch_adc32: already applied"); sys.exit(0)
n = 0

old = ("\tif (cfg->output_ohm != 0) {\n"
       "\t\taccp->input_positive = 1 + iocp->channel; // <=sdk 3.1 SAADC_CH_PSELP_PSELP_AnalogInput0\n")
new = ("\tif (cfg->output_ohm != 0) {\n"
       "\t\taccp->input_positive = iocp->channel; // NCS 3.2: NRF_SAADC_AIN0 == 0 (was 1 on <=3.1)\n")
if old in s: s = s.replace(old, new, 1); n += 1

old = ("\t} else {\n"
       "\t\taccp->input_positive = 9; // SAADC_CH_PSELP_PSELP_VDD\n"
       "\t}\n")
new = ("\t} else {\n"
       "\t\taccp->input_positive = 128 + 0; // NCS 3.2: NRF_SAADC_VDD (shim offset 128)\n"
       "\t}\n")
if old in s: s = s.replace(old, new, 1); n += 1

old = ("\tif (iocp->channel == 12) { // VDDHDIV5\n"
       "\t\t// <=sdk 3.1 SAADC_CH_PSELP_PSELP_VDDHDIV5\n")
new = ("\tif (iocp->channel == 12) { // VDDHDIV5\n"
       "\t\taccp->input_positive = 128 + 4; // NCS 3.2: NRF_SAADC_VDDHDIV5\n")
if old in s: s = s.replace(old, new, 1); n += 1

open(f, "w", encoding="utf-8").write(s)
print("patch_adc32: applied %d/3 (SAADC input selection -> NCS 3.2 encoding)" % n)
sys.exit(0)
