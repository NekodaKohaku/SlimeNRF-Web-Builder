#!/usr/bin/env python3
# mcuboot 自身の main.c に電源自锁 (raw HAL) を追記する。
# 実行場所: zephyr-workspace/SlimeVR-Tracker-nRF (build-single.yml の
# "Enable MCUboot UART DFU" ステップ)。冪等 (二回目以降は何もしない)。
#
# 二重の保険でラッチする:
#   1) SYS_INIT EARLY (全 init の最前、電源投入後 <1ms)
#   2) main() 冒頭 (watchdog 直後、電源投入後 ~10-30ms) で明示的に呼ぶ
# どちらも 0.5s DFU 待機ウィンドウよりはるかに早い。EARLY が環境要因で
# 効かない場合でも main() 側が確実にラッチする。
#
# DT は gen_mcuboot_files.py が mcuboot.overlay に出力する
# zephyr,user { pwr-gpios } を読む。prop が無いビルドでは空関数になり無害。
# nRF52 / nRF54L 両対応 (NRF_GPIO_PIN_MAP が吸収)。
import os, sys

CANDIDATES = (
    "../bootloader/mcuboot/boot/zephyr/main.c",   # NCS 標準レイアウト
    "../modules/mcuboot/boot/zephyr/main.c",      # 念のため
)

path = sys.argv[1] if len(sys.argv) > 1 else next(
    (p for p in CANDIDATES if os.path.isfile(p)), None)
if not path or not os.path.isfile(path):
    sys.exit("patch_mcuboot_pwr: mcuboot main.c not found: " + ", ".join(CANDIDATES))

MARK = "SLIMENRF_PWR_LATCH"
src = open(path, encoding="utf-8").read()
if MARK in src:
    print(f"patch_mcuboot_pwr: already applied ({path})")
    sys.exit(0)

BLOCK = """
/* ==== SLIMENRF_PWR_LATCH (SlimeNRF-Web-Builder が挿入) ====
 * 電源自锁: zephyr,user の pwr-gpios を raw HAL でラッチする。
 * レジスタ書き込みのみで、カーネル・ドライバ・クロックに依存しない。
 * EARLY SYS_INIT と main() 冒頭の両方から呼ばれる (冪等)。
 */
#include <zephyr/init.h>
#include <zephyr/devicetree.h>
#include <zephyr/dt-bindings/gpio/gpio.h>
#include <hal/nrf_gpio.h>

#define SLIMENRF_PWR_NODE DT_PATH(zephyr_user)
#if DT_NODE_HAS_PROP(SLIMENRF_PWR_NODE, pwr_gpios)
static int slimenrf_pwr_latch(void)
{
	uint32_t pin = NRF_GPIO_PIN_MAP(
		DT_PROP(DT_GPIO_CTLR(SLIMENRF_PWR_NODE, pwr_gpios), port),
		DT_GPIO_PIN(SLIMENRF_PWR_NODE, pwr_gpios));

	nrf_gpio_cfg(pin, NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT,
		     NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE);
#if (DT_GPIO_FLAGS(SLIMENRF_PWR_NODE, pwr_gpios) & GPIO_ACTIVE_LOW)
	nrf_gpio_pin_clear(pin);
#else
	nrf_gpio_pin_set(pin);
#endif
	return 0;
}
SYS_INIT(slimenrf_pwr_latch, EARLY, 0);
#else
static inline int slimenrf_pwr_latch(void) { return 0; }
#endif
"""

# ---- 1) main() の直前に関数ブロックを挿入 ----
ANCHOR_MAIN = "\nint main(void)\n"
if ANCHOR_MAIN not in src:
    sys.exit(f"patch_mcuboot_pwr: anchor 'int main(void)' not found in {path}")
src = src.replace(ANCHOR_MAIN, "\n" + BLOCK + "\nint main(void)\n", 1)

# ---- 2) main() 冒頭 (watchdog 直後) に呼び出しを挿入 ----
ANCHOR_WDT = "MCUBOOT_WATCHDOG_FEED();"
if ANCHOR_WDT not in src:
    sys.exit(f"patch_mcuboot_pwr: anchor MCUBOOT_WATCHDOG_FEED not found in {path}")
src = src.replace(
    ANCHOR_WDT,
    ANCHOR_WDT + "\n\n    /* SLIMENRF: 電源自锁 (EARLY の保険。冪等なので二重実行は無害) */\n"
    "    (void)slimenrf_pwr_latch();",
    1)

open(path, "w", encoding="utf-8", newline="").write(src)
print(f"patch_mcuboot_pwr: EARLY + main() power latch inserted into {path}")
