#!/usr/bin/env python3
# jiting ESB OTA を MCUboot 二槽バックエンドに切り替える (mcuboot ビルド専用)。
#
# 変更点 (すべて #if CONFIG_BOOTLOADER_MCUBOOT ゲート、hex/uf2 ビルドは不変):
#   1) defines: staging = mcuboot_secondary (slot1) 固定。54L15 でも OTA 有効化
#      (fork 本家は 54L OTA 非対応。二槽化により可能になる)
#   2) handle_begin: staging アドレス計算と実行中コード重なりチェックを
#      slot1 固定に置換 (別区画なので重なり得ない)
#   3) handle_activate: bootloader settings + RAM コピーの代わりに
#      trailer ページ確保 + boot_request_upgrade() + 通常再起動。
#      実際の slot1 -> slot0 上書きは mcuboot が次回起動時に実行
#      (コピー元 slot1 は常に完全 = どの時点で断電しても復旧可能)
#
# 前提: gen_mcuboot_files.py の二槽 pm_static (mcuboot_secondary) と
#       overwrite-only sysbuild、prj.conf の IMG_MANAGER 系 Kconfig。
# 実行順: patch_mcuboot_dfu_jiting.py の後 (esb_ota.c の同一ブロックを
#         以前ゲートしていた hunk はそちらから削除済み)。
import sys

MARK = "SLIMENRF_OTA_MCUBOOT"
f = "src/system/esb_ota.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_esb_ota_mcuboot: already applied"); sys.exit(0)
changed = 0

def repl(old, new):
    global s, changed
    o = old.replace("\n", NL); n = new.replace("\n", NL)
    if s.count(o) == 1:
        s = s.replace(o, n, 1); changed += 1; return True
    print(f"patch_esb_ota_mcuboot: hunk not found (count={s.count(o)}):\n{old[:120]}", file=sys.stderr)
    return False

# ---- 1) defines: mcuboot 分岐を SoC 分岐の前に挿入 ----
repl(
"#if CONFIG_SOC_NRF52840\n"
"#define OTA_FLASH_END        0xEE000 /* End of app partition (before NVS) */\n"
"#define OTA_USE_RAM_ENGINE   0\n"
"#define BOOTLOADER_SETTINGS_ADDR BOOTLOADER_SETTINGS_ADDR_52840\n"
"#define OTA_SUPPORTED        1\n",
"#if CONFIG_BOOTLOADER_MCUBOOT\n"
"/* " + MARK + ": 二槽バックエンド。データは slot1 (mcuboot_secondary) へ、\n"
" * activate は upgrade magic を書いて再起動するだけ。実際の上書きは\n"
" * mcuboot が次回起動時に行う。nRF52840 / nRF54L15 共通。 */\n"
"#include <pm_config.h>\n"
"#include <zephyr/dfu/mcuboot.h>\n"
"#define OTA_FLASH_END        (PM_APP_ADDRESS + PM_APP_SIZE) /* final image bound (slot0 end) */\n"
"#define OTA_STAGING_BASE     PM_MCUBOOT_SECONDARY_ADDRESS\n"
"#define OTA_STAGING_SIZE     PM_MCUBOOT_SECONDARY_SIZE\n"
"#define OTA_USE_RAM_ENGINE   0\n"
"#define BOOTLOADER_SETTINGS_ADDR 0\n"
"#define OTA_SUPPORTED        1\n"
"#elif CONFIG_SOC_NRF52840\n"
"#define OTA_FLASH_END        0xEE000 /* End of app partition (before NVS) */\n"
"#define OTA_USE_RAM_ENGINE   0\n"
"#define BOOTLOADER_SETTINGS_ADDR BOOTLOADER_SETTINGS_ADDR_52840\n"
"#define OTA_SUPPORTED        1\n")

