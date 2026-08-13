#!/usr/bin/env python3
# jiting fork の電池まわり修正。usage: patch_jiting_battery.py [battery_option]
#
# 1) 54L gain 表 + acquisition time 修正 (下記)。fork の input_positive
#    (0 基底) は NCS 3.2+ では正しい。触らない。
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

# ---- 1) (撤回) input_positive は fork の 0 基底が正しい ----
# NCS 3.2+ の dt-bindings は NRF_SAADC_AIN0 = 0 (実機 zephyr commit 9673eec75908 で確認)。
# 公式 main の "1 + channel" の方が off-by-one バグ (公式自身のコメントにも記載あり)。

# ---- 1b) 54L gain table (upstream-shared bug): nRF52 のみの 1/6,1/5,1/3 を選ぶと
#      54L の SAADC (gain 1/4,1/2,1,2,4 / ref 0.9V) で adc_channel_setup が -22。
oldg = ("\tif (max_adc_voltage < 0.6f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1;\n"
        "\telse if (max_adc_voltage < 1.2f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_2;\n"
        "\telse if (max_adc_voltage < 1.8f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_3;\n"
        "\telse if (max_adc_voltage < 2.4f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_4;\n"
        "\telse if (max_adc_voltage < 3.0f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_5;\n").replace("\n", NL)
newg = ("#if defined(CONFIG_SOC_SERIES_NRF54LX)\n"
        "\t/* " + MARK + ": 54L SAADC has only 1/4,1/2,1,2,4 gains, internal ref 0.9V.\n"
        "\t * Default 1/4 -> 3.6V range (same span as nRF52 1/6 @ 0.6V ref). */\n"
        "\tbattery_adc_gain = ADC_GAIN_1_4;\n"
        "\tif (max_adc_voltage < 0.9f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1;\n"
        "\telse if (max_adc_voltage < 1.8f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_2;\n"
        "#else\n"
        "\tif (max_adc_voltage < 0.6f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1;\n"
        "\telse if (max_adc_voltage < 1.2f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_2;\n"
        "\telse if (max_adc_voltage < 1.8f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_3;\n"
        "\telse if (max_adc_voltage < 2.4f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_4;\n"
        "\telse if (max_adc_voltage < 3.0f)\n"
        "\t\tbattery_adc_gain = ADC_GAIN_1_5;\n"
        "#endif\n").replace("\n", NL)
if oldg not in s:
    sys.exit("patch_jiting_battery: FAILED, gain table anchor not found in battery.c")
s = s.replace(oldg, newg, 1)

# ---- 1c) acquisition time 3us -> 40us: 高源阻抗の電池監視 (直列 1M 等) では
#      3us でサンプルコンデンサが充電しきれず、レール付近の偽値が出る。
#      40us は nRF52 の正規 enum 値でもあり 54L でも tacq 上限内。
olda = "\t\t.acquisition_time = ADC_ACQ_TIME(ADC_ACQ_TIME_MICROSECONDS, 3),\n".replace("\n", NL)
newa = ("\t\t/* " + MARK + ": 40us (was 3us) - required for high source impedance\n"
        "\t\t * battery sense (e.g. 1M series). Nordic spec: <=800k needs 40us. */\n"
        "\t\t.acquisition_time = ADC_ACQ_TIME(ADC_ACQ_TIME_MICROSECONDS, 40),\n").replace("\n", NL)
if olda not in s:
    sys.exit("patch_jiting_battery: FAILED, acquisition_time anchor not found in battery.c")
s = s.replace(olda, newa, 1)

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
