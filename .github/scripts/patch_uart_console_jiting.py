#!/usr/bin/env python3
# jiting fork (jitingcn/SlimeVR-Tracker-nRF@dev) 用の UART console 解放パッチ。
# 上流用の patch_uart_console.py と同じ考え方 (USB_EXISTS ゲートを
# UART_CONSOLE_EXISTS でも通す) だが、fork は USB_DEVICE_STACK_NEXT ベースで
# コードが異なるため、アンカーを fork の実テキストに合わせている。
import sys
f = "src/console.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if "UART_CONSOLE_EXISTS" in s:
    print("patch_uart_console_jiting: already applied"); sys.exit(0)
changed = 0

def repl(old, new):
    global s, changed
    o = old.replace("\n", NL); n = new.replace("\n", NL)
    if o in s:
        s = s.replace(o, n, 1); changed += 1; return True
    return False

# 1) UART_CONSOLE_EXISTS 定義を追加
repl(
"#define USB_EXISTS (DT_NODE_HAS_STATUS(USB, okay) && CONFIG_UART_CONSOLE)\n#endif\n",
"#define USB_EXISTS (DT_NODE_HAS_STATUS(USB, okay) && CONFIG_UART_CONSOLE)\n#endif\n"
"#define UART_CONSOLE_EXISTS (IS_ENABLED(CONFIG_UART_CONSOLE) && DT_HAS_CHOSEN(zephyr_console) && DT_NODE_HAS_STATUS(DT_CHOSEN(zephyr_console), okay) && DT_NODE_HAS_COMPAT(DT_CHOSEN(zephyr_console), nordic_nrf_uarte))\n")

# 2) console 全体のゲート
repl(
"#if (USB_EXISTS || CONFIG_RTT_CONSOLE) && CONFIG_USE_SLIMENRF_CONSOLE\n",
"#if (USB_EXISTS || UART_CONSOLE_EXISTS || CONFIG_RTT_CONSOLE) && CONFIG_USE_SLIMENRF_CONSOLE\n")

# 3) include の分岐
repl(
"#if USB_EXISTS\n#include <zephyr/console/console.h>\n#include <zephyr/logging/log_ctrl.h>\n#include <zephyr/drivers/uart.h>\n#else\n#include \"system/rtt_console.h\"\n#endif\n",
"#if USB_EXISTS || UART_CONSOLE_EXISTS\n#include <zephyr/console/console.h>\n#include <zephyr/logging/log_ctrl.h>\n#include <zephyr/drivers/uart.h>\n#else\n#include \"system/rtt_console.h\"\n#endif\n")

# 4) console_getline_init (DTR 待ちは USB 専用のまま残す)
repl(
"#if USB_EXISTS\n\tconsole_getline_init();\n",
"#if USB_EXISTS || UART_CONSOLE_EXISTS\n\tconsole_getline_init();\n#endif\n#if USB_EXISTS\n")

# 5) getline ループ
repl(
"#if USB_EXISTS\n\t\tchar *line = console_getline();\n#else\n\t\tchar *line = rtt_console_getline();\n#endif\n",
"#if USB_EXISTS || UART_CONSOLE_EXISTS\n\t\tchar *line = console_getline();\n#else\n\t\tchar *line = rtt_console_getline();\n#endif\n")

if changed >= 5:
    open(f, "w", encoding="utf-8", newline="").write(s)
    print(f"patch_uart_console_jiting: applied {changed}/5"); sys.exit(0)
print(f"patch_uart_console_jiting: FAILED, only {changed}/5 hunks matched", file=sys.stderr)
sys.exit(1)
