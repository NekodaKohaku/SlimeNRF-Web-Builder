#!/usr/bin/env python3
# jiting fork を nRF54L でコンパイル可能にする総合パッチ。
# (fork の dev は nRF52 中心で、54L パスに未ガード箇所が残っている)
#
# 1) esb_ota_flash.c: OTA 適用エンジン (NVMC 直書き = nRF52 専用) をガード
# fork の OTA 適用エンジンは NVMC 直書き (nRF52 専用ペリフェラル) のため
# 54L では include の時点で壊れる。NVMC 部分を nRF52 系ガードで包み、
# 54L には「未対応エラー + リセット」のスタブを与える。
# (OTA の受信・staging は共通 flash API なのでそのまま生きる)
import sys
f = "src/system/esb_ota_flash.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
MARK = "SLIMENRF_54L_OTA_GUARD"
if MARK in s:
    print("patch_jiting_54l_ota: already applied"); sys.exit(0)
changed = 0

def repl(old, new):
    global s, changed
    o = old.replace("\n", NL); n = new.replace("\n", NL)
    if o in s:
        s = s.replace(o, n, 1); changed += 1; return True
    return False

# 1) NVMC ヘッダは nRF52 系のみ include
repl(
"#include <hal/nrf_nvmc.h>\n",
"#if defined(CONFIG_SOC_SERIES_NRF52X) /* " + MARK + " */\n#include <hal/nrf_nvmc.h>\n#endif\n")

# 2) RAM コピー関数 + copy_and_reset を nRF52 系ガードで包む
repl(
"__attribute__((noinline))\nstatic void ota_flash_copy_from_ram(const struct flash_copy_params *p)\n",
"#if defined(CONFIG_SOC_SERIES_NRF52X)\n__attribute__((noinline))\nstatic void ota_flash_copy_from_ram(const struct flash_copy_params *p)\n")

repl(
"\tram_copy(&params);\n\t/* Never reached */\n}\n",
"\tram_copy(&params);\n\t/* Never reached */\n}\n#else /* !CONFIG_SOC_SERIES_NRF52X (" + MARK + ") */\n"
"void esb_ota_flash_copy_and_reset(uint32_t staging_base, uint32_t target_base,\n"
"\t\t\t\t  uint32_t image_size)\n"
"{\n"
"\t(void)staging_base; (void)target_base; (void)image_size;\n"
"\tLOG_ERR(\"OTA apply engine not supported on this SoC (nRF52 only); rebooting\");\n"
"\tk_msleep(100);\n"
"\tNVIC_SystemReset();\n"
"}\n"
"#endif\n")

if changed >= 3:
    open(f, "w", encoding="utf-8", newline="").write(s)
    print(f"patch_jiting_54l: esb_ota_flash.c {changed}/3 OK")
else:
    print(f"patch_jiting_54l: FAILED, esb_ota_flash.c only {changed}/3 hunks", file=sys.stderr)
    sys.exit(1)

# 2) clock_control.c: NRF_CLOCK_LFCLK_XTAL_FULL_SWING は nRF52 系 HAL のみ。
#    fork は LOW_SWING にはガードを付けたが FULL_SWING を忘れている
f2 = "src/system/clock_control.c"
s2 = open(f2, encoding="utf-8", newline="").read()
NL2 = "\r\n" if "\r\n" in s2 else "\n"
changed2 = 0

def repl2(old, new):
    global s2, changed2
    o = old.replace("\n", NL2); n = new.replace("\n", NL2)
    if o in s2:
        s2 = s2.replace(o, n, 1); changed2 += 1; return True
    return False

repl2(
"\tif (\n\t\tsource == NRF_CLOCK_LFCLK_XTAL_FULL_SWING\n",
"\tif (\n#ifdef NRF_CLOCK_LFCLK_XTAL_FULL_SWING /* " + MARK + " */\n\t\tsource == NRF_CLOCK_LFCLK_XTAL_FULL_SWING\n#else\n\t\tfalse\n#endif\n")

repl2(
"\t\t&& (source == NRF_CLOCK_LFCLK_XTAL || source == NRF_CLOCK_LFCLK_XTAL_FULL_SWING)) {\n",
"\t\t&& (source == NRF_CLOCK_LFCLK_XTAL\n#ifdef NRF_CLOCK_LFCLK_XTAL_FULL_SWING\n\t\t|| source == NRF_CLOCK_LFCLK_XTAL_FULL_SWING\n#endif\n\t\t)) {\n")

