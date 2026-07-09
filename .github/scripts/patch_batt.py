#!/usr/bin/env python3
# Quiet the per-cycle battery read error in power_thread.
# When no battery divider is wired (or the SAADC channel setup is unsupported,
# e.g. nRF54L rejecting the hardcoded ADC reference), battery_ok stays false and
# read_batt_mV returns -1 every ~100ms. The firmware already tolerates a missing
# battery ("Keep working without the battery connected"), and battery.c itself
# logs the same failure at LOG_DBG (see read_batt_mV / battery_sample). power.c is
# the lone inconsistent LOG_ERR, which spams the log. Align it to LOG_DBG.
import sys
f = "src/system/power.c"
s = open(f, encoding="utf-8").read()

o = '\t\t\tLOG_ERR("Failed to read battery voltage: %d", battery_pptt);'
n = '\t\t\tLOG_DBG("Failed to read battery voltage: %d", battery_pptt);'
if o in s:
    s = s.replace(o, n, 1)
    open(f, "w", encoding="utf-8").write(s)
    print("patch_batt: battery read-fail log -> LOG_DBG")
    sys.exit(0)

if 'LOG_DBG("Failed to read battery voltage: %d", battery_pptt);' in s:
    print("patch_batt: already applied")
    sys.exit(0)

print("patch_batt: WARNING target line not found (upstream changed?)", file=sys.stderr)
sys.exit(0)
