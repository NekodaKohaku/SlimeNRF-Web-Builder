#!/usr/bin/env python3
# Make the nRF54L DATA path genuinely no-ack.
#
# esb_write() already sets tx_payload.noack = true for nRF54L (upstream, the
# "esb halts with ack and tx fail" workaround). BUT esb_initialize() sets
# config.selective_auto_ack = true, and per esb.h the noack flag is IGNORED
# when selective auto ack is enabled. So on nRF54L the data packets still
# request an ACK -> failed ACK round-trip -> ESB retransmits the same packet ->
# the receiver sees stale sequence numbers ("expected 204, got 203, Discarding")
# and drops the data. Server sees nothing.
#
# Fix (nRF54L only): drive selective_auto_ack off the esb_paired flag.
#   - During pairing (esb_paired == false) -> selective_auto_ack = true.
#     Pairing needs the ACK/ack-payload handshake, keep it working.
#   - After pairing (esb_paired == true) -> selective_auto_ack = false, so the
#     existing noack = true takes effect: data is sent one-way, no retransmit,
#     clean sequence numbers. PRX (dongle) receives it regardless of ACK.
# nRF52 is left exactly as upstream (selective_auto_ack = true).
import sys
f = "src/connection/esb.c"
s = open(f, encoding="utf-8").read()

old = "\t\tconfig.selective_auto_ack = true; // TODO: while pairing, should be set to false"
new = ("#if defined(NRF54L15_XXAA)\n"
       "\t\tconfig.selective_auto_ack = !esb_paired; // nRF54L: ACK while pairing, no-ack for data (lets noack=true take effect, avoids ack-retransmit duplicate discards)\n"
       "#else\n"
       "\t\tconfig.selective_auto_ack = true; // TODO: while pairing, should be set to false\n"
       "#endif")

if "config.selective_auto_ack = !esb_paired;" in s:
    print("patch_esbnoack: already applied")
elif old in s:
    open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patch_esbnoack: nRF54L data path -> no-ack (selective_auto_ack = !esb_paired)")
else:
    print("patch_esbnoack: WARNING anchor not found (upstream changed?)", file=sys.stderr)
sys.exit(0)
