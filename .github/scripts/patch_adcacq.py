#!/usr/bin/env python3
# battery.c: the SAADC acquisition time for the external AIN channel is too short.
#
# The nRF SAADC charges an internal sampling capacitor through the source; if the
# acquisition time is shorter than that RC needs, the capacitor never reaches the input
# voltage and the conversion comes out SYSTEMATICALLY LOW. Nordic's table maps acquisition
# time to the maximum source resistance it can settle: 3 us ~ 10 kOhm, 10 us ~ 100 kOhm,
# 20 us ~ 400 kOhm, 40 us ~ 800 kOhm.
#
# battery.c uses 3 us for the external AIN path -- yet it already uses 10 us for the
# internal VDDHDIV5 channel, and the author left a "ADC is very noisy" TODO next to
# oversampling = 7 (128x averaging, which makes short-acquisition droop worse).
#
# Measured on hardware: a NiMH cell reading 1.117 V on a multimeter came back as ~1002 mV
# from the ADC -- about 10% low, consistently. And the typical SlimeVR divider (1000k/510k)
# is ~337 kOhm Thevenin, for which 3 us is nowhere near enough, so a divider-equipped board
# is affected even more than this direct-connected one.
#
# 40 us covers source impedances up to ~800 kOhm, i.e. every divider we can be configured
# with, and the cost is irrelevant here (the battery is sampled at most once a second).
import sys
f = "src/system/battery.c"
s = open(f, encoding="utf-8").read()
old = "\t\t.acquisition_time = ADC_ACQ_TIME(ADC_ACQ_TIME_MICROSECONDS, 3),\n"
new = "\t\t.acquisition_time = ADC_ACQ_TIME(ADC_ACQ_TIME_MICROSECONDS, 40), // 3 us only settles ~10 kOhm; the sampling cap never charges -> readings come out low\n"
if "MICROSECONDS, 40)" in s:
    print("patch_adcacq: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_adcacq: external AIN acquisition time 3 us -> 40 us")
else:
    print("patch_adcacq: WARNING hunk not matched (upstream changed?)", file=sys.stderr)
sys.exit(0)
