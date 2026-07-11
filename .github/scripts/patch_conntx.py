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
sys.exit(0)
