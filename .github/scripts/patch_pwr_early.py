#!/usr/bin/env python3
# nRF52 only (wired from the workflow's non-nrf54l branch -- no chip ifdef in the C).
#
# The board's power latch works like this: pressing the button connects power, the MCU
# boots, and the MCU must then drive pwr-gpios high to hold power on by itself. Upstream
# asserts that latch at the top of main() -- but Zephyr's main() only runs after EVERY
# SYS_INIT level (GPIO, flash, sensors, console...) has finished. Let go of the button
# before that and the board drops power mid-boot. Press long enough to survive it and you
# instead trigger the pairing long-press. There is no good press duration.
#
# Latch the pin from a PRE_KERNEL_1 SYS_INIT at priority 0 -- the earliest code that runs
# at all -- using the raw nRF HAL. Raw HAL needs no driver to be initialised (so it can run
# this early) and, importantly, it does NOT go through the Zephyr GPIO driver: that driver
# ends its configure path with port_retain_set(), which on nRF54L latches the pin's
# registers and makes the power-off release (gpio_pin_set_dt(&pwr_hold, 0)) fail. This is
# exactly what test54l_board.c already does for the nRF54L, which is why the nRF54L does
# not need (and must not get) this patch.
#
# main()'s own gpio_pin_configure_dt() stays; on nRF52 there is no retention, so
# re-asserting the same pin through the driver later is harmless.
import sys

f = "src/main.c"
s = open(f, encoding="utf-8").read()
if "pwr_hold_early" in s:
    print("patch_pwr_early: already applied"); sys.exit(0)

anchor = "\nint main(void)\n{\n"
if anchor not in s:
    sys.exit("patch_pwr_early: main() anchor not found (run patch_pwr first)")

block = (
    "\n#include <zephyr/init.h>\n"
    "#include <hal/nrf_gpio.h>\n"
    "#if DT_NODE_HAS_PROP(PWR_HOLD_NODE, pwr_gpios)\n"
    "static int pwr_hold_early(void)\n"
    "{\n"
    "\tuint32_t psel = NRF_DT_GPIOS_TO_PSEL(PWR_HOLD_NODE, pwr_gpios);\n"
    "\tnrf_gpio_cfg(psel, NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT,\n"
    "\t             NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_S0S1, NRF_GPIO_PIN_NOSENSE);\n"
    "#if (DT_GPIO_FLAGS(PWR_HOLD_NODE, pwr_gpios) & GPIO_ACTIVE_LOW)\n"
    "\tnrf_gpio_pin_clear(psel);\n"
    "#else\n"
    "\tnrf_gpio_pin_set(psel);\n"
    "#endif\n"
    "\treturn 0;\n"
    "}\n"
    "SYS_INIT(pwr_hold_early, PRE_KERNEL_1, 0);\n"
    "#endif\n"
    + anchor
)
open(f, "w", encoding="utf-8").write(s.replace(anchor, block, 1))
print("patch_pwr_early: power latch asserted at PRE_KERNEL_1/0 via raw HAL (nRF52 only)")
sys.exit(0)
