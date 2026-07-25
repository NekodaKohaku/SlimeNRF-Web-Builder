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
#include <hal/nrf_spim.h>

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
	printk("P1 OUT=0x%08X IN=0x%08X DIR=0x%08X\n",
	       (unsigned int)NRF_P1->OUT, (unsigned int)NRF_P1->IN,
	       (unsigned int)NRF_P1->DIR);
	/* raw GPIO wiggle test: CS (P1.05) toggle, read back via IN */
	nrf_gpio_cfg_output(NRF_GPIO_PIN_MAP(1, 5));
	nrf_gpio_pin_set(NRF_GPIO_PIN_MAP(1, 5));
	uint32_t in_hi = NRF_P1->IN;
	nrf_gpio_pin_clear(NRF_GPIO_PIN_MAP(1, 5));
	uint32_t in_lo = NRF_P1->IN;
	nrf_gpio_pin_set(NRF_GPIO_PIN_MAP(1, 5));
	printk("CS wiggle: IN(hi)=0x%08X IN(lo)=0x%08X (bit5 should change)\n",
	       (unsigned int)in_hi, (unsigned int)in_lo);
#if defined(NRF_GPIO_HAS_RETENTION_SETCLEAR) && NRF_GPIO_HAS_RETENTION_SETCLEAR
	/* SET/CLR style: reading RETAINSET returns the current retain mask */
	printk("P1 RETAIN=0x%08X\n", (unsigned int)NRF_P1->RETAINSET);
#endif
	/* clear retain on SPI pins just in case (chainload may leave pads latched) */
#if defined(NRF_GPIO_HAS_RETENTION_SETCLEAR) && NRF_GPIO_HAS_RETENTION_SETCLEAR
	for (int p = 2; p <= 6; p++) {
		nrf_gpio_pin_retain_disable(NRF_GPIO_PIN_MAP(1, p));
	}
	printk("P1.02-06 retain cleared; P1 RETAIN now=0x%08X\n",
	       (unsigned int)NRF_P1->RETAINSET);
#endif
	/* bit-bang SPI mode0: read LSM6DSV WHO_AM_I (0x0F). expect 0x70 */
	{
		const uint32_t cs = NRF_GPIO_PIN_MAP(1, 5), sck = NRF_GPIO_PIN_MAP(1, 4);
		const uint32_t mosi = NRF_GPIO_PIN_MAP(1, 3), miso = NRF_GPIO_PIN_MAP(1, 2);
		nrf_gpio_cfg_output(cs); nrf_gpio_pin_set(cs);
		nrf_gpio_cfg_output(sck); nrf_gpio_pin_clear(sck);
		nrf_gpio_cfg_output(mosi);
		nrf_gpio_cfg_input(miso, NRF_GPIO_PIN_NOPULL);
		k_busy_wait(10);
		nrf_gpio_pin_clear(cs);
		k_busy_wait(5);
		uint8_t tx = 0x8F, rx = 0;
		for (int b = 7; b >= 0; b--) {
			(tx & (1 << b)) ? nrf_gpio_pin_set(mosi) : nrf_gpio_pin_clear(mosi);
			k_busy_wait(2);
			nrf_gpio_pin_set(sck); k_busy_wait(2);
			nrf_gpio_pin_clear(sck);
		}
		for (int b = 7; b >= 0; b--) {
			nrf_gpio_pin_set(sck); k_busy_wait(2);
			rx |= (uint8_t)(nrf_gpio_pin_read(miso) << b);
			nrf_gpio_pin_clear(sck); k_busy_wait(2);
		}
		nrf_gpio_pin_set(cs);
		printk("BITBANG WHO_AM_I=0x%02X (expect 0x70)\n", rx);
	}
	/* raw-register SPIM20 transaction (bypass zephyr driver):
	 * restore pinctrl-style pad config, then WHO_AM_I via EasyDMA */
