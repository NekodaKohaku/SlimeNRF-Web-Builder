#!/usr/bin/env python3
# Cap the nRF54L high-rate (precise-quat) send rate to reduce RF airtime.
#
# When moving, connection_thread hits "else if (quat_update_time)" and sends a
# full-precision packet for EVERY fusion output (~230/s, seen as tx/s spiking to
# ~248). On a channel shared with other trackers this floods airtime -> jams the
# other trackers (worse when close) and can overrun the dongle->server forwarding
# (-> "freeze then drop"). nRF52 keeps full rate; only nRF54L is capped to ~100/s.
import sys
f = "src/connection/connection.c"
s = open(f, encoding="utf-8").read()
old = ("\t\t// send quat otherwise\n"
       "\t\telse if (quat_update_time)\n"
       "\t\t{")
new = ("\t\t// send quat otherwise\n"
       "#if defined(NRF54L15_XXAA)\n"
       "\t\telse if (quat_update_time && k_uptime_get() - last_quat_time >= 10) // nRF54L: cap precise-quat to ~100/s to cut RF airtime (coexistence)\n"
       "#else\n"
       "\t\telse if (quat_update_time)\n"
       "#endif\n"
       "\t\t{")
if "k_uptime_get() - last_quat_time >= 10) // nRF54L" in s:
    print("patch_ratecap: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_ratecap: nRF54L precise-quat capped to ~100/s")
else:
    print("patch_ratecap: WARNING anchor not found", file=sys.stderr)
sys.exit(0)
