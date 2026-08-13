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
off_anchor = 'LOG_INF("System off requested");\n'
if off_anchor not in p:
    sys.exit("pwr patch failed: system off anchor not found in power.c")
p = p.replace(
    off_anchor,
    off_anchor
    + "#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, pwr_gpios)\n"
    "\tgpio_pin_set_dt(&pwr_hold, 0);\n"
    "#endif\n",
    1,
)
open(POWER, "w").write(p)

print("power-hold source patch applied (latch in main(), release on system off)")
