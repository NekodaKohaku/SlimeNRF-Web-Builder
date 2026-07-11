#!/usr/bin/env python3
# TEMP TRAP: log every gpio_pin_configure() that reaches the nRF GPIO driver.
#
# Hardware evidence (PIN_CNF dump): ~100 ms after boot something turns the LED pin
# (P1.05) from a clean push-pull output (0x003) into an open-drain INPUT (0x800/0x802)
# and it stays that way -- OUT keeps toggling but never reaches the pad. The same thing
# almost certainly hits the power-latch pin (P1.09), which is why releasing the latch no
# longer powers the board off. No GPIO_OPEN_DRAIN exists anywhere in the firmware source
# and the DT flags do not carry it, so the caller is outside the app.
#
# Patch the driver itself: every pin_configure prints port/pin/flags. Whoever it is
# cannot hide.
import sys, os
f = "../zephyr/drivers/gpio/gpio_nrfx.c"
if not os.path.exists(f):
    print("patch_gpiotrap: %s not found" % f, file=sys.stderr); sys.exit(0)
s = open(f, encoding="utf-8").read()
if "[gtrap]" in s:
    print("patch_gpiotrap: already applied"); sys.exit(0)
anchor = "\tconst struct gpio_nrfx_cfg *cfg = get_port_cfg(port);\n"
i = s.find("static int gpio_nrfx_pin_configure")
if i < 0 or anchor not in s[i:]:
    print("patch_gpiotrap: anchor not found", file=sys.stderr); sys.exit(0)
j = s.index(anchor, i) + len(anchor)
inject = ('\tprintk("[gtrap] P%u.%02u flags=0x%08x\\n", (unsigned)cfg->port_num, (unsigned)pin, (unsigned)flags);\n')
s = s[:j] + inject + s[j:]
if "#include <zephyr/sys/printk.h>" not in s:
    s = s.replace("#include <zephyr/drivers/gpio.h>", "#include <zephyr/drivers/gpio.h>\n#include <zephyr/sys/printk.h>", 1)
open(f, "w", encoding="utf-8").write(s)
print("patch_gpiotrap: gpio_nrfx_pin_configure now logs every call")
sys.exit(0)
