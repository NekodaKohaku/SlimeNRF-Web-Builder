#!/usr/bin/env python3
# 公式レシーバー (dongle) にボタン操作を追加する。
#
# 公式のレシーバーは console コマンド (pair / exit / clear / dfu) しか持たず、
# ボタン処理が一切ない。ケースに入れた完成品や、PC のターミナルを開かずに
# ペアリングしたい場面では不便なので、jiting レシーバーと同じ操作体系を
# 公式側にも実装する。
#
# 操作 (DT に sw0 alias があるときだけ有効):
#   3 回押し    ペアリングモードに入る      esb_reset_pair()
#   2 回押し    ペアリングモードを抜ける    esb_finish_pair()
#   長押し 5s   ペアリング全消去 (離した時) esb_clear()
#   長押し 10s  DFU に入る                  GPREGRET + reboot
#   1 回押し    何もしない (誤操作対策。jiting は全トラッカー shutdown だが
#               公式にはリモートコマンド機構が無いため実装しない)
#
# 長押し中は LED が 1 秒ごとに点滅して経過を知らせる。
# 起動時にボタンが押されたままでも誤爆しないよう、一度離すまで長押しは
# 成立しない (電源ボタン兼用の基板を想定)。
#
# 実行場所: zephyr-workspace/SlimeVR-Tracker-nRF-Receiver
import sys

MARK = "SLIMENRF_RECV_BUTTON"
f = "src/system/system.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_recv_button: already applied"); sys.exit(0)

