#!/usr/bin/env python3
# jiting fork の電池まわり修正。usage: patch_jiting_battery.py [battery_option]
#
# 1) battery.c input_positive (常時): fork は io-channels の生 AIN 番号を
#    そのまま input_positive に渡すが、SAADC の AIN0 エンコードは 1 始まり
#    (公式は 1 + channel)。fork 自社ボードは channel 12 (VDDHDIV5) の特殊
#    分岐しか通らないため未発覚。AIN 分圧ボードでは setup 失敗/誤ピン読み
#    -> power_thread "Failed to read battery voltage: -2" の原因。
#
# 2) battery_option == "nimh" のとき、公式 patch_nimh.py と同じ三点セット:
#    - battery.c levels[] を NiMH 曲線に置換
#    - power.c battery_available 閾値 1500 -> 930 mV
#    - connection.c 電圧表示を SoC -> 3.0-4.2V 窓へ (プロトコルは 2.45V が下限)
import re, sys

bat_opt = sys.argv[1] if len(sys.argv) > 1 else ""
MARK = "SLIMENRF_JITING_BATT"

# ---- 1) input_positive fix (always) ----
f = "src/system/battery.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_jiting_battery: already applied"); sys.exit(0)

old = ("\t\tif (iocp->channel == 12) {\n"
       "\t\t\taccp->input_positive = NRF_SAADC_VDDHDIV5;\n"
       "\t\t} else {\n"
       "\t\t\taccp->input_positive = iocp->channel;\n"
       "\t\t}\n").replace("\n", NL)
new = ("\t\tif (iocp->channel == 12) {\n"
       "\t\t\taccp->input_positive = NRF_SAADC_VDDHDIV5;\n"
       "\t\t} else {\n"
       "\t\t\t/* " + MARK + ": io-channels holds the raw AIN index; the SAADC\n"
       "\t\t\t * driver expects NRF_SAADC_AIN0(=1)-based values (official: 1 + ch). */\n"
       "\t\t\taccp->input_positive = 1 + iocp->channel;\n"
       "\t\t}\n").replace("\n", NL)
if old not in s:
    sys.exit("patch_jiting_battery: FAILED, input_positive anchor not found in battery.c")
s = s.replace(old, new, 1)

# ---- 2) NiMH curve (levels[] replace, same as official patch_nimh.py) ----
if bat_opt == "nimh":
    nimh = ("static const struct battery_level_point levels[] = {\n"
            "\t{ 10000, 1300 },\n\t{ 8500, 1270 },\n\t{ 7000, 1250 },\n\t{ 5500, 1230 },\n"
            "\t{ 4000, 1210 },\n\t{ 2500, 1190 },\n\t{ 1200, 1150 },\n\t{ 600, 1100 },\n"
            "\t{ 300, 1000 },\n\t{ 0, 930 },\n};").replace("\n", NL)
    s2 = re.sub(r"static const struct battery_level_point levels\[\] = \{.*?\};",
                lambda m: nimh, s, count=1, flags=re.S)
    if s2 == s:
        sys.exit("patch_jiting_battery: FAILED, levels[] pattern not found in battery.c")
    s = s2

open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_jiting_battery: battery.c OK" + (" (+NiMH curve)" if bat_opt == "nimh" else ""))

if bat_opt != "nimh":
    sys.exit(0)

# ---- 3) power.c battery_available threshold ----
pw = "src/system/power.c"
p = open(pw, encoding="utf-8", newline="").read()
p2 = p.replace("battery_mV > 1500", "battery_mV >= 930", 1)
if p2 == p:
    sys.exit("patch_jiting_battery: FAILED, power.c 1500mV threshold not found")
open(pw, "w", encoding="utf-8", newline="").write(p2)
print("patch_jiting_battery: power.c OK (battery_available >= 930 mV)")

# ---- 4) connection.c voltage display mapping (SoC -> 3.0-4.2V) ----
conn = "src/connection/connection.c"
c = open(conn, encoding="utf-8", newline="").read()
NLc = "\r\n" if "\r\n" in c else "\n"
anchor = "\tbattery_pptt /= 100;\n\tbatt = battery_pptt;\n".replace("\n", NLc)
if anchor not in c:
    sys.exit("patch_jiting_battery: FAILED, connection.c battery anchor not found")
c = c.replace(anchor,
    ("\tbattery_mV = 3000 + (battery_pptt * 1200 / 10000); // " + MARK + " NiMH display mapping: SoC -> Li-ion 3.0-4.2V window (protocol byte floors at 2.45V; a 1.2V cell would underflow)\n"
     ).replace("\n", NLc) + anchor, 1)
open(conn, "w", encoding="utf-8", newline="").write(c)
print("patch_jiting_battery: connection.c OK (NiMH voltage display mapping)")
