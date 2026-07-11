#!/usr/bin/env python3
# TEMP: dump the LED pin's actual PIN_CNF / OUT registers so we stop guessing who owns it.
# PIN_CNF tells us DIR (output?), INPUT (connected?), and on nRF54L the CTRLSEL field
# (which peripheral, if any, owns the pad). OUT tells us the level being driven.
import sys
f = "src/system/led.c"
s = open(f, encoding="utf-8").read()
if "[ldbg]" in s:
    print("patch_leddebug: already applied"); sys.exit(0)
n = 0

helper = '''
#include <hal/nrf_gpio.h>
static void ldbg_dump(const char *tag)
{
#if LED_EXISTS
	uint32_t abs_pin = NRF_GPIO_PIN_MAP(1, led.pin); /* LED is on gpio1 in this build */
	NRF_GPIO_Type *reg = nrf_gpio_pin_port_decode(&abs_pin);
	uint32_t cnf = reg->PIN_CNF[abs_pin];
	LOG_INF("[ldbg] %-10s P1.%02u PIN_CNF=0x%08x  DIR=%u INPUT=%u CTRLSEL=%u  OUT=%u",
		tag, (unsigned)led.pin, (unsigned)cnf,
		(unsigned)(cnf & 1), (unsigned)((cnf >> 1) & 1), (unsigned)((cnf >> 28) & 0xF),
		(unsigned)((reg->OUT >> led.pin) & 1));
#endif
}
#else
static void ldbg_dump(const char *tag) { (void)tag; }
#endif
'''
# helper 要放在 led/LED_EXISTS 宣告之後
anchor = "static enum sys_led_pattern current_led_pattern;\n"
assert anchor in s
s = s.replace(anchor, helper.replace("#else\nstatic void ldbg_dump(const char *tag) { (void)tag; }\n#endif\n", "") + "\n" + anchor, 1); n += 1

# 開機:哪條路徑
old = 'static int led_pin_init(void)\n{\n\tLOG_DBG("led_pin_init");\n'
new = ('static int led_pin_init(void)\n{\n\tLOG_DBG("led_pin_init");\n'
       '#ifdef PWM_LED_EXISTS\n\tLOG_INF("[ldbg] path=PWM");\n#else\n\tLOG_INF("[ldbg] path=GPIO");\n#endif\n'
       '\tldbg_dump("init-in");\n')
if old in s: s = s.replace(old, new, 1); n += 1
old = '#if LED3_EXISTS\n\tgpio_pin_configure_dt(&led3, GPIO_OUTPUT);\n\tgpio_pin_set_dt(&led3, 0);\n#endif\n\treturn 0;\n}\n\nSYS_INIT(led_pin_init'
new = '#if LED3_EXISTS\n\tgpio_pin_configure_dt(&led3, GPIO_OUTPUT);\n\tgpio_pin_set_dt(&led3, 0);\n#endif\n\tldbg_dump("init-out");\n\treturn 0;\n}\n\nSYS_INIT(led_pin_init'
if old in s: s = s.replace(old, new, 1); n += 1

# 每次點燈:設定前後的腳位狀態
old = '\tgpio_pin_configure_dt(&led, (value_pptt > 5000) ? GPIO_OUTPUT_ACTIVE : GPIO_OUTPUT_INACTIVE);\n#endif\n}\n'
new = ('\tldbg_dump("set-pre");\n\tgpio_pin_configure_dt(&led, (value_pptt > 5000) ? GPIO_OUTPUT_ACTIVE : GPIO_OUTPUT_INACTIVE);\n'
       '\tLOG_INF("[ldbg] gpio_cfg value=%d -> %d", value_pptt, value_pptt > 5000);\n'
       '\tldbg_dump("set-post");\n#endif\n}\n')
if old in s: s = s.replace(old, new, 1); n += 1

# suspend / resume
for a, b in [('static void led_suspend(void)\n{\n\tLOG_DBG("led_suspend");\n',
              'static void led_suspend(void)\n{\n\tLOG_INF("[ldbg] SUSPEND");\n\tldbg_dump("susp");\n'),
             ('static void led_resume(void)\n{\n\tLOG_DBG("led_resume");\n',
              'static void led_resume(void)\n{\n\tLOG_INF("[ldbg] RESUME");\n\tldbg_dump("resu");\n')]:
    if a in s: s = s.replace(a, b, 1); n += 1

open(f, "w", encoding="utf-8").write(s)
print("patch_leddebug: applied %d hunks (PIN_CNF/OUT dump)" % n)
sys.exit(0)
