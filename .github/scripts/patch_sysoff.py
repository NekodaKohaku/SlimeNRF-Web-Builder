#!/usr/bin/env python3
# power.c: release the sensor supply pins before System OFF.
#
# sys_disconnect_interface_pins() only disconnects chip selects. On boards that
# drive the sensor supply from GPIO - which upstream's own promicro definition
# does, with both vcc-gpios and gnd-gpios - the IMU is still fully powered when
# the SoC enters System OFF, and it keeps drawing its normal current for as long
# as the board sits there.
#
# Upstream knows: the function carries a TODO saying "for promicro, leaving
# ext_vcc on draws ~50uA, disconnect works". It was never wired up, and there is
# no handling for gnd-gpios at all.
#
# The datasheet figure for nRF52840 System OFF is 0.4 uA (1.5 uA with full RAM
# retention). Measured boards land around 135 uA, which is the sensor still
# running rather than anything about the SoC.
#
# Both pins go to the reset state (input, no pull, input buffer disconnected)
# rather than driven low. Driving either one is another way into the sensor:
# with ground driven and the supply floating, current flows in through the ESD
# diodes on SCK/MOSI/CS and powers the die from the signal side instead.
#
# Order matters. The supply is released first and ground last, because letting
# go of ground first leaves the sensor supplied with no return path, which leaks
# just as badly through whatever pin can sink it.
import sys

MARK = "SLIMENRF_SYSOFF_SUPPLY"
f = "src/system/power.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"

if MARK in s:
    print("patch_sysoff: already applied")
    sys.exit(0)

old = """/*
	TODO: for promicro, leaving ext_vcc on draws ~50uA, disconnect works, pulldown may be more reliable
	what to do about boards that use ext_vcc? it is not expected to leave on during WOM
*/
}
"""

new = """	/* """ + MARK + """: the TODO below is the whole story - a board that powers
	 * its IMU from GPIO leaves it running through System OFF, which is worth far
	 * more than the SoC's own 0.4 uA. Release both supply pins.
	 *
	 * Reset state (input, no pull, buffer disconnected), not driven low: a driven
	 * pin is another path into the sensor. With ground driven and the supply
	 * floating, current flows in through the ESD diodes on SCK/MOSI/CS and powers
	 * the die from the signal side.
	 *
	 * Supply first, ground last. The other order leaves the sensor supplied with
	 * no return path, which leaks through whatever pin can sink it.
	 */
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, vcc_gpios)
	nrf_gpio_cfg_default(NRF_DT_GPIOS_TO_PSEL(ZEPHYR_USER_NODE, vcc_gpios));
	LOG_INF("Disconnected sensor VCC GPIO");
#endif
#if DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, gnd_gpios)
	nrf_gpio_cfg_default(NRF_DT_GPIOS_TO_PSEL(ZEPHYR_USER_NODE, gnd_gpios));
	LOG_INF("Disconnected sensor GND GPIO");
#endif
/*
	TODO: for promicro, leaving ext_vcc on draws ~50uA, disconnect works, pulldown may be more reliable
	what to do about boards that use ext_vcc? it is not expected to leave on during WOM
*/
}
"""

o = old.replace("\n", NL)
if o not in s:
    sys.exit("patch_sysoff: FAILED, sys_disconnect_interface_pins tail not found "
             "(upstream may have changed)")

s = s.replace(o, new.replace("\n", NL), 1)
open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_sysoff: applied (sensor VCC/GND released before System OFF)")