if changed2 >= 2:
    open(f2, "w", encoding="utf-8", newline="").write(s2)
    print(f"patch_jiting_54l: clock_control.c {changed2}/2 OK")
else:
    print(f"patch_jiting_54l: FAILED, clock_control.c only {changed2}/2 hunks", file=sys.stderr)
    sys.exit(1)

# 3) watchdog.c: nRF52 専用アクセスが 3 箇所
#    - GPREGRET: 54L では配列 (GPREGRET[0])
#    - DT_NODELABEL(wdt): 54L のノードは wdt31 (overlay で status okay にする)
#    - RESET_RESETREAS_DOG_Msk: 54L では DOG0/DOG1 に分割
f3 = "src/system/watchdog.c"
s3 = open(f3, encoding="utf-8", newline="").read()
NL3 = "\r\n" if "\r\n" in s3 else "\n"
changed3 = 0

def repl3(old, new):
    global s3, changed3
    o = old.replace("\n", NL3); n = new.replace("\n", NL3)
    if o in s3:
        s3 = s3.replace(o, n, 1); changed3 += 1; return True
    return False

repl3(
"\tsaved_gpregret = NRF_POWER->GPREGRET & 0xFF;\n"
"\tif (saved_gpregret >= 0xD0 && saved_gpregret <= 0xDE) {\n"
"\t\t/* Clear it so bootloader doesn't see it on next reset */\n"
"\t\tNRF_POWER->GPREGRET = 0;\n"
"\t}\n",
"#if defined(CONFIG_SOC_SERIES_NRF52X) /* " + MARK + " */\n"
"\tsaved_gpregret = NRF_POWER->GPREGRET & 0xFF;\n"
"\tif (saved_gpregret >= 0xD0 && saved_gpregret <= 0xDE) {\n"
"\t\t/* Clear it so bootloader doesn't see it on next reset */\n"
"\t\tNRF_POWER->GPREGRET = 0;\n"
"\t}\n"
"#else /* nRF54L: GPREGRET is an array */\n"
"\tsaved_gpregret = NRF_POWER->GPREGRET[0] & 0xFF;\n"
"\tif (saved_gpregret >= 0xD0 && saved_gpregret <= 0xDE) {\n"
"\t\tNRF_POWER->GPREGRET[0] = 0;\n"
"\t}\n"
"#endif\n")

repl3(
"\tconst struct device *wdt_dev = DEVICE_DT_GET(DT_NODELABEL(wdt));\n",
"#if DT_NODE_HAS_STATUS(DT_NODELABEL(wdt), okay)\n"
"\tconst struct device *wdt_dev = DEVICE_DT_GET(DT_NODELABEL(wdt));\n"
"#elif DT_NODE_HAS_STATUS(DT_NODELABEL(wdt31), okay)\n"
"\tconst struct device *wdt_dev = DEVICE_DT_GET(DT_NODELABEL(wdt31)); /* nRF54L */\n"
"#else\n"
"\tconst struct device *wdt_dev = NULL; /* no WDT node: device_is_ready(NULL)=false -> graceful disable */\n"
"#endif\n")

repl3(
"\tuint32_t reset_reason = NRF_RESET->RESETREAS;\n"
"\treturn (reset_reason & RESET_RESETREAS_DOG_Msk) != 0;\n",
"\tuint32_t reset_reason = NRF_RESET->RESETREAS;\n"
"\tuint32_t dog_msk = 0;\n"
"#if defined(RESET_RESETREAS_DOG_Msk)\n"
"\tdog_msk |= RESET_RESETREAS_DOG_Msk;\n"
"#endif\n"
"#if defined(RESET_RESETREAS_DOG0_Msk) /* nRF54L */\n"
"\tdog_msk |= RESET_RESETREAS_DOG0_Msk;\n"
"#endif\n"
"#if defined(RESET_RESETREAS_DOG1_Msk)\n"
"\tdog_msk |= RESET_RESETREAS_DOG1_Msk;\n"
"#endif\n"
"\treturn (reset_reason & dog_msk) != 0;\n")

if changed3 >= 3:
    open(f3, "w", encoding="utf-8", newline="").write(s3)
    print(f"patch_jiting_54l: watchdog.c {changed3}/3 OK")
else:
    print(f"patch_jiting_54l: FAILED, watchdog.c only {changed3}/3 hunks", file=sys.stderr)
    sys.exit(1)
