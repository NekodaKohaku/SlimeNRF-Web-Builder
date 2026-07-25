#!/usr/bin/env python3
# mcuboot の MCUBOOT_WATCHDOG_FEED() を raw レジスタ書き込みで確実化する。
#
# 背景: jiting fork のアプリは task watchdog の HW fallback (54L: WDT31,
# 52840: WDT) を起動する。nRF の WDT は一度起動すると停止不可能で、
# ソフトリセットを跨いで走り続ける。`dfu` で MCUboot serial recovery に
# 入っても、mcuboot 側の feed が実際に効いていないと約 5 秒
# (TASK_WDT_HW_FALLBACK_DELAY) で WDT リセットされ、boot mode は既に
# クリア済みのためアプリへ戻ってしまう (実測: ping 応答後 ~5 秒で切断)。
#
# Nordic 自身の 54L15 サンプルは軒並み CONFIG_BOOT_WATCHDOG_FEED=n に
# しており、54L の既定 feed 経路は当てにならない。そこで Kconfig の状態に
# かかわらず、mcuboot_config.h の feed マクロを MDK レジスタ直書きで
# 上書きする (reload 値 0x6E524635 は WDT RR の固定マジック)。
# 起動していない WDT への RR 書き込みは無害なので、公式ビルド
# (watchdog なし) に入っても副作用はない。
#
# 実行場所: zephyr-workspace/SlimeVR-Tracker-nRF (patch_mcuboot_pwr.py と同じ)
import os, sys

CANDIDATES = (
    "../bootloader/mcuboot/boot/zephyr/include/mcuboot_config/mcuboot_config.h",
    "../modules/mcuboot/boot/zephyr/include/mcuboot_config/mcuboot_config.h",
)

path = sys.argv[1] if len(sys.argv) > 1 else next(
    (p for p in CANDIDATES if os.path.isfile(p)), None)
if not path or not os.path.isfile(path):
    sys.exit("patch_mcuboot_wdtfeed: mcuboot_config.h not found: " + ", ".join(CANDIDATES))

MARK = "SLIMENRF_WDT_FEED"
src = open(path, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in src else "\n"
if MARK in src:
    print(f"patch_mcuboot_wdtfeed: already applied ({path})")
    sys.exit(0)

ANCHOR = "#ifndef MCUBOOT_WATCHDOG_SETUP"
if ANCHOR not in src:
    sys.exit("patch_mcuboot_wdtfeed: FAILED, anchor not found in mcuboot_config.h")

BLOCK = r"""
/* ==== SLIMENRF_WDT_FEED (SlimeNRF-Web-Builder が挿入) ====
 * アプリが起動した WDT はソフトリセット後も走り続けるため、serial
 * recovery 中に確実に餌をやる。Kconfig 依存の既定実装 (54L では Nordic
 * サンプル自身が無効化している) を raw レジスタ書き込みで置き換える。
 * 起動していないインスタンスへの RR 書き込みは無視されるだけで無害。 */
#if defined(CONFIG_SOC_FAMILY_NORDIC_NRF) || defined(CONFIG_SOC_FAMILY_NRF)
#include <nrf.h>
#define SLIMENRF_WDT_FEED_INST(inst)                     \
    do {                                                 \
        for (unsigned int zzi = 0; zzi < 8; zzi++) {     \
            (inst)->RR[zzi] = 0x6E524635UL;              \
        }                                                \
    } while (0)
#if defined(NRF_WDT30) && defined(NRF_WDT31)
#undef MCUBOOT_WATCHDOG_FEED
#define MCUBOOT_WATCHDOG_FEED()              \
    do {                                     \
        SLIMENRF_WDT_FEED_INST(NRF_WDT30);   \
        SLIMENRF_WDT_FEED_INST(NRF_WDT31);   \
    } while (0)
#elif defined(NRF_WDT31)
#undef MCUBOOT_WATCHDOG_FEED
#define MCUBOOT_WATCHDOG_FEED() SLIMENRF_WDT_FEED_INST(NRF_WDT31)
#elif defined(NRF_WDT0) && defined(NRF_WDT1)
#undef MCUBOOT_WATCHDOG_FEED
#define MCUBOOT_WATCHDOG_FEED()              \
    do {                                     \
        SLIMENRF_WDT_FEED_INST(NRF_WDT0);    \
        SLIMENRF_WDT_FEED_INST(NRF_WDT1);    \
    } while (0)
#elif defined(NRF_WDT0)
#undef MCUBOOT_WATCHDOG_FEED
#define MCUBOOT_WATCHDOG_FEED() SLIMENRF_WDT_FEED_INST(NRF_WDT0)
#elif defined(NRF_WDT)
#undef MCUBOOT_WATCHDOG_FEED
#define MCUBOOT_WATCHDOG_FEED() SLIMENRF_WDT_FEED_INST(NRF_WDT)
#endif
#endif /* Nordic */

"""

src = src.replace(ANCHOR, BLOCK.replace("\n", NL) + ANCHOR, 1)
open(path, "w", encoding="utf-8", newline="").write(src)
print(f"patch_mcuboot_wdtfeed: applied ({path})")
