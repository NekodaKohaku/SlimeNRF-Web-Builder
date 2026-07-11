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

# The SlimeVR protocol packs voltage into ONE byte:  batt_v = battery_mV/10 - 245,
# so it can only express 2.45-5.00 V. A ~1.2 V NiMH cell underflows, clamps to 0, and
# the server shows the floor value 2.45 V forever -- that is not a reading at all.
#
# Report the voltage DERIVED FROM THE PERCENTAGE instead of scaling the raw cell
# voltage (this is what SlimeVR-Tracker-ESP does: reportVoltage = 3.0 + level * 1.2).
# Mapping the state of charge onto a Li-ion's real 3.0-4.2 V range keeps voltage and
# percentage mutually consistent -- anyone (or anything) reading 3.44 V off a Li-ion
# curve gets 37%, which is exactly what we report. Scaling the raw voltage instead
# (e.g. x3.2) lands in range but makes the two contradict each other.
# The percentage itself is untouched and stays on the real NiMH curve above.
conn = "src/connection/connection.c"
c = open(conn, encoding="utf-8").read()
anchor = "\tbattery_pptt /= 100;\n\tbatt = battery_pptt;\n"
if "NiMH display mapping" in c:
    print("NiMH voltage mapping: already applied")
elif anchor in c:
    c = c.replace(anchor,
        "\tbattery_mV = 3000 + (battery_pptt * 1200 / 10000); // NiMH display mapping: SoC -> Li-ion 3.0-4.2V window (protocol byte floors at 2.45V; a 1.2V cell would underflow)\n"
        + anchor, 1)
    open(conn, "w", encoding="utf-8").write(c)
    print("NiMH voltage mapping applied (SoC -> 3.0-4.2 V, self-consistent)")
else:
    sys.exit("NiMH patch failed: connection_update_battery anchor not found")

print("NiMH source patch applied")
