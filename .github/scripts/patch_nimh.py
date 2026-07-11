#!/usr/bin/env python3
import re
import sys

bat = "src/system/battery.c"
s = open(bat).read()
nimh = ("static const struct battery_level_point levels[] = {\n"
        "\t{ 10000, 1300 },\n\t{ 8500, 1270 },\n\t{ 7000, 1250 },\n\t{ 5500, 1230 },\n"
        "\t{ 4000, 1210 },\n\t{ 2500, 1190 },\n\t{ 1200, 1150 },\n\t{ 600, 1100 },\n"
        "\t{ 300, 1000 },\n\t{ 0, 930 },\n};")
s2 = re.sub(r"static const struct battery_level_point levels\[\] = \{.*?\};", nimh, s, count=1, flags=re.S)
if s2 == s:
    sys.exit("NiMH patch failed: battery.c levels[] pattern not found (upstream may have changed)")
open(bat, "w").write(s2)

pw = "src/system/power.c"
p = open(pw).read()
p2 = p.replace("battery_mV > 1500", "battery_mV >= 930")
if p2 == p:
    sys.exit("NiMH patch failed: power.c threshold not found (upstream may have changed)")
open(pw, "w").write(p2)

print("NiMH source patch applied")
