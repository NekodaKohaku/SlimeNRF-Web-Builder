#!/usr/bin/env python3
# Guard nordic,nrf-temp (die temperature) usage.
# nRF54L15 has no such DT node -> temp_dev is NULL -> sensor_* calls jump to a
# null api pointer ("undefined instruction" fault, boot loop). Add device_is_ready guards.
# Harmless on nRF52 (temp_dev is ready).
import sys
f = "src/system/system.c"
s = open(f, encoding="utf-8").read()
changed = 0

o1 = ("\tif (k_uptime_get() - last_temp_time > 1000)\n"
      "\t\treturn -1;\n"
      "\tsensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &temp);")
n1 = ("\tif (k_uptime_get() - last_temp_time > 1000)\n"
      "\t\treturn -1;\n"
      "\tif (!device_is_ready(temp_dev))\n"
      "\t\treturn -1;\n"
      "\tsensor_channel_get(temp_dev, SENSOR_CHAN_DIE_TEMP, &temp);")
if o1 in s:
    s = s.replace(o1, n1, 1); changed += 1

o2 = ("\twhile (1)\n\t{\n\t\tif (sensor_sample_fetch(temp_dev))")
n2 = ("\twhile (1)\n\t{\n"
      "\t\tif (!device_is_ready(temp_dev))\n\t\t{\n\t\t\tk_msleep(1000);\n\t\t\tcontinue;\n\t\t}\n"
      "\t\tif (sensor_sample_fetch(temp_dev))")
if o2 in s:
    s = s.replace(o2, n2, 1); changed += 1

open(f, "w", encoding="utf-8").write(s)
print("patch_temp: applied %d guard(s) to system.c" % changed)
if changed != 2:
    print("WARN: expected 2 patches, got %d (source may have changed)" % changed, file=sys.stderr)
