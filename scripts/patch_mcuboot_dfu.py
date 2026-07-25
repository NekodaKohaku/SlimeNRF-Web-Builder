#!/usr/bin/env python3
# MCUboot UART DFU 入口パッチ:
# 既存の `dfu` コンソールコマンドとリセットモード 3/4 (ボタン 4 回連打) から、
# Zephyr の retention boot-mode (bootmode_set + 再起動) 経由で MCUboot serial
# recovery を要求できるようにする。MCUboot 側は CONFIG_BOOT_SERIAL_BOOT_MODE で
# 次回起動時にこれを検出する。
# SlimeVR-Tracker-nRF 内で実行。冪等 (再実行しても安全)。他パッチと同スタイル。
import sys

total = 0

def patch(f, hunks):
    global total
    s = open(f, encoding="utf-8", newline="").read()
    NL = "\r\n" if "\r\n" in s else "\n"
    if "MCUBOOT_BOOTLOADER" in s:
        print(f"patch_mcuboot_dfu: {f} already applied")
        return
    changed = 0
    for old, new in hunks:
        o = old.replace("\n", NL); n = new.replace("\n", NL)
        if o in s:
            s = s.replace(o, n, 1); changed += 1
    if changed == len(hunks):
        open(f, "w", encoding="utf-8", newline="").write(s)
        print(f"patch_mcuboot_dfu: {f} applied {changed}/{len(hunks)}")
    else:
        print(f"patch_mcuboot_dfu: WARNING {f} only {changed}/{len(hunks)} hunks applied", file=sys.stderr)
        sys.exit(1)
    total += changed

DEFS_OLD = (
"#define DFU_EXISTS CONFIG_BUILD_OUTPUT_UF2 || CONFIG_BOARD_HAS_NRF5_BOOTLOADER\n"
"#define ADAFRUIT_BOOTLOADER CONFIG_BUILD_OUTPUT_UF2\n"
"#define NRF5_BOOTLOADER CONFIG_BOARD_HAS_NRF5_BOOTLOADER\n")
DEFS_NEW = (
"#define DFU_EXISTS CONFIG_BUILD_OUTPUT_UF2 || CONFIG_BOARD_HAS_NRF5_BOOTLOADER || CONFIG_BOOTLOADER_MCUBOOT\n"
"#define ADAFRUIT_BOOTLOADER CONFIG_BUILD_OUTPUT_UF2\n"
"#define NRF5_BOOTLOADER CONFIG_BOARD_HAS_NRF5_BOOTLOADER\n"
"#define MCUBOOT_BOOTLOADER CONFIG_BOOTLOADER_MCUBOOT\n"
"\n"
"#if MCUBOOT_BOOTLOADER\n"
"#include <zephyr/retention/bootmode.h>\n"
"#endif\n")

# console.c: `dfu` コマンドハンドラー
# (タブ 3 個のインデントはコマンドブロック固有。コンソール起動時の
#  button_read() ブロックはタブ 2 個で USB 専用のため対象外)
patch("src/console.c", [
    (DEFS_OLD, DEFS_NEW),
    ("#if ADAFRUIT_BOOTLOADER\n"
     "\t\t\tNRF_POWER->GPREGRET = 0x57;\n"
     "\t\t\tsys_request_system_reboot(false);\n"
     "#endif\n",
     "#if ADAFRUIT_BOOTLOADER\n"
     "\t\t\tNRF_POWER->GPREGRET = 0x57;\n"
     "\t\t\tsys_request_system_reboot(false);\n"
     "#endif\n"
     "#if MCUBOOT_BOOTLOADER\n"
     "\t\t\tbootmode_set(BOOT_MODE_TYPE_BOOTLOADER); // MCUboot serial recovery on next boot\n"
     "\t\t\tsys_request_system_reboot(false);\n"
     "#endif\n"),
])

# system.c: リセットモード 3/4 (4 回連打) の DFU パス
patch("src/system/system.c", [
    (DEFS_OLD, DEFS_NEW),
    ("\t\tLOG_INF(\"DFU requested\");\n"
     "#if ADAFRUIT_BOOTLOADER\n"
     "\t\tNRF_POWER->GPREGRET = 0x57; // DFU_MAGIC_UF2_RESET\n"
     "\t\tsys_request_system_reboot(false);\n"
     "#endif\n",
     "\t\tLOG_INF(\"DFU requested\");\n"
     "#if ADAFRUIT_BOOTLOADER\n"
     "\t\tNRF_POWER->GPREGRET = 0x57; // DFU_MAGIC_UF2_RESET\n"
     "\t\tsys_request_system_reboot(false);\n"
     "#endif\n"
     "#if MCUBOOT_BOOTLOADER\n"
     "\t\tbootmode_set(BOOT_MODE_TYPE_BOOTLOADER); // MCUboot serial recovery on next boot\n"
     "\t\tsys_request_system_reboot(false);\n"
     "#endif\n"),
])

print(f"patch_mcuboot_dfu: done ({total} hunks)")
