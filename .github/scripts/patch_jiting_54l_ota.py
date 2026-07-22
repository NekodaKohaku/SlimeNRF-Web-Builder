#!/usr/bin/env python3
# jiting fork の esb_ota_flash.c を nRF54L でもコンパイル可能にする。
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
    print(f"patch_jiting_54l_ota: applied {changed}/3"); sys.exit(0)
print(f"patch_jiting_54l_ota: FAILED, only {changed}/3 hunks matched", file=sys.stderr)
sys.exit(1)
