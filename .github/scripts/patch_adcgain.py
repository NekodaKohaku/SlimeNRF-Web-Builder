import pathlib

p = pathlib.Path("src/system/battery.c")
s = p.read_text(encoding="utf-8")

anchor = """	else if (max_adc_voltage < 3.0f)
		battery_adc_gain = ADC_GAIN_1_5;
"""
assert anchor in s, "patch_adcgain: gain ladder not found"
s = s.replace(anchor, anchor + """
#if !NRF_SAADC_HAS_GAIN_1_6 || !NRF_SAADC_HAS_GAIN_1_5
	if (battery_adc_gain == ADC_GAIN_1_6 || battery_adc_gain == ADC_GAIN_1_5)
		battery_adc_gain = ADC_GAIN_1_4;
#endif
""", 1)

inc = "#include <zephyr/drivers/adc.h>"
assert inc in s, "patch_adcgain: adc.h include not found"
s = s.replace(inc, inc + "\n#include <hal/nrf_saadc.h>", 1)

p.write_text(s, encoding="utf-8")
print("patch_adcgain: applied (unsupported 1/6 and 1/5 gains clamped to 1/4)")
