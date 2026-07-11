#!/usr/bin/env python3
# TEMPORARY nRF54L sensor debug: once-per-second FIFO read counters, so we can
# see whether the IMU is actually producing data (fifo_pkts/s) or the FIFO is
# empty. nRF52 untouched (#if NRF54L15_XXAA). Remove once the data path is fixed.
import sys
f = "src/sensor/sensor.c"
s = open(f, encoding="utf-8").read()

anchor = "\t\t\tuint16_t packets = sensor_imu->fifo_read(raw_data, data_size); // TODO: name this better?"
block = anchor + (
    "\n#if defined(NRF54L15_XXAA)\n"
    "\t\t\t{\n"
    "\t\t\t\tstatic int64_t sdbg_t = 0;\n"
    "\t\t\t\tstatic uint32_t sdbg_pk = 0, sdbg_loops = 0;\n"
    "\t\t\t\tsdbg_pk += packets; sdbg_loops++;\n"
    "\t\t\t\tint64_t sdbg_now = k_uptime_get();\n"
    "\t\t\t\tif (sdbg_now - sdbg_t >= 1000) {\n"
    "\t\t\t\t\tLOG_INF(\"[sdbg] fifo_pkts/s=%u loops/s=%u last_read=%u\", sdbg_pk, sdbg_loops, packets);\n"
    "\t\t\t\t\tsdbg_pk = 0; sdbg_loops = 0; sdbg_t = sdbg_now;\n"
    "\t\t\t\t}\n"
    "\t\t\t}\n"
    "#endif"
)

if "[sdbg] fifo_pkts/s=" in s:
    print("patch_sensordebug: already applied")
elif anchor in s:
    open(f, "w", encoding="utf-8").write(s.replace(anchor, block, 1))
    print("patch_sensordebug: nRF54L per-second FIFO debug added")
else:
    print("patch_sensordebug: WARNING anchor not found (upstream changed?)", file=sys.stderr)
sys.exit(0)
