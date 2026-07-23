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

# 4) TDMA 時基修正: プロトコルの "server ticks" は 32768Hz (nRF52 RTC kernel tick)
#    前提だが、nRF54L の GRTC kernel tick は 31250Hz (-4.86%)。ローカル tick を
#    そのまま server tick 領域に混ぜると、スロット位相が ~80ms 毎にフレーム全周を
#    掃引し、複数トラッカー同時運用で他機のスロットを踏み潰す
#    (単機ではスロット=フレームなので無症状)。
#    ローカル tick を 32768Hz 領域へ正規化し、スリープだけ逆変換する。
f4 = "src/connection/esb.c"
s4 = open(f4, encoding="utf-8", newline="").read()
NL4 = "\r\n" if "\r\n" in s4 else "\n"
changed4 = 0

def repl4(old, new, cnt=1):
    global s4, changed4
    o = old.replace("\n", NL4); n = new.replace("\n", NL4)
    if s4.count(o) >= cnt:
        s4 = s4.replace(o, n, cnt); changed4 += cnt; return True
    return False

# 4a) helper を NRF54L include ブロックの直後に挿入
repl4(
"#if defined(NRF54L15_XXAA)\n#include <hal/nrf_clock.h>\n#endif /* defined(NRF54L15_XXAA) */\n",
"#if defined(NRF54L15_XXAA)\n#include <hal/nrf_clock.h>\n#endif /* defined(NRF54L15_XXAA) */\n"
"\n/* " + MARK + ": TDMA/time-sync protocol ticks are 32768 Hz (nRF52 RTC kernel\n"
" * tick). nRF54L GRTC kernel tick is 31250 Hz; normalize local ticks into the\n"
" * 32768 Hz protocol domain (identity on nRF52). */\n"
"static inline uint32_t slimenrf_proto_ticks32(void)\n"
"{\n"
"#if CONFIG_SYS_CLOCK_TICKS_PER_SEC == 32768\n"
"\treturn sys_clock_tick_get_32();\n"
"#else\n"
"\treturn (uint32_t)((uint64_t)sys_clock_tick_get_32() * 32768ULL / CONFIG_SYS_CLOCK_TICKS_PER_SEC);\n"
"#endif\n"
"}\n")

# 4b) local tick 取得 3 箇所を helper に置換 (同一行 2 箇所 + ping_history 1 箇所)
repl4("uint32_t local_now = sys_clock_tick_get_32();",
      "uint32_t local_now = slimenrf_proto_ticks32(); /* " + MARK + " */", 2)
repl4("ping_history[ping_history_idx].ping_ticks = sys_clock_tick_get_32();",
      "ping_history[ping_history_idx].ping_ticks = slimenrf_proto_ticks32(); /* " + MARK + " */")

# 4c) us 変換: protocol ticks はローカル tick レートと無関係
repl4("\treturn k_ticks_to_us_near64(ticks);\n",
      "\treturn ticks * 1000000ULL / 32768ULL; /* " + MARK + ": protocol ticks are 32768Hz */\n")

if changed4 == 5:
    open(f4, "w", encoding="utf-8", newline="").write(s4)
    print(f"patch_jiting_54l: esb.c tick-domain {changed4}/5 OK")
else:
    print(f"patch_jiting_54l: FAILED, esb.c tick-domain only {changed4}/5 hunks", file=sys.stderr)
    sys.exit(1)

# 4d) tdma.c: スリープ量は protocol ticks -> ローカル tick へ逆変換
f5 = "src/connection/tdma.c"
s5 = open(f5, encoding="utf-8", newline="").read()
NL5 = "\r\n" if "\r\n" in s5 else "\n"
o5 = "\t\tk_sleep(K_TICKS(ticks_to_target));\n".replace("\n", NL5)
n5 = ("\t\t/* " + MARK + ": ticks_to_target is in 32768Hz protocol ticks; K_TICKS\n"
      "\t\t * wants local kernel ticks (31250Hz on nRF54L). Convert. */\n"
      "\t\tk_sleep(K_TICKS((uint64_t)ticks_to_target * CONFIG_SYS_CLOCK_TICKS_PER_SEC / 32768ULL));\n").replace("\n", NL5)
if o5 not in s5:
    print("patch_jiting_54l: FAILED, tdma.c sleep anchor not found", file=sys.stderr)
    sys.exit(1)
s5 = s5.replace(o5, n5, 1)
open(f5, "w", encoding="utf-8", newline="").write(s5)
print("patch_jiting_54l: tdma.c sleep conversion OK")
