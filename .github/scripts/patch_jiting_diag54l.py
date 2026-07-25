#!/usr/bin/env python3
# 一時診断 (TEMP): 54L で SPI IMU が mcuboot ビルドのみ死ぬ問題の現場検証。
# src/system/zz_diag54l.c を生成 (CMake が src/*.c を GLOB するので自動でコンパイル)。
# 起動時に P1.01-P1.06 の PIN_CNF (CTRLSEL 含む) と SPIM20 の PSEL/ENABLE を printk。
# 期待値: PSEL SCK=0x24 MOSI=0x23 MISO=0x22 (port1<<5|pin, bit31=0=connected)
import os, sys

f = "src/system/zz_diag54l.c"
if os.path.exists(f):
    print("patch_jiting_diag54l: already present"); sys.exit(0)

open(f, "w", newline="\n").write(r'''/* SLIMENRF TEMP DIAG: dump pad/SPIM state at boot (remove after debugging) */
#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/sys/printk.h>
#include <hal/nrf_gpio.h>

#if defined(CONFIG_SOC_SERIES_NRF54LX)
static int zz_diag54l(void)
{
	printk("=== DIAG54L pad/SPIM dump ===\n");
	for (int pin = 1; pin <= 6; pin++) {
		printk("P1.%02d PIN_CNF=0x%08X\n", pin,
		       (unsigned int)NRF_P1->PIN_CNF[pin]);
	}
#if defined(NRF_SPIM20)
	printk("SPIM20 ENABLE=%u PSEL SCK=0x%08X MOSI=0x%08X MISO=0x%08X\n",
	       (unsigned int)NRF_SPIM20->ENABLE,
	       (unsigned int)NRF_SPIM20->PSEL.SCK,
	       (unsigned int)NRF_SPIM20->PSEL.MOSI,
	       (unsigned int)NRF_SPIM20->PSEL.MISO);
#else
	printk("SPIM20 symbol not defined\n");
#endif
	return 0;
}
SYS_INIT(zz_diag54l, APPLICATION, 90);
#endif
''')
print("patch_jiting_diag54l: created src/system/zz_diag54l.c (TEMP)")
