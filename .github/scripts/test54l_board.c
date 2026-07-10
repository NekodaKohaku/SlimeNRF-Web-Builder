/*
 * SPDX-License-Identifier: Apache-2.0
 * SlimeNRF-Web-Builder: early power-hold latch (PRE_KERNEL_1) + sensor power via DT.
 * Replaces upstream test54l board.c (which hardcoded P1.7/P1.8 and no pwr-hold).
 */
#include <zephyr/init.h>
#include <zephyr/devicetree.h>
#include <zephyr/dt-bindings/gpio/gpio.h>
#include <hal/nrf_gpio.h>
#include <nrf.h>

#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)

#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, pwr_gpios)
	#define PWR_GPIO_PIN DT_GPIO_PIN(ZEPHYR_USER_NODE, pwr_gpios)
	#define PWR_GPIO_PORT_NUM DT_PROP(DT_GPIO_CTLR(ZEPHYR_USER_NODE, pwr_gpios), port)
	#define PWR_GPIO_FLAGS DT_GPIO_FLAGS(ZEPHYR_USER_NODE, pwr_gpios)
#endif
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, vcc_gpios)
	#define VCC_GPIO_PIN DT_GPIO_PIN(ZEPHYR_USER_NODE, vcc_gpios)
	#define VCC_GPIO_PORT_NUM DT_PROP(DT_GPIO_CTLR(ZEPHYR_USER_NODE, vcc_gpios), port)
#endif
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, gnd_gpios)
	#define GND_GPIO_PIN DT_GPIO_PIN(ZEPHYR_USER_NODE, gnd_gpios)
	#define GND_GPIO_PORT_NUM DT_PROP(DT_GPIO_CTLR(ZEPHYR_USER_NODE, gnd_gpios), port)
#endif

static int board_test54l_init(void)
{
	/* P1.02 (NFC1) / P1.03 (NFC2) default to NFC mode on nRF54L15 and cannot be
	 * used as GPIO/SPIM until NFC is disabled. Free them here, before SPIM init. */
#if defined(NRF_NFCT)
	NRF_NFCT->PADCONFIG = 0;
#endif

	/* Hold the external power latch as early as possible. */
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, pwr_gpios)
	nrf_gpio_cfg(NRF_GPIO_PIN_MAP(PWR_GPIO_PORT_NUM, PWR_GPIO_PIN), NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT, NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE);
	#if (PWR_GPIO_FLAGS & GPIO_ACTIVE_LOW)
	nrf_gpio_pin_clear(NRF_GPIO_PIN_MAP(PWR_GPIO_PORT_NUM, PWR_GPIO_PIN));
	#else
	nrf_gpio_pin_set(NRF_GPIO_PIN_MAP(PWR_GPIO_PORT_NUM, PWR_GPIO_PIN));
	#endif
#endif

	/* Sensor power via DT vcc-gpios / gnd-gpios (was hardcoded P1.7/P1.8). */
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, vcc_gpios)
	nrf_gpio_cfg(NRF_GPIO_PIN_MAP(VCC_GPIO_PORT_NUM, VCC_GPIO_PIN), NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT, NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_D0H1, NRF_GPIO_PIN_NOSENSE);
	nrf_gpio_pin_set(NRF_GPIO_PIN_MAP(VCC_GPIO_PORT_NUM, VCC_GPIO_PIN));
#endif
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, gnd_gpios)
	nrf_gpio_cfg(NRF_GPIO_PIN_MAP(GND_GPIO_PORT_NUM, GND_GPIO_PIN), NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT, NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_H0D1, NRF_GPIO_PIN_NOSENSE);
	nrf_gpio_pin_clear(NRF_GPIO_PIN_MAP(GND_GPIO_PORT_NUM, GND_GPIO_PIN));
#endif
	return 0;
}

SYS_INIT(board_test54l_init, PRE_KERNEL_1, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT);
