#!/usr/bin/env python3
# nRF54L only: raise the small thread stacks.
#
# The workflow already appends CONFIG_MAIN_STACK_SIZE=2048 because upstream's 512 crashes
# on nRF54L -- Cortex-M33 with FPU and TrustZone pushes noticeably larger exception/call
# frames than the nRF52's M4. But that only fixed main(); every K_THREAD_DEFINE in the app
# still uses the nRF52-sized 128/256/512 byte stacks.
#
# button_thread is defined with 256 bytes and, on a long press, runs the whole
# sys_request_system_off() -> configure_system_off() chain. On nRF54L that overflows:
#   <err> os: usage_fault: Stack overflow ... Current thread: button_thread_id
# so the board faults and RESETS instead of powering off -- which looks exactly like
# "hold the button, it blinks, let go, and it doesn't turn off".
#
# Raise every thread stack below MIN_STACK to MIN_STACK. RAM cost is ~10 KB out of 256 KB.
import re, sys, pathlib

MIN_STACK = 1024
n = 0
for path in pathlib.Path("src").rglob("*.c"):
    s = path.read_text(encoding="utf-8")
    orig = s

    def bump_thread(m):
        global n
        size = int(m.group(2))
        if size >= MIN_STACK:
            return m.group(0)
        n += 1
        return "%s%d%s" % (m.group(1), MIN_STACK, m.group(3))

    s = re.sub(r'(K_THREAD_DEFINE\(\s*\w+\s*,\s*)(\d+)(\s*,)', bump_thread, s)
    s = re.sub(r'(K_THREAD_STACK_DEFINE\(\s*\w+\s*,\s*)(\d+)(\s*\))', bump_thread, s)
    if s != orig:
        path.write_text(s, encoding="utf-8")

print("patch_stacks: raised %d thread stacks to >= %d bytes (nRF54L M33+FPU+TrustZone)" % (n, MIN_STACK))
sys.exit(0)
