#!/usr/bin/env python3
# jiting fork 用 MCUboot UART DFU 入口パッチ (公式 patch_mcuboot_dfu.py の fork 版)。
# - console `dfu` コマンドと ボタン 4 連打 (sys_reset_mode 3/4) から
#   Zephyr retention boot-mode 経由で MCUboot serial recovery を要求
# - 52840: fork の ESB-OTA 適用エンジンは adafruit 布局前提の直書きのため、
#   MCUboot 布局では危険 -> MCUboot ビルドでは OTA_SUPPORTED=0 に落とす
#   (更新は MCUboot UART DFU 経由。54L15 は fork 自身が OTA_SUPPORTED=0)
import sys

total_files = 0

def patch(f, hunks, mark):
    global total_files
    s = open(f, encoding="utf-8", newline="").read()
    NL = "\r\n" if "\r\n" in s else "\n"
    if mark in s:
        print(f"patch_mcuboot_dfu_jiting: {f} already applied")
        return
    changed = 0
    for old, new in hunks:
        o = old.replace("\n", NL); n = new.replace("\n", NL)
        if o in s:
            s = s.replace(o, n, 1); changed += 1
    if changed == len(hunks):
        open(f, "w", encoding="utf-8", newline="").write(s)
        print(f"patch_mcuboot_dfu_jiting: {f} applied {changed}/{len(hunks)}")
        total_files += 1
    else:
        print(f"patch_mcuboot_dfu_jiting: FAILED {f} only {changed}/{len(hunks)} hunks", file=sys.stderr)
        sys.exit(1)

DEFS_OLD = (
"#define DFU_EXISTS (CONFIG_BUILD_OUTPUT_UF2 || CONFIG_BOARD_HAS_NRF5_BOOTLOADER)\n"
"#define ADAFRUIT_BOOTLOADER CONFIG_BUILD_OUTPUT_UF2\n"
"#define NRF5_BOOTLOADER CONFIG_BOARD_HAS_NRF5_BOOTLOADER\n")
DEFS_NEW = (
"#define DFU_EXISTS (CONFIG_BUILD_OUTPUT_UF2 || CONFIG_BOARD_HAS_NRF5_BOOTLOADER || CONFIG_BOOTLOADER_MCUBOOT)\n"
"#define ADAFRUIT_BOOTLOADER CONFIG_BUILD_OUTPUT_UF2\n"
"#define NRF5_BOOTLOADER CONFIG_BOARD_HAS_NRF5_BOOTLOADER\n"
"#define MCUBOOT_BOOTLOADER CONFIG_BOOTLOADER_MCUBOOT\n"
"\n"
"#if MCUBOOT_BOOTLOADER\n"
"#include <zephyr/retention/bootmode.h>\n"
"#endif\n")

# ---- console.c: defs + `dfu` コマンドに MCUboot 分岐 ----
patch("src/console.c", [
    (DEFS_OLD, DEFS_NEW),
    ("\tk_msleep(100); // Wait for GPREGRET to be written\n"
     "\tsys_request_system_reboot(false);\n"
     "#else\n"
     "\tARG_UNUSED(arg);\n"
     "#endif\n"
     "#if NRF5_BOOTLOADER\n"
     "\tgpio_pin_configure(gpio_dev, 19, GPIO_OUTPUT | GPIO_OUTPUT_INIT_LOW);\n"
     "#endif\n"
     "}\n",
     "\tk_msleep(100); // Wait for GPREGRET to be written\n"
     "\tsys_request_system_reboot(false);\n"
     "#else\n"
     "\tARG_UNUSED(arg);\n"
     "#endif\n"
     "#if NRF5_BOOTLOADER\n"
     "\tgpio_pin_configure(gpio_dev, 19, GPIO_OUTPUT | GPIO_OUTPUT_INIT_LOW);\n"
     "#endif\n"
     "#if MCUBOOT_BOOTLOADER\n"
     "\tprintk(\"Entering MCUboot serial recovery...\\n\");\n"
     "\tbootmode_set(BOOT_MODE_TYPE_BOOTLOADER); // picked up by CONFIG_BOOT_SERIAL_BOOT_MODE\n"
     "\tsys_request_system_reboot(false);\n"
     "#endif\n"
     "}\n"),
], "MCUBOOT_BOOTLOADER")

