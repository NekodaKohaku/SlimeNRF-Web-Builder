#!/usr/bin/env python3
# promicro_uf2 のボード定義に残る「実機 promicro 前提」の設定を無効化する。
# (P0.13 のプルは patch_promicro_p013.py が担当。こちらはそれ以外)
#
# 1) zephyr,user の vcc-gpios = <&gpio0 31 0>
#    実機 promicro はセンサー電源を P0.31 で入れる回路。対象モジュールには
#    その回路が無いのに、config で vcc を指定しないとこの既定値が残り、
#    board.c が PRE_KERNEL_1 で P0.31 を「出力・High」に固定してしまう。
#    P0.31 を UART TX などに使う構成と正面衝突する。
#    -> config が vcc を指定していないときだけ削除する。
#
# 2) &i2c0 { status = "okay" }  (pinctrl 既定 P0.24=SDA / P0.22=SCL)
#    ボード dts が無条件で TWIM を有効にするため、SPI 構成でも P0.24/P0.22 が
#    TWIM に握られたままになる。誰も使わないので PM がサスペンドし、
#    sleep 状態 (low-power-enable) でパッドが切断される。そのピンに何か
#    割り当てていると起動直後だけ動いて後で死ぬ、という嫌な挙動になる。
#    (nRF54L の i2c21 で実測済みの問題。同じ対策を 52840 にも入れる)
#    -> IMU が SPI かつ磁力計が I2C を使わない構成でのみ無効化する。
#
# 使い方: patch_promicro_cleanup.py "$CONFIG_JSON"
# board.c / dts が無い構成 (54L 等) では何もしない。
import json, os, re, sys

MARK = "SLIMENRF_PROMICRO_CLEANUP"
cfg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
pins = cfg.get("pins", {}) or {}
opts = cfg.get("options", {}) or {}
bus = cfg.get("bus", "spi")
mag_conn = opts.get("mag_conn", cfg.get("mag_conn", "none"))

dts = "boards/nordic/promicro_uf2/promicro_uf2.dts"
if not os.path.isfile(dts):
    print("patch_promicro_cleanup: promicro dts not found, skipped")
    sys.exit(0)

s = open(dts, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_promicro_cleanup: already applied"); sys.exit(0)

changed = []

# ---- 1) vcc-gpios ----
_vcc = pins.get("vcc")
if not (_vcc and _vcc != "none"):
    # 行末の \r を許容 (Windows の CRLF チェックアウト対策)
    m = re.search(r"^[ \t]*vcc-gpios\s*=\s*<[^>]*>;[ \t\r]*$", s, re.M)
    if m:
        s = s.replace(m.group(0),
                      "\t\t/* " + MARK + ": board default (P0.31 sensor power on real\n"
                      "\t\t * promicro) removed - this module has no such rail and the\n"
                      "\t\t * pin may be used for something else. */\n"
                      "\t\t/* " + m.group(0).strip() + " */",
                      1)
        changed.append("vcc-gpios removed")

# ---- 2) i2c0 ----
# SPI IMU かつ I2C 磁力計でもない場合、TWIM は誰も使わない
_i2c_used = (bus == "i2c") or (mag_conn in ("i2c", "i2c_shared"))
if not _i2c_used:
    m = re.search(r"(&i2c0\s*\{[^}]*?)status\s*=\s*\"okay\";", s, re.S)
    if m:
        s = s.replace(m.group(0),
                      m.group(1) + "status = \"disabled\"; /* " + MARK + ": SPI build, "
                      "TWIM would just squat on P0.24/P0.22 */",
                      1)
        changed.append("i2c0 disabled")

if not changed:
    print("patch_promicro_cleanup: nothing to change (vcc/i2c in use or anchors gone)")
    sys.exit(0)

open(dts, "w", encoding="utf-8", newline="").write(s)
print("patch_promicro_cleanup: " + ", ".join(changed))