# ---- 2) handle_begin: staging = slot1 固定 ----
repl(
"\tuint32_t image_pages = (image_size + OTA_FLASH_PAGE_SIZE - 1) / OTA_FLASH_PAGE_SIZE;\n"
"\tota.staging_base = OTA_FLASH_END - (image_pages * OTA_FLASH_PAGE_SIZE);\n"
"\tota.staging_base &= ~(OTA_FLASH_PAGE_SIZE - 1); /* Page-align */\n"
"\tota.page_buf_flash_addr = ota.staging_base;\n"
"\n"
"\t/* Verify staging area doesn't overlap with currently running firmware.\n"
"\t * Gate on live image end (_flash_used), not the new image_size — a smaller\n"
"\t * update must not place staging over still-executing code. */\n"
"\textern char _flash_used[];\n"
"\tuint32_t running_end = (uint32_t)_flash_used;\n"
"\tif (running_end < OTA_FLASH_BASE) {\n"
"\t\trunning_end = OTA_FLASH_BASE;\n"
"\t}\n"
"\tif (ota.staging_base < running_end) {\n"
"\t\tLOG_ERR(\"OTA BEGIN: staging 0x%05X overlaps running firmware (ends 0x%05X, new size %u)\",\n"
"\t\t\tota.staging_base, running_end, image_size);\n"
"\t\tota.state = OTA_STATE_ERROR;\n"
"\t\tota.error_code = OTA_STATUS_SIZE_ERROR;\n"
"\t\tota_send_status();\n"
"\t\treturn -ENOMEM;\n"
"\t}\n",
"#if CONFIG_BOOTLOADER_MCUBOOT\n"
"\t/* " + MARK + ": staging = slot1 先頭固定。実行中コード (slot0) とは\n"
"\t * 別区画なので重なりチェックは不要。サイズは BEGIN の\n"
"\t * OTA_FLASH_END 検査で既に slot0 容量以下が保証されている。\n"
"\t * image_pages は直後の LOG_INF が両分岐共通で参照するため計算する。 */\n"
"\tuint32_t image_pages = (image_size + OTA_FLASH_PAGE_SIZE - 1) / OTA_FLASH_PAGE_SIZE;\n"
"\tota.staging_base = OTA_STAGING_BASE;\n"
"\tota.page_buf_flash_addr = ota.staging_base;\n"
"#else\n"
"\tuint32_t image_pages = (image_size + OTA_FLASH_PAGE_SIZE - 1) / OTA_FLASH_PAGE_SIZE;\n"
"\tota.staging_base = OTA_FLASH_END - (image_pages * OTA_FLASH_PAGE_SIZE);\n"
"\tota.staging_base &= ~(OTA_FLASH_PAGE_SIZE - 1); /* Page-align */\n"
"\tota.page_buf_flash_addr = ota.staging_base;\n"
"\n"
"\t/* Verify staging area doesn't overlap with currently running firmware.\n"
"\t * Gate on live image end (_flash_used), not the new image_size — a smaller\n"
"\t * update must not place staging over still-executing code. */\n"
"\textern char _flash_used[];\n"
"\tuint32_t running_end = (uint32_t)_flash_used;\n"
"\tif (running_end < OTA_FLASH_BASE) {\n"
"\t\trunning_end = OTA_FLASH_BASE;\n"
"\t}\n"
"\tif (ota.staging_base < running_end) {\n"
"\t\tLOG_ERR(\"OTA BEGIN: staging 0x%05X overlaps running firmware (ends 0x%05X, new size %u)\",\n"
"\t\t\tota.staging_base, running_end, image_size);\n"
"\t\tota.state = OTA_STATE_ERROR;\n"
"\t\tota.error_code = OTA_STATUS_SIZE_ERROR;\n"
"\t\tota_send_status();\n"
"\t\treturn -ENOMEM;\n"
"\t}\n"
"#endif /* CONFIG_BOOTLOADER_MCUBOOT */\n")

# ---- 3a) handle_activate: settings 準備 -> upgrade magic ----
repl(
"\t/* Compute bootloader settings (will be written by RAM copier in protected context) */\n"
"\tint err = esb_ota_flash_prepare_bootloader_settings(ota.staging_base, ota.image_size,\n"
"\t\t\t\t\t\t\t    ota.page_buf);\n",
"#if CONFIG_BOOTLOADER_MCUBOOT\n"
"\t/* " + MARK + ": trailer ページを確保してから upgrade magic を書く\n"
"\t * (nRF52840 は旧データが残った trailer には write できないため)。\n"
"\t * mcuboot は次回起動時に slot1 -> slot0 を上書きコピーする。 */\n"
"\tesb_ota_flash_erase_page(OTA_STAGING_BASE + OTA_STAGING_SIZE - OTA_FLASH_PAGE_SIZE);\n"
"\tint err = boot_request_upgrade(BOOT_UPGRADE_PERMANENT);\n"
"#else\n"
"\t/* Compute bootloader settings (will be written by RAM copier in protected context) */\n"
"\tint err = esb_ota_flash_prepare_bootloader_settings(ota.staging_base, ota.image_size,\n"
"\t\t\t\t\t\t\t    ota.page_buf);\n"
"#endif\n")

# ---- 3b) handle_activate: RAM コピー呼び出しを mcuboot では無効化 ----
repl(
"\t/* Copy from staging to final location (with IRQs disabled) and reset */\n"
"\tesb_ota_flash_copy_and_reset(ota.staging_base, ota.target_flash_base, ota.image_size);\n",
"#if !CONFIG_BOOTLOADER_MCUBOOT\n"
"\t/* Copy from staging to final location (with IRQs disabled) and reset */\n"
"\tesb_ota_flash_copy_and_reset(ota.staging_base, ota.target_flash_base, ota.image_size);\n"
"#endif\n"
"\t/* (" + MARK + ": mcuboot backend は下の通常再起動のみ。\n"
"\t * 次回起動で mcuboot が slot1 -> slot0 を実行する) */\n")

if changed == 4:
    open(f, "w", encoding="utf-8", newline="").write(s)
    print(f"patch_esb_ota_mcuboot: esb_ota.c {changed}/4 OK")
else:
    print(f"patch_esb_ota_mcuboot: FAILED, only {changed}/4 hunks matched", file=sys.stderr)
    sys.exit(1)
