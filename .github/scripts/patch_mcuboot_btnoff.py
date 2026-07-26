#!/usr/bin/env python3
# serial recovery 中の「長押し 1 秒で電源オフ」。
#
# 背景: DFU (serial recovery) 中に動いているのは mcuboot であり、アプリの
# ボタン処理は存在しない。さらに patch_mcuboot_pwr.py の電源自锁で電源は
# 保持され続けるため、DFU に入ったあと抜ける手段が「電池を外す」しかない。
# 筐体に封入した完成品ではこれは実質デッドロック。
#
# 対処: boot_serial の受信ループ (MCUBOOT_WATCHDOG_FEED() が毎周回呼ばれる
# 場所) にボタンのポーリングを差し込み、1 秒以上押しっぱなしなら pwr-gpios を
# 非アクティブに落として電源を切る。アプリ側の「長押し 1 秒でシャットダウン」
# と同じ操作感になる。
#
# 安全性: overwrite-only 構成では転送先 slot1 が壊れてもアプリ (slot0) は
# 無傷なので、更新途中で電源を切っても文鎮化しない (次回また DFU すればよい)。
#
# DT: zephyr,user の btn-gpios (gen_mcuboot_files.py が出力) と pwr-gpios。
# どちらか無ければ何もしない空実装になる。
#
# 実行場所: zephyr-workspace/SlimeVR-Tracker-nRF (patch_mcuboot_pwr.py の後)
import os, sys

MARK = "SLIMENRF_BTN_OFF"

MAIN_CANDIDATES = (
    "../bootloader/mcuboot/boot/zephyr/main.c",
    "../modules/mcuboot/boot/zephyr/main.c",
)
BS_CANDIDATES = (
    "../bootloader/mcuboot/boot/boot_serial/src/boot_serial.c",
    "../modules/mcuboot/boot/boot_serial/src/boot_serial.c",
)

def pick(cands, what):
    p = next((c for c in cands if os.path.isfile(c)), None)
    if not p:
        sys.exit(f"patch_mcuboot_btnoff: {what} not found: " + ", ".join(cands))
    return p

main_c = sys.argv[1] if len(sys.argv) > 1 else pick(MAIN_CANDIDATES, "mcuboot main.c")
bs_c = sys.argv[2] if len(sys.argv) > 2 else pick(BS_CANDIDATES, "boot_serial.c")

