#!/usr/bin/env python3
# TEMP: make led.c report which path it compiled to and what it is doing.
# Distinguishes (A) pwm_led0 alias missing -> GPIO fallback on a PWM-owned pin,
# from (B) PWM path fine but PM suspend/resume leaves the pin in the sleep state.
import sys
f = "src/system/led.c"
s = open(f, encoding="utf-8").read()
if "[ldbg]" in s:
    print("patch_leddebug: already applied"); sys.exit(0)
n = 0

# 1) which path did we compile?
old = 'static int led_pin_init(void)\n{\n\tLOG_DBG("led_pin_init");\n'
new = ('static int led_pin_init(void)\n{\n\tLOG_DBG("led_pin_init");\n'
       '#ifdef PWM_LED_EXISTS\n'
       '\tLOG_INF("[ldbg] path=PWM  period=%u ns  dev=%s", (unsigned)pwm_led.period, pwm_led.dev ? pwm_led.dev->name : "NULL");\n'
       '#else\n'
       '\tLOG_INF("[ldbg] path=GPIO-FALLBACK  (DT_ALIAS(pwm_led0) MISSING!)");\n'
       '#endif\n'
       '#ifdef LED_EXISTS\n'
       '\tLOG_INF("[ldbg] LED_EXISTS=1 (led-gpios present)");\n'
       '#else\n'
       '\tLOG_INF("[ldbg] LED_EXISTS=0");\n'
       '#endif\n')
if old in s: s = s.replace(old, new, 1); n += 1

# 2) every actual drive call: what pulse are we asking for?
old = ('#elif PWM_LED_EXISTS\n'
       '\tvalue_pptt = value_pptt * brightness_pptt / 10000;\n')
new = ('#elif PWM_LED_EXISTS\n'
       '\tvalue_pptt = value_pptt * brightness_pptt / 10000;\n'
       '\tLOG_INF("[ldbg] set color=%d value=%d -> pulse=%u/%u", (int)color, value_pptt,\n'
       '\t\t(unsigned)(pwm_led.period / 10000 * (led_pwm_period[color][0] < 0 ? 10000 : led_pwm_period[color][0]) * value_pptt / 10000),\n'
       '\t\t(unsigned)pwm_led.period);\n')
if old in s: s = s.replace(old, new, 1); n += 1

# 3) is the PWM being suspended (and does it come back)?
old = 'static void led_suspend(void)\n{\n\tLOG_DBG("led_suspend");\n'
new = 'static void led_suspend(void)\n{\n\tLOG_INF("[ldbg] SUSPEND");\n'
if old in s: s = s.replace(old, new, 1); n += 1
old = 'static void led_resume(void)\n{\n\tLOG_DBG("led_resume");\n'
new = 'static void led_resume(void)\n{\n\tLOG_INF("[ldbg] RESUME");\n'
if old in s: s = s.replace(old, new, 1); n += 1

open(f, "w", encoding="utf-8").write(s)
print("patch_leddebug: applied %d/4" % n)
sys.exit(0)
