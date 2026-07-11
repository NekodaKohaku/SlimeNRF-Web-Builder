#!/usr/bin/env python3
# When the LED is PWM-driven, led.c must not also configure the same pin as a GPIO.
#
# led_pin_init() (SYS_INIT, APPLICATION) does gpio_pin_configure_dt(&led, GPIO_OUTPUT)
# and led_pin_reset() does gpio_pin_configure_dt(&led, GPIO_DISCONNECTED) -- on the very
# pin that pinctrl has already handed to the PWM peripheral (PWM inits at POST_KERNEL,
# i.e. BEFORE APPLICATION). Two drivers configuring one pin.
#
# nRF52 survives this: the PWM keeps its own PSEL, so re-touching GPIO PIN_CNF doesn't
# unroute it. nRF54L does not: peripheral pin ownership lives in the GPIO PIN_CNF
# (CTRLSEL), so gpio_pin_configure() takes the pin back from the PWM and the LED goes
# dark from boot -- which is exactly the "nRF54L LED barely ever lights" symptom.
#
# Fix at the point that is actually wrong, with no chip ifdef: if PWM owns the LED,
# the GPIO helpers leave that pin alone. Harmless no-op removal on nRF52 (the PWM was
# driving the pin anyway); essential on nRF54L. Suspend power-down is still handled by
# the PWM device's PM action + the pwm*_sleep pinctrl state.
import sys
f = "src/system/led.c"
s = open(f, encoding="utf-8").read()
hunks = [
    ("static int led_pin_init(void)\n"
     "{\n"
     "\tLOG_DBG(\"led_pin_init\");\n"
     "#if LED_EXISTS\n"
     "\tgpio_pin_configure_dt(&led, GPIO_OUTPUT);\n"
     "\tgpio_pin_set_dt(&led, 0);\n"
     "#endif\n",
     "static int led_pin_init(void)\n"
     "{\n"
     "\tLOG_DBG(\"led_pin_init\");\n"
     "#if LED_EXISTS && !defined(PWM_LED_EXISTS)\n"
     "\tgpio_pin_configure_dt(&led, GPIO_OUTPUT);\n"
     "\tgpio_pin_set_dt(&led, 0);\n"
     "#endif\n"),
    ("static void led_pin_reset(void)\n"
     "{\n"
     "\tLOG_DBG(\"led_pin_reset\");\n"
     "#if LED_EXISTS\n"
     "\tgpio_pin_configure_dt(&led, GPIO_DISCONNECTED);\n"
     "#endif\n",
     "static void led_pin_reset(void)\n"
     "{\n"
     "\tLOG_DBG(\"led_pin_reset\");\n"
     "#if LED_EXISTS && !defined(PWM_LED_EXISTS)\n"
     "\tgpio_pin_configure_dt(&led, GPIO_DISCONNECTED);\n"
     "#endif\n"),
]
if "#if LED_EXISTS && !defined(PWM_LED_EXISTS)" in s:
    print("patch_ledpwm: already applied"); sys.exit(0)
n = 0
for old, new in hunks:
    if old in s:
        s = s.replace(old, new, 1); n += 1
    else:
        print("patch_ledpwm: WARNING hunk not matched", file=sys.stderr)
open(f, "w", encoding="utf-8").write(s)
print("patch_ledpwm: applied %d/2 (PWM-owned LED pin no longer reconfigured as GPIO)" % n)
sys.exit(0)