# ---- system.c: defs + sys_reset_mode 3/4 (ボタン 4 連打) に MCUboot 分岐 ----
patch("src/system/system.c", [
    (DEFS_OLD, DEFS_NEW),
    ("\t\tLOG_INF(\"DFU requested\");\n"
     "#if ADAFRUIT_BOOTLOADER\n"
     "\t\tNRF_POWER->GPREGRET = ADAFRUIT_DFU_MAGIC_UF2_RESET;\n"
     "\t\tsys_request_system_reboot(false);\n"
     "#endif\n"
     "#if NRF5_BOOTLOADER\n"
     "\t\tgpio_pin_configure(gpio_dev, 19, GPIO_OUTPUT | GPIO_OUTPUT_INIT_LOW);\n"
     "#endif\n"
     "\t\tbreak;\n",
     "\t\tLOG_INF(\"DFU requested\");\n"
     "#if ADAFRUIT_BOOTLOADER\n"
     "\t\tNRF_POWER->GPREGRET = ADAFRUIT_DFU_MAGIC_UF2_RESET;\n"
     "\t\tsys_request_system_reboot(false);\n"
     "#endif\n"
     "#if NRF5_BOOTLOADER\n"
     "\t\tgpio_pin_configure(gpio_dev, 19, GPIO_OUTPUT | GPIO_OUTPUT_INIT_LOW);\n"
     "#endif\n"
     "#if MCUBOOT_BOOTLOADER\n"
     "\t\tbootmode_set(BOOT_MODE_TYPE_BOOTLOADER); // MCUboot serial recovery on next boot\n"
     "\t\tsys_request_system_reboot(false);\n"
     "#endif\n"
     "\t\tbreak;\n"),
], "MCUBOOT_BOOTLOADER")

# ---- esb_ota.c: 52840 の OTA 適用を MCUboot ビルドでは無効化 ----
patch("src/system/esb_ota.c", [
    ("#if CONFIG_SOC_NRF52840\n"
     "#define OTA_FLASH_END        0xEE000 /* End of app partition (before NVS) */\n"
     "#define OTA_USE_RAM_ENGINE   0\n"
     "#define BOOTLOADER_SETTINGS_ADDR BOOTLOADER_SETTINGS_ADDR_52840\n"
     "#define OTA_SUPPORTED        1\n",
     "#if CONFIG_SOC_NRF52840 && !CONFIG_BOOTLOADER_MCUBOOT\n"
     "#define OTA_FLASH_END        0xEE000 /* End of app partition (before NVS) */\n"
     "#define OTA_USE_RAM_ENGINE   0\n"
     "#define BOOTLOADER_SETTINGS_ADDR BOOTLOADER_SETTINGS_ADDR_52840\n"
     "#define OTA_SUPPORTED        1\n"
     "#elif CONFIG_SOC_NRF52840 /* SLIMENRF_MCUBOOT: adafruit-layout OTA map is invalid\n"
     " * under MCUboot partitions; updates go via MCUboot UART DFU instead */\n"
     "#define OTA_FLASH_END        (OTA_FLASH_BASE + 256 * 1024)\n"
     "#define OTA_USE_RAM_ENGINE   0\n"
     "#define BOOTLOADER_SETTINGS_ADDR 0\n"
     "#define OTA_SUPPORTED        0\n"),
], "SLIMENRF_MCUBOOT")

print(f"patch_mcuboot_dfu_jiting: done ({total_files} files)")
