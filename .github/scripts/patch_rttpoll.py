#!/usr/bin/env python3
# rtt_console.h: the idle wait burns ~6.5 mA on any build without a USB or
# UART console.
#
#   while (SEGGER_RTT_HasKey() == 0)
#       k_usleep(1);
#
# k_usleep(1) asks for less than one system tick (30.5 us at 32768 Hz), so it
# rounds up and the console thread wakes on every single tick - 32768 times a
# second. The SoC never reaches a low-power state.
#
# It only shows up on the modules this builder targets. console.c picks the
# input function at compile time:
#
#   #if USB_EXISTS || UART_CONSOLE_EXISTS
#       char *line = console_getline();      // blocks, thread sleeps
#   #else
#       char *line = rtt_console_getline();  // spins
#   #endif
#
# Boards with USB or a UART console never take the second path, which is why
# upstream has not noticed. Configure a module with no TX/RX pins and current
# draw jumps from ~2.2 mA to ~8.6 mA - almost exactly the cost of keeping the
# CPU awake continuously.
#
# Polling every 20 ms makes the idle cost vanish. Throughput is unaffected:
# the sleep only happens when the buffer is empty, so a burst of characters
# still drains at full speed. Only the first keystroke sees added latency, and
# 20 ms is imperceptible when typing.
import sys

MARK = "SLIMENRF_RTT_IDLE_POLL"
f = "src/system/rtt_console.h"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"

if MARK in s:
    print("patch_rttpoll: already applied")
    sys.exit(0)

old = ("\t\twhile (SEGGER_RTT_HasKey() == 0)\n"
       "\t\t\tk_usleep(1);\n")
new = ("\t\t/* " + MARK + ": k_usleep(1) is below one system tick, so it\n"
       "\t\t * rounds up and wakes the CPU 32768 times a second - the SoC never\n"
       "\t\t * idles and it costs ~6.5 mA. Only builds without a USB or UART\n"
       "\t\t * console reach this path; the others block in console_getline().\n"
       "\t\t * The sleep only runs while the buffer is empty, so queued input\n"
       "\t\t * still drains at full speed. */\n"
       "\t\twhile (SEGGER_RTT_HasKey() == 0)\n"
       "\t\t\tk_msleep(20);\n")

o = old.replace("\n", NL)
if o not in s:
    sys.exit("patch_rttpoll: FAILED, idle poll loop not found in " + f)

s = s.replace(o, new.replace("\n", NL), 1)
open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_rttpoll: applied (RTT console idle poll 1us -> 20ms)")
