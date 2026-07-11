#!/usr/bin/env python3
# nRF54L LED fix. Two hunks, both minimal, both at the actual point of failure.
#
# ROOT CAUSE -- nRF54L GPIO retention.
# nRF54L has a per-pin "retain" latch that FREEZES that pin's GPIO registers, PIN_CNF
# included. Zephyr's gpio_nrfx driver enables it after configuring a pin (port_retain_set)
# and gpio_pin_set_dt()'s port_set_bits_raw() only clears it around the OUT write -- it
# never touches PIN_CNF. So once the direction ends up latched as INPUT, the pin can never
# be driven again no matter how often OUT is written. Measured on hardware: PIN_CNF stuck
# at 0x802 (DIR=0) while OUT kept toggling 1/0 exactly as commanded, and the LED stayed
# dark after a single flash at boot. nRF52 has no retention at all, which is why the very
# same code works there.
#
# FIX: release the latch right after the LED pin is configured, so the pad keeps following
# PIN_CNF. Guarded by the HAL capability flag, so it compiles to nothing on chips without
# retention -- no chip ifdef needed, and gpio_pin_set_dt() (the light upstream path that
# does not churn GPIOTE) keeps working as-is.
#
# The second hunk is unrelated to retention: when the LED is PWM-driven, led.c must not
# also configure that same pin as a GPIO (led_pin_init/led_pin_reset), because on nRF54L
# peripheral pin ownership lives in PIN_CNF.CTRLSEL and the GPIO configure takes the pad
# back from the PWM.
import sys
f = "src/system/led.c"
s = open(f, encoding="utf-8").read()
if "LED_RETAIN_OFF" in s:
    print("patch_ledpwm: already applied"); sys.exit(0)
n = 0

# 1) retention release helper (no-op where the SoC has no retention)
helper = ('#include <hal/nrf_gpio.h>\n'
          '#if NRF_GPIO_HAS_RETENTION && DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, led_gpios)\n'
          '#define LED_RETAIN_OFF() nrf_gpio_pin_retain_disable(NRF_DT_GPIOS_TO_PSEL(ZEPHYR_USER_NODE, led_gpios))\n'
          '#else\n'
          '#define LED_RETAIN_OFF() ((void)0)\n'
          '#endif\n')
anchor = "static enum sys_led_pattern current_led_pattern;\n"
if anchor in s:
    s = s.replace(anchor, helper + "\n" + anchor, 1); n += 1

# 2) PWM owns the pad -> GPIO must not reconfigure it; otherwise configure + drop the latch
old = ("#if LED_EXISTS\n"
       "\tgpio_pin_configure_dt(&led, GPIO_OUTPUT);\n"
       "\tgpio_pin_set_dt(&led, 0);\n"
       "#endif\n")
new = ("#if LED_EXISTS && !defined(PWM_LED_EXISTS)\n"
       "\tgpio_pin_configure_dt(&led, GPIO_OUTPUT);\n"
       "\tLED_RETAIN_OFF();\n"
       "\tgpio_pin_set_dt(&led, 0);\n"
       "\tLED_RETAIN_OFF();\n"
       "#endif\n")
if old in s: s = s.replace(old, new, 1); n += 1

old = ("#if LED_EXISTS\n"
       "\tgpio_pin_configure_dt(&led, GPIO_DISCONNECTED);\n"
       "#endif\n")
new = ("#if LED_EXISTS && !defined(PWM_LED_EXISTS)\n"
       "\tgpio_pin_configure_dt(&led, GPIO_DISCONNECTED);\n"
       "#endif\n")
if old in s: s = s.replace(old, new, 1); n += 1

# 3) the LED drive itself stays on upstream's light gpio_pin_set_dt; just drop the latch
old = "\tgpio_pin_set_dt(&led, value_pptt > 5000);\n"
new = "\tgpio_pin_set_dt(&led, value_pptt > 5000);\n\tLED_RETAIN_OFF();\n"
if old in s: s = s.replace(old, new, 1); n += 1

open(f, "w", encoding="utf-8").write(s)
print("patch_ledpwm: applied %d/4 (retention latch released; PWM-owned pin left alone)" % n)
sys.exit(0)
