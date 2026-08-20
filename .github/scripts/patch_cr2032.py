#!/usr/bin/env python3
# battery.c: swap in a CR2032 discharge curve.
#
# Upstream only ships Li-ion mappings (4.15 V down to 3.2 V). A CR2032 never
# leaves 3.0 V, so against those tables it reads empty from the moment it is
# fitted. Against the NiMH table it is the opposite problem - the curve tops out
# at 1.30 V, so a coin cell reads 100% until it dies.
#
# The curve below is deliberately pessimistic at the bottom. A CR2032's internal
# resistance starts around 10-20 ohm and climbs steeply with depth of discharge,
# so under a radio pulse the rail sags well below the open-circuit voltage the
# ADC sees between packets. Reporting empty a little early is much cheaper than
# browning out mid-session.
#
# No display remap is needed, unlike NiMH. The protocol packs voltage as
# battery_mV/10 - 245, i.e. 2.45-5.00 V, and a CR2032 sits inside that window
# for all of its useful life. Only the last stretch below 2.45 V clamps to the
# floor, by which point the curve already reports 0%.
#
# Pairs with adc=internal: with the cell wired straight to VDD (no regulator or
# boost in between) the SoC's internal VDD measurement is the cell voltage, so
# no divider and no extra pin are needed.
import re
import sys

bat = "src/system/battery.c"
s = open(bat, encoding="utf-8").read()

if "SLIMENRF_CR2032" in s:
    print("patch_cr2032: already applied")
    sys.exit(0)

cr2032 = (
    "/* SLIMENRF_CR2032: 3.0 V nominal, long plateau near 2.9 V, knee around\n"
    " * 2.7 V, then a steep tail. Conservative at the bottom because the cell's\n"
    " * internal resistance climbs with depth of discharge and it sags under\n"
    " * radio pulses far more than its open-circuit voltage suggests. */\n"
    "static const struct battery_level_point levels[] = {\n"
    "\t{ 10000, 3000 },\n"
    "\t{ 9000, 2920 },\n"
    "\t{ 7000, 2880 },\n"
    "\t{ 5000, 2840 },\n"
    "\t{ 3000, 2780 },\n"
    "\t{ 1500, 2700 },\n"
    "\t{ 700, 2600 },\n"
    "\t{ 300, 2450 },\n"
    "\t{ 0, 2200 },\n"
    "};"
)

s2 = re.sub(
    r"static const struct battery_level_point levels\[\] = \{.*?\};",
    cr2032, s, count=1, flags=re.S,
)
if s2 == s:
    sys.exit("patch_cr2032: FAILED, battery.c levels[] pattern not found "
             "(upstream may have changed)")
open(bat, "w", encoding="utf-8").write(s2)

# "Is a battery present" gate. Upstream requires > 1.5 V, which a CR2032 clears
# for its whole life, so the default already works - assert it rather than
# silently depending on it.
pw = "src/system/power.c"
p = open(pw, encoding="utf-8").read()
if "battery_mV > 1500" not in p and "battery_mV >= 930" not in p:
    sys.exit("patch_cr2032: FAILED, power.c battery-present threshold not found")

print("patch_cr2032: applied (CR2032 discharge curve)")