#if defined(NRF_SPIM20)
	{
		static uint8_t txb[3] = {0x8F, 0x00, 0x00};
		static uint8_t rxb[3];
		const uint32_t cs = NRF_GPIO_PIN_MAP(1, 5);
		/* pads back to SPIM-style config (as pinctrl leaves them) */
		nrf_gpio_cfg(NRF_GPIO_PIN_MAP(1, 4), NRF_GPIO_PIN_DIR_OUTPUT,
			     NRF_GPIO_PIN_INPUT_CONNECT, NRF_GPIO_PIN_NOPULL,
			     NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE); /* SCK */
		nrf_gpio_cfg(NRF_GPIO_PIN_MAP(1, 3), NRF_GPIO_PIN_DIR_OUTPUT,
			     NRF_GPIO_PIN_INPUT_DISCONNECT, NRF_GPIO_PIN_NOPULL,
			     NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE); /* MOSI */
		nrf_gpio_cfg(NRF_GPIO_PIN_MAP(1, 2), NRF_GPIO_PIN_DIR_INPUT,
			     NRF_GPIO_PIN_INPUT_CONNECT, NRF_GPIO_PIN_NOPULL,
			     NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE); /* MISO */
		nrf_spim_pins_set(NRF_SPIM20, NRF_GPIO_PIN_MAP(1, 4),
				  NRF_GPIO_PIN_MAP(1, 3), NRF_GPIO_PIN_MAP(1, 2));
		nrf_spim_configure(NRF_SPIM20, NRF_SPIM_MODE_0,
				   NRF_SPIM_BIT_ORDER_MSB_FIRST);
#if defined(NRF_SPIM_HAS_PRESCALER) && NRF_SPIM_HAS_PRESCALER
		nrf_spim_prescaler_set(NRF_SPIM20, 16); /* slow + safe */
#else
		nrf_spim_frequency_set(NRF_SPIM20, NRF_SPIM_FREQ_1M);
#endif
		nrf_spim_tx_buffer_set(NRF_SPIM20, txb, 3);
		nrf_spim_rx_buffer_set(NRF_SPIM20, rxb, 3);
		nrf_spim_event_clear(NRF_SPIM20, NRF_SPIM_EVENT_END);
		nrf_spim_enable(NRF_SPIM20);
		nrf_gpio_pin_clear(cs);
		k_busy_wait(5);
		nrf_spim_task_trigger(NRF_SPIM20, NRF_SPIM_TASK_START);
		int tmo = 10000;
		while (!nrf_spim_event_check(NRF_SPIM20, NRF_SPIM_EVENT_END) && --tmo) {
			k_busy_wait(1);
		}
		nrf_gpio_pin_set(cs);
		printk("RAW SPIM20: END=%d tmo_left=%d RX=%02X %02X %02X (WHO expect [1]=0x70)\n",
		       (int)nrf_spim_event_check(NRF_SPIM20, NRF_SPIM_EVENT_END), tmo,
		       rxb[0], rxb[1], rxb[2]);
		nrf_spim_disable(NRF_SPIM20);
	}
#endif
	return 0;
}
SYS_INIT(zz_diag54l, APPLICATION, 90);

/* second dump AFTER sensor scan window (~5s) */
static void zz_diag54l_late(struct k_work *w)
{
	ARG_UNUSED(w);
	printk("=== DIAG54L late dump ===\n");
	printk("P1 OUT=0x%08X IN=0x%08X DIR=0x%08X\n",
	       (unsigned int)NRF_P1->OUT, (unsigned int)NRF_P1->IN,
	       (unsigned int)NRF_P1->DIR);
#if defined(NRF_SPIM20)
	printk("SPIM20 ENABLE=%u\n", (unsigned int)NRF_SPIM20->ENABLE);
#endif
}
static K_WORK_DELAYABLE_DEFINE(zz_diag_work, zz_diag54l_late);
static int zz_diag54l_sched(void)
{
	k_work_schedule(&zz_diag_work, K_SECONDS(5));
	return 0;
}
SYS_INIT(zz_diag54l_sched, APPLICATION, 99);
#endif
''')
print("patch_jiting_diag54l: created src/system/zz_diag54l.c (TEMP)")