# ---------------- 1) main.c: ポーリング関数の実装 ----------------
src = open(main_c, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in src else "\n"
if MARK in src:
    print(f"patch_mcuboot_btnoff: already applied ({main_c})")
    sys.exit(0)

BLOCK = r"""
/* ==== SLIMENRF_BTN_OFF (SlimeNRF-Web-Builder) ====
 * serial recovery 中の長押しシャットダウン。boot_serial の受信ループから
 * 毎周回呼ばれる。raw HAL のみ (ドライバ・割り込み・スレッド非依存)。
 * btn-gpios / pwr-gpios が無ければ何もしない。
 */
#define SLIMENRF_BTN_NODE DT_PATH(zephyr_user)
#if DT_NODE_HAS_PROP(SLIMENRF_BTN_NODE, btn_gpios) && \
    DT_NODE_HAS_PROP(SLIMENRF_BTN_NODE, pwr_gpios)

#define SLIMENRF_BTN_HOLD_MS 1000

void slimenrf_poll_power_button(void)
{
	static int64_t press_start;
	static bool armed;
	static bool seen_release;   /* 起動時の押しっぱなしを無視するため */

	uint32_t btn = NRF_GPIO_PIN_MAP(
		DT_PROP(DT_GPIO_CTLR(SLIMENRF_BTN_NODE, btn_gpios), port),
		DT_GPIO_PIN(SLIMENRF_BTN_NODE, btn_gpios));

	if (!armed) {
		/* 入力設定は一度だけ。プルは DT のフラグに従う。 */
		nrf_gpio_pin_pull_t pull = NRF_GPIO_PIN_NOPULL;
#if (DT_GPIO_FLAGS(SLIMENRF_BTN_NODE, btn_gpios) & GPIO_PULL_UP)
		pull = NRF_GPIO_PIN_PULLUP;
#elif (DT_GPIO_FLAGS(SLIMENRF_BTN_NODE, btn_gpios) & GPIO_PULL_DOWN)
		pull = NRF_GPIO_PIN_PULLDOWN;
#endif
		nrf_gpio_cfg_input(btn, pull);
		armed = true;
		return; /* 設定直後の読みは安定しないので次周回から */
	}

	bool level = nrf_gpio_pin_read(btn) != 0;
#if (DT_GPIO_FLAGS(SLIMENRF_BTN_NODE, btn_gpios) & GPIO_ACTIVE_LOW)
	bool pressed = !level;
#else
	bool pressed = level;
#endif

	if (!pressed) {
		press_start = 0;
		seen_release = true;   /* ここから先の長押しだけを受け付ける */
		return;
	}
	if (!seen_release) {
		/* 電源ボタンで起動した直後はボタンが押されたままなので、
		 * それを長押しと誤判定して即シャットダウンしない。
		 * (app 側もエッジ割り込みなので同じ挙動になる)
		 * 一度離してから押し直せばシャットダウンできる。 */
		return;
	}
	if (press_start == 0) {
		press_start = k_uptime_get();
		return;
	}
	if (k_uptime_get() - press_start < SLIMENRF_BTN_HOLD_MS) {
		return;
	}

	/* 長押し成立: 電源自锁を解除して落とす */
	uint32_t pwr = NRF_GPIO_PIN_MAP(
		DT_PROP(DT_GPIO_CTLR(SLIMENRF_BTN_NODE, pwr_gpios), port),
		DT_GPIO_PIN(SLIMENRF_BTN_NODE, pwr_gpios));

	nrf_gpio_cfg(pwr, NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT,
		     NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE);
#if (DT_GPIO_FLAGS(SLIMENRF_BTN_NODE, pwr_gpios) & GPIO_ACTIVE_LOW)
	nrf_gpio_pin_set(pwr);
#else
	nrf_gpio_pin_clear(pwr);
#endif

	/* ラッチが切れれば電源は落ちる。外部給電中など落ちない環境では
	 * ここで止めておく (誤って DFU を続行しない)。 */
	while (1) {
		k_cpu_idle();
	}
}
#else
void slimenrf_poll_power_button(void) { }
#endif
"""

ANCHOR_MAIN = NL + "int main(void)" + NL
if ANCHOR_MAIN not in src:
    sys.exit(f"patch_mcuboot_btnoff: anchor 'int main(void)' not found in {main_c}")
src = src.replace(ANCHOR_MAIN, NL + BLOCK.replace("\n", NL) + NL + "int main(void)" + NL, 1)
open(main_c, "w", encoding="utf-8", newline="").write(src)
print(f"patch_mcuboot_btnoff: poll function inserted into {main_c}")

# ---------------- 2) boot_serial.c: 受信ループから呼ぶ ----------------
bs = open(bs_c, encoding="utf-8", newline="").read()
NL2 = "\r\n" if "\r\n" in bs else "\n"
if MARK in bs:
    print(f"patch_mcuboot_btnoff: already applied ({bs_c})")
    sys.exit(0)

OLD = "        MCUBOOT_WATCHDOG_FEED();".replace("\n", NL2)
if OLD not in bs:
    sys.exit(f"patch_mcuboot_btnoff: watchdog-feed anchor not found in {bs_c}")
NEW = (OLD + NL2 +
       "        /* " + MARK + ": long-press power-off while in serial recovery */" + NL2 +
       "        {" + NL2 +
       "            extern void slimenrf_poll_power_button(void);" + NL2 +
       "            slimenrf_poll_power_button();" + NL2 +
       "        }")
bs = bs.replace(OLD, NEW, 1)
open(bs_c, "w", encoding="utf-8", newline="").write(bs)
print(f"patch_mcuboot_btnoff: poll call inserted into {bs_c}")