BLOCK = r"""
/* ==== SLIMENRF_RECV_BUTTON (SlimeNRF-Web-Builder) ====
 * Button support for the official receiver (upstream has none).
 * Enabled only when the devicetree provides an sw0 alias.
 */
#if DT_NODE_HAS_PROP(DT_ALIAS(sw0), gpios)

#include <zephyr/kernel.h>
#include "connection/esb.h"

#define RECV_BTN_DEBOUNCE_MS   50
#define RECV_BTN_SEQ_GAP_MS    1000   /* end of a multi-press sequence */
#define RECV_BTN_CLEAR_MS      5000   /* hold: clear all pairings */
#define RECV_BTN_DFU_MS        10000  /* hold: enter DFU */

#define RECV_DFU_EXISTS (CONFIG_BUILD_OUTPUT_UF2 || CONFIG_BOARD_HAS_NRF5_BOOTLOADER)
#define RECV_ADAFRUIT_DFU_MAGIC 0x57

static const struct gpio_dt_spec recv_button0 = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static int64_t recv_press_time;
static int64_t recv_last_press_duration;

static void recv_button_isr(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);

	bool pressed = gpio_pin_get_dt(&recv_button0) > 0;
	int64_t now = k_uptime_get();

	if (recv_press_time && !pressed && now - recv_press_time > RECV_BTN_DEBOUNCE_MS) {
		recv_last_press_duration = now - recv_press_time;
	} else if (recv_press_time && pressed) {
		return; /* spurious edge while already pressed */
	}
	recv_press_time = pressed ? now : 0;
}

static struct gpio_callback recv_button_cb;

static int recv_button_init(void)
{
	if (!gpio_is_ready_dt(&recv_button0)) {
		return 0;
	}
	gpio_pin_configure_dt(&recv_button0, GPIO_INPUT);
	gpio_pin_interrupt_configure_dt(&recv_button0, GPIO_INT_EDGE_BOTH);
	gpio_init_callback(&recv_button_cb, recv_button_isr, BIT(recv_button0.pin));
	gpio_add_callback(recv_button0.port, &recv_button_cb);
	return 0;
}
SYS_INIT(recv_button_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);

static void recv_enter_dfu(void)
{
#if CONFIG_BUILD_OUTPUT_UF2
	NRF_POWER->GPREGRET = RECV_ADAFRUIT_DFU_MAGIC;
	k_msleep(100);
	sys_reboot(SYS_REBOOT_COLD);
#elif CONFIG_BOARD_HAS_NRF5_BOOTLOADER
	const struct device *gpio_dev = DEVICE_DT_GET(DT_NODELABEL(gpio0));
	if (device_is_ready(gpio_dev)) {
		gpio_pin_configure(gpio_dev, 19, GPIO_OUTPUT | GPIO_OUTPUT_INIT_LOW);
		k_msleep(100);
	}
	sys_reboot(SYS_REBOOT_COLD);
#endif
}

static void recv_button_thread(void)
{
	int num_presses = 0;
	int64_t seq_last_press = 0;
	int64_t hold_start = 0;
	int64_t last_blink = 0;
	bool led_on = false;
	bool dfu_done = false;
	bool seen_release = false;   /* ignore a button already held at boot */

	while (1) {
		bool pressed = gpio_pin_get_dt(&recv_button0) > 0;

		if (!pressed) {
			seen_release = true;
		}

		/* --- press start --- */
		if (recv_press_time && !hold_start && seen_release) {
			hold_start = recv_press_time;
			dfu_done = false;
			set_led(SYS_LED_PATTERN_ON, SYS_LED_PRIORITY_HIGHEST);
			last_blink = k_uptime_get();
			led_on = true;
		}

		/* --- being held: blink once per second, act at thresholds --- */
		if (hold_start && pressed) {
			int64_t now = k_uptime_get();
			int64_t held = now - hold_start;

			if (now - last_blink >= 1000) {
				led_on = !led_on;
				set_led(led_on ? SYS_LED_PATTERN_ON : SYS_LED_PATTERN_OFF,
					SYS_LED_PRIORITY_HIGHEST);
				last_blink = now;
			}
#if RECV_DFU_EXISTS
			if (held >= RECV_BTN_DFU_MS && !dfu_done) {
				printk("Button: entering DFU\n");
				set_led(SYS_LED_PATTERN_ERROR_D, SYS_LED_PRIORITY_HIGHEST);
				dfu_done = true;
				recv_enter_dfu();
				return;
			}
#endif
		}

		/* --- release --- */
		if (recv_last_press_duration > RECV_BTN_DEBOUNCE_MS && hold_start) {
			int64_t dur = recv_last_press_duration;
			recv_last_press_duration = 0;
			hold_start = 0;
			set_led(SYS_LED_PATTERN_OFF, SYS_LED_PRIORITY_HIGHEST);

			if (dur >= RECV_BTN_CLEAR_MS && dur < RECV_BTN_DFU_MS) {
				printk("Button: clearing all pairings\n");
				esb_clear();
				set_led(SYS_LED_PATTERN_ONESHOT_COMPLETE, SYS_LED_PRIORITY_HIGHEST);
				num_presses = 0;
				seq_last_press = 0;
			} else if (dur < RECV_BTN_CLEAR_MS) {
				num_presses++;
				seq_last_press = k_uptime_get();
			} else {
				num_presses = 0;
				seq_last_press = 0;
			}
		}

		/* --- multi-press sequence finished --- */
		if (seq_last_press && k_uptime_get() - seq_last_press > RECV_BTN_SEQ_GAP_MS
		    && num_presses > 0) {
			switch (num_presses) {
			case 2:
				printk("Button: exit pairing mode\n");
				esb_finish_pair();
				set_led(SYS_LED_PATTERN_ONESHOT_PROGRESS, SYS_LED_PRIORITY_HIGHEST);
				break;
			case 3:
				printk("Button: enter pairing mode\n");
				esb_reset_pair();
				break;
			default:
				/* 1 press (and 4+) intentionally do nothing */
				break;
			}
			num_presses = 0;
			seq_last_press = 0;
		}

		k_msleep(50);
	}
}
K_THREAD_DEFINE(recv_button_thread_id, 1024, recv_button_thread, NULL, NULL, NULL, 6, 0, 0);

#endif /* sw0 alias exists */
"""

# システムファイルの末尾に追加 (既存コードには一切触れない)
s = s.rstrip() + NL + NL + BLOCK.replace("\n", NL).lstrip() + NL
open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_recv_button: system.c OK (button thread appended)")
