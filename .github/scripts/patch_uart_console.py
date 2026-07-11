#!/usr/bin/env python3
# Unlock the interactive SlimeNRF console over a hardware UART (no USB).
# console.c gates the Zephyr console-subsystem path behind USB_EXISTS; on nRF54L
# (no usbd) it falls back to RTT, so typed commands only work over a debugger.
# console_getline() actually reads from `chosen zephyr,console`, which the builder
# points at a UARTE when tx/rx pins are given. All required Kconfigs
# (CONSOLE_SUBSYS/GETLINE, UART_CONSOLE, UART_INTERRUPT_DRIVEN) are already set.
# Add a self-gating UART_CONSOLE_EXISTS (true only when the chosen console is a
# nordic,nrf-uarte) that shares the USB_EXISTS console path. Inert on USB/RTT-only.
import sys
f = "src/console.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if "UART_CONSOLE_EXISTS" in s:
    print("patch_uart_console: already applied"); sys.exit(0)
changed = 0

def repl(old, new):
    global s, changed
    o = old.replace("\n", NL); n = new.replace("\n", NL)
    if o in s:
        s = s.replace(o, n, 1); changed += 1; return True
    return False

repl(
"#define USB_EXISTS (DT_NODE_HAS_STATUS(USB, okay) && CONFIG_UART_CONSOLE)\n#endif\n",
"#define USB_EXISTS (DT_NODE_HAS_STATUS(USB, okay) && CONFIG_UART_CONSOLE)\n#endif\n"
"#ifndef USB_EXISTS\n#define USB_EXISTS 0\n#endif\n"
"#define UART_CONSOLE_EXISTS (IS_ENABLED(CONFIG_UART_CONSOLE) && DT_HAS_CHOSEN(zephyr_console) && DT_NODE_HAS_STATUS(DT_CHOSEN(zephyr_console), okay) && DT_NODE_HAS_COMPAT(DT_CHOSEN(zephyr_console), nordic_nrf_uarte))\n")

repl(
"#if (USB_EXISTS || CONFIG_RTT_CONSOLE) && CONFIG_USE_SLIMENRF_CONSOLE\n",
"#if (USB_EXISTS || UART_CONSOLE_EXISTS || CONFIG_RTT_CONSOLE) && CONFIG_USE_SLIMENRF_CONSOLE\n")

repl(
"#if USB_EXISTS\n#include <zephyr/console/console.h>\n#include <zephyr/logging/log_ctrl.h>\n#else\n#include \"system/rtt_console.h\"\n#endif\n",
"#if USB_EXISTS || UART_CONSOLE_EXISTS\n#include <zephyr/console/console.h>\n#include <zephyr/logging/log_ctrl.h>\n#else\n#include \"system/rtt_console.h\"\n#endif\n")

repl(
"#if USB_EXISTS\n\tconsole_getline_init();\n\twhile (log_data_pending())\n\t\tk_usleep(1);\n\tk_msleep(100);\n\tprintk(\"*** \" CONFIG_USB_DEVICE_MANUFACTURER \" \" CONFIG_USB_DEVICE_PRODUCT \" ***\\n\");\n#endif\n",
"#if USB_EXISTS || UART_CONSOLE_EXISTS\n\tconsole_getline_init();\n#endif\n#if USB_EXISTS\n\twhile (log_data_pending())\n\t\tk_usleep(1);\n\tk_msleep(100);\n\tprintk(\"*** \" CONFIG_USB_DEVICE_MANUFACTURER \" \" CONFIG_USB_DEVICE_PRODUCT \" ***\\n\");\n#endif\n")

repl(
"#if USB_EXISTS\n\t\tchar *line = console_getline();\n#else\n\t\tchar *line = rtt_console_getline();\n#endif\n",
"#if USB_EXISTS || UART_CONSOLE_EXISTS\n\t\tchar *line = console_getline();\n#else\n\t\tchar *line = rtt_console_getline();\n#endif\n")

if changed >= 5:
    open(f, "w", encoding="utf-8", newline="").write(s)
    print(f"patch_uart_console: applied {changed}/5"); sys.exit(0)
print(f"patch_uart_console: WARNING only {changed}/5 hunks applied", file=sys.stderr)
sys.exit(0)
