#!/usr/bin/env python3
# connection_thread(): send-then-sleep bug -> caps the tracker's TX rate.
#
# In connection_thread(), EVERY branch ends with `continue;` except the one that
# actually transmits: after esb_write(data_copy) the code falls straight through to
#     sleep = true; k_msleep(...); sleep = false;
# so the thread goes to sleep after EVERY packet and can only send the next one once
# the sensor wakes it via `if (sleep) k_wakeup(connection_thread_id)`. That wakeup is
# also racy: if the sensor fires between `sleep = true;` and the thread actually
# entering k_msleep(), k_wakeup() hits a non-sleeping thread and is lost -- the thread
# then sleeps the full timeout (tens of ms).
#
# Measured effect on nRF54L: sensor delivers 343 pkts/s (loop 229/s) but the tracker
# only calls esb_write ~55 times/s, and erratically (26-90). The ESB re-init was
# measured at 63 us, so it is NOT the bottleneck -- this is.
#
# Fix: `continue;` after esb_write, matching every other branch. The thread then loops
# straight back and sends again if new data is ready, and only falls through to
# clocks_request_stop()/k_msleep() when there is genuinely nothing left to send.
import sys
f = "src/connection/connection.c"
s = open(f, encoding="utf-8").read()
old = ("\t\t\t*crc_ptr = crc32_k_4_2_update(0x93a409eb, data_copy, 16);\n"
       "\t\t\tesb_write(data_copy);\n"
       "\t\t}\n")
new = ("\t\t\t*crc_ptr = crc32_k_4_2_update(0x93a409eb, data_copy, 16);\n"
       "\t\t\tesb_write(data_copy);\n"
       "\t\t\tcontinue;\n"
       "\t\t}\n")
if "esb_write(data_copy);\n\t\t\tcontinue;" in s:
    print("patch_conntx: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_conntx: added continue after esb_write (no more sleep-after-every-packet)")
else:
    print("patch_conntx: WARNING hunk not matched (upstream changed?)", file=sys.stderr)

# The `continue` above exposes a second bug, and on nRF52 it is fatal.
#
# esb_write() only QUEUES the packet; the radio transmits it afterwards. Before the
# continue, the thread went straight to k_msleep() and the ESB event handler stopped the
# HF clock later, on TX_SUCCESS/TX_FAILED -- i.e. AFTER the transmission completed. With
# the continue, the thread loops straight back, finds no new sensor data yet, falls all
# the way through to `else { connection_clocks_request_stop(); }` and kills the HF clock
# WHILE THE PACKET IS STILL IN FLIGHT. The radio loses its clock mid-transmission and the
# TX fails: measured tx_err pinned at TX_ERROR_MAX (100) and "Connection error" within
# half a second of boot.
#
# nRF54L never saw this because patch_clkpolicy makes clocks_stop() a no-op while paired,
# so the premature stop did nothing. nRF52 has no such shield and took the hit.
#
# Fix at the point that is actually wrong: connection_thread must not stop the clock at
# all. esb.c's event handler already does it on TX_SUCCESS and TX_FAILED, which is the
# correct moment (transmission finished). The call here is redundant AND mistimed.
conn = "src/connection/connection.c"
c = open(conn, encoding="utf-8").read()
old_stop = "\t\telse\n\t\t{\n\t\t\tconnection_clocks_request_stop();\n\t\t}\n"
new_stop = ("\t\telse\n\t\t{\n"
            "\t\t\t/* clock is stopped by esb.c's TX_SUCCESS/TX_FAILED handler, i.e. once the\n"
            "\t\t\t   transmission has actually finished. Stopping it here would kill the clock\n"
            "\t\t\t   while a queued packet is still in flight. */\n"
            "\t\t}\n")
if "still in flight" in c:
    print("patch_conntx: clock-stop removal already applied")
elif old_stop in c:
    open(conn, "w", encoding="utf-8").write(c.replace(old_stop, new_stop, 1))
    print("patch_conntx: removed premature connection_clocks_request_stop() (killed in-flight TX on nRF52)")
else:
    print("patch_conntx: WARNING clocks_request_stop hunk not matched", file=sys.stderr)

sys.exit(0)
