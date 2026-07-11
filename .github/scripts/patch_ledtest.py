#!/usr/bin/env python3
# TEMP DIAGNOSTIC ONLY -- pins the LED GPIO permanently HIGH and stops anything else
# from touching it. The LED loses all indicator function; this build exists purely to
# answer one question with a multimeter:
#
#   Can P1.05 be driven high at all, and does it STAY high?
#
#   -> steady bright LED / ~3.3 V at the pin : the pin and the GPIO path are fine, and
#      the bug lives in led.c's flow (patterns / suspend / retention interaction).
#   -> dim, blinking or ~0 V                 : the pin cannot hold its drive, so the bug
#      is below led.c (GPIO retention, the driver, or hardware).
import sys
f = "src/system/led.c"
s = open(f, encoding="utf-8").read()
n = 0

# 1) init: drive the pin HIGH and leave it there
old = "\tgpio_pin_configure_dt(&led, GPIO_OUTPUT);\n\tgpio_pin_set_dt(&led, 0);\n"
new = "\tgpio_pin_configure_dt(&led, GPIO_OUTPUT_ACTIVE); /* LEDTEST: pin held HIGH */\n"
if old in s: s = s.replace(old, new, 1); n += 1

# 2) led_pin_set: do nothing at all
old = ('\tLOG_DBG("led_pin_set: color %d, brightness %d, value %d", color, brightness_pptt, value_pptt);\n')
new = ('\tLOG_DBG("led_pin_set: color %d, brightness %d, value %d", color, brightness_pptt, value_pptt);\n'
       '\treturn; /* LEDTEST: never touch the pin again */\n')
if old in s: s = s.replace(old, new, 1); n += 1

# 3) led_pin_reset: do nothing (so suspend cannot disconnect the pin)
old = 'static void led_pin_reset(void)\n{\n\tLOG_DBG("led_pin_reset");\n'
new = 'static void led_pin_reset(void)\n{\n\tLOG_DBG("led_pin_reset");\n\treturn; /* LEDTEST */\n'
if old in s: s = s.replace(old, new, 1); n += 1

open(f, "w", encoding="utf-8").write(s)
print("patch_ledtest: applied %d/3 -- LED pin pinned HIGH, nothing else touches it" % n)
sys.exit(0)
