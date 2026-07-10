#!/usr/bin/env python3
# Keep uart0 alive for logging on no-USB boards.
#
# power_thread() unconditionally suspends uart0 (PM_DEVICE_ACTION_SUSPEND) at the
# top of its loop to save power. On USB boards this is fine: usb.c's status_cb
# RESUMES the console device when the host connects. But usb.c is wrapped in
# #if CONFIG_USB_DEVICE_STACK, so on a USB-disabled board (has_usb=false module
# built with CONFIG_USB_DEVICE_STACK=n) nothing ever resumes uart0 -> the UART
# log backend has an always-suspended device -> zero UART output.
#
# Fix: gate the uart0 suspend on CONFIG_USB_DEVICE_STACK, matching how usb.c
# itself is gated. No USB stack => never suspend uart0 => UART log works.
# USB boards keep the original suspend/resume behaviour untouched.
# nRF54L uses uart30/uart22 (not uart0), so this block never applied to it.
import sys
f = "src/system/power.c"
s = open(f, encoding="utf-8").read()

old = "#if DT_NODE_HAS_STATUS_OKAY(DT_NODELABEL(uart0))"
new = "#if DT_NODE_HAS_STATUS_OKAY(DT_NODELABEL(uart0)) && CONFIG_USB_DEVICE_STACK"

if new in s:
    print("patch_uart_pm: already applied")
elif old in s:
    s = s.replace(old, new, 1)
    open(f, "w", encoding="utf-8").write(s)
    print("patch_uart_pm: applied 1/1")
else:
    print("patch_uart_pm: WARNING no hunk matched (upstream changed?)", file=sys.stderr)
sys.exit(0)
