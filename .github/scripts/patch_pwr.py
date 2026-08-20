#!/usr/bin/env python3
# Power-hold latch: assert pwr-gpios at the top of main(), release it on system off.
# (Upstream has no pwr-gpios concept; this is the external power latch our modules use.)
import sys

MAIN = "src/main.c"
POWER = "src/system/power.c"

main_spec = (
    "#include <zephyr/drivers/gpio.h>\n"
    "#define PWR_HOLD_NODE DT_PATH(zephyr_user)\n"
    "#if DT_NODE_HAS_PROP(PWR_HOLD_NODE, pwr_gpios)\n"
    "static const struct gpio_dt_spec pwr_hold = GPIO_DT_SPEC_GET(PWR_HOLD_NODE, pwr_gpios);\n"
    "#endif\n\n"
    "int main(void)\n{\n"
    "#if DT_NODE_HAS_PROP(PWR_HOLD_NODE, pwr_gpios)\n"
    "\tgpio_pin_configure_dt(&pwr_hold, GPIO_OUTPUT_ACTIVE);\n"
    "#endif\n"
)

s = open(MAIN).read()
if "pwr_hold" in s:
    print("pwr patch: already applied")
    sys.exit(0)
if "int main(void)\n{\n" not in s:
    sys.exit("pwr patch failed: main() anchor not found in main.c")
s = s.replace("int main(void)\n{\n", main_spec, 1)
open(MAIN, "w").write(s)

p = open(POWER).read()
anchor = "#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)\n"
if anchor not in p:
    sys.exit("pwr patch failed: ZEPHYR_USER_NODE anchor not found in power.c")
p = p.replace(
    anchor,
    anchor
    + "#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, pwr_gpios)\n"
    "static const struct gpio_dt_spec pwr_hold = GPIO_DT_SPEC_GET(ZEPHYR_USER_NODE, pwr_gpios);\n"
    "#endif\n",
    1,
)
# Release the latch LAST, immediately before sys_poweroff().
#
# It used to be released on the first line of sys_system_off(), which cuts the
# board's power while the rest of the shutdown is still running: the battery
# tracker is written to NVS after that point, and the non-silent path then busy
# waits ~650 ms for the power-off LED pattern to finish. Everything after the
# release races a collapsing rail, and an NVS write caught by a brownout is how
# stored data gets corrupted. Boards survive it on bulk capacitance, which is
# exactly the kind of thing that works until a cell ages.
#
# Doing it last also orders correctly against the sensor supply, which
# patch_sysoff.py releases inside sys_disconnect_interface_pins(): sensor first,
# then system power. And if the latch is bypassed - held button, big EN
# capacitor, or a board where it only gates part of the rail - sys_poweroff()
# still puts the SoC in System OFF straight after.
off_anchor = (
    "\telse\n\t{\n\t\twait_for_logging();\n\t}\n"
    "#if ADAFRUIT_BOOTLOADER // if using Adafruit bootloader, always skip dfu for next boot\n"
    "\t(*dbl_reset_mem) = DFU_DBL_RESET_APP; // Skip DFU\n"
    "#endif\n"
    "\tsys_poweroff();\n"
)
if p.count(off_anchor) != 1:
    sys.exit("pwr patch failed: sys_system_off tail anchor not unique in power.c")
p = p.replace(
    off_anchor,
    off_anchor.replace(
        "\tsys_poweroff();\n",
        "#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, pwr_gpios)\n"
        "\t/* Latch released last: everything above still needs a stable rail. */\n"
        "\tgpio_pin_set_dt(&pwr_hold, 0);\n"
        "#endif\n"
        "\tsys_poweroff();\n",
    ),
    1,
)
open(POWER, "w").write(p)

print("power-hold source patch applied (latch in main(), release on system off)")
