#!/usr/bin/env python3
# Make "no battery present" a clean state on power.c (fixes upstream bugs that
# surface on boards without a battery divider, e.g. nRF54L bring-up).
#
# Symptoms without this patch: battery_ok is false (ADC/divider unavailable),
# read_batt_mV() returns -1 WITHOUT writing *out, so battery_mV keeps an
# uninitialized stack value (e.g. 735401120). That garbage trips
# abnormal_reading, which latches SYS_STATUS_SYSTEM_ERROR ("General error")
# permanently and spams the log.
#
# Three fixes:
#   1. Initialize battery_mV = 0 (uninitialized-read bug).
#   2. Only treat a reading as abnormal if the read actually succeeded
#      (battery_pptt >= 0). A board with a real but broken battery still reports
#      abnormal correctly; a board with no battery no longer false-errors.
#   3. Downgrade the per-cycle read-fail log from LOG_ERR to LOG_DBG, matching
#      battery.c's own convention and the firmware's "keep working without the
#      battery connected" design.
import sys
f = "src/system/power.c"
s = open(f, encoding="utf-8").read()
n = 0

def repl(o, x):
    global s, n
    if o in s and x not in s:
        s = s.replace(o, x, 1); n += 1

repl("\t\tint battery_mV;\n",
     "\t\tint battery_mV = 0;\n")

repl("\t\tbool abnormal_reading = battery_mV < 100 || battery_mV > 6000;",
     "\t\tbool abnormal_reading = battery_pptt >= 0 && (battery_mV < 100 || battery_mV > 6000);")

repl('\t\t\tLOG_ERR("Failed to read battery voltage: %d", battery_pptt);',
     '\t\t\tLOG_DBG("Failed to read battery voltage: %d", battery_pptt);')

if n > 0:
    open(f, "w", encoding="utf-8").write(s)
    print(f"patch_batt: applied {n}/3")
elif "int battery_mV = 0;" in s:
    print("patch_batt: already applied")
else:
    print("patch_batt: WARNING no hunks matched (upstream changed?)", file=sys.stderr)
sys.exit(0)
