#!/usr/bin/env python3
# TEMPORARY receiver (dongle) debug for SlimeVR-Tracker-nRF-Receiver.
# Prints, once per second, per-tracker RX packets received and packets forwarded
# to HID. Lets us watch, from the dongle side, exactly what happens when a tracker
# drops: does rx/s go to 0 (dongle stopped hearing it -> RF) or does rx/s continue
# while fwd/s stops / server still drops (-> forwarding/server side)?
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()
n = 0

g_old = "uint8_t packets_lost[256] = {0};\n"
g_new = ("uint8_t packets_lost[256] = {0};\n"
         "static uint32_t rdbg_rx[16] = {0};\n"
         "static uint32_t rdbg_fwd[16] = {0};\n"
         "static int64_t rdbg_t = 0;\n")
if "rdbg_rx[16]" not in s and g_old in s:
    s = s.replace(g_old, g_new, 1); n += 1

rx_old = "\t\t\tswitch (rx_payload.length)\n\t\t\t{"
rx_new = ("\t\t\t{\n"
          "\t\t\t\tuint8_t rtid = rx_payload.data[1];\n"
          "\t\t\t\tif (rtid < 16) rdbg_rx[rtid]++;\n"
          "\t\t\t\tint64_t rnow = k_uptime_get();\n"
          "\t\t\t\tif (rnow - rdbg_t >= 1000) {\n"
          "\t\t\t\t\tLOG_INF(\"[rdbg] rx/s t0=%u t1=%u t2=%u | fwd/s t0=%u t1=%u t2=%u\", rdbg_rx[0], rdbg_rx[1], rdbg_rx[2], rdbg_fwd[0], rdbg_fwd[1], rdbg_fwd[2]);\n"
          "\t\t\t\t\tfor (int rii = 0; rii < 16; rii++) { rdbg_rx[rii] = 0; rdbg_fwd[rii] = 0; }\n"
          "\t\t\t\t\trdbg_t = rnow;\n"
          "\t\t\t\t}\n"
          "\t\t\t}\n"
          "\t\t\tswitch (rx_payload.length)\n\t\t\t{")
if "[rdbg] rx/s" not in s and rx_old in s:
    s = s.replace(rx_old, rx_new, 1); n += 1

fwd_old = "\t\t\t\thid_write_packet_n(rx_payload.data, rx_payload.rssi); // write to hid endpoint"
fwd_new = ("\t\t\t\tif (imu_id < 16) rdbg_fwd[imu_id]++;\n"
           "\t\t\t\thid_write_packet_n(rx_payload.data, rx_payload.rssi); // write to hid endpoint")
if "if (imu_id < 16) rdbg_fwd" not in s and fwd_old in s:
    s = s.replace(fwd_old, fwd_new, 1); n += 1

if "[rdbg] rx/s" in s and "rdbg_fwd[rtid]" not in s:  # marker of full apply
    pass
open(f, "w", encoding="utf-8").write(s)
print(f"patch_recvdebug: applied {n}/3 hunks")
sys.exit(0)
