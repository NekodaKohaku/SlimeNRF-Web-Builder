#!/usr/bin/env python3
# promicro_uf2 の board.c が P0.13 に無条件でプルを掛けるのを止める。
#
# 上流の board.c (PRE_KERNEL_1) には
#     /* pull down on P0.13, disables external 3V3 regulator */
#     nrf_gpio_cfg(NRF_GPIO_PIN_MAP(0, 13), ... PULLDOWN ...);
# がある。これは nice!nano / promicro 実機の回路 (P0.13 が外部 3V3
# レギュレータの EN に繋がっている) 前提の処理。
#
# この builder が対象にしているモジュール (MS88SF2 等) にはその
# レギュレータが無く、P0.13 は普通の GPIO。にもかかわらず全ドライバより
# 早い PRE_KERNEL_1 でプルが掛かるため、P0.13 を何かに使うと
# 内部プルと綱引きになる (実測はしていないが、WS2812 のダミー SCK 候補に
# していたピンでもある)。
#
# base_board が promicro_uf2 のときだけ実行される。ファイルや該当行が
# 無ければ何もしない (上流が書き換えた場合も安全に素通り)。
import os, re, sys

MARK = "SLIMENRF_NO_P013_PULL"
f = "boards/nordic/promicro_uf2/board.c"
if not os.path.isfile(f):
    print("patch_promicro_p013: board.c not found, skipped")
    sys.exit(0)

s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_promicro_p013: already applied"); sys.exit(0)

# 公式版と jiting 版で 4 番目の引数が違う (PULLDOWN / EXTERNAL_3V3_REGULATOR_PULL)
# 行末に \r を許容する: Windows で clone すると core.autocrlf により CRLF になり、
# newline="" で読むと行末が "\r\n" のままなので [ \t]*$ では一致しない。
pat = re.compile(
    r"^[ \t]*nrf_gpio_cfg\(NRF_GPIO_PIN_MAP\(0,\s*13\)[^;]*;[ \t\r]*$",
    re.M)
m = pat.search(s)
if not m:
    print("patch_promicro_p013: WARNING P0.13 pull line not found (upstream changed?)",
          file=sys.stderr)
    sys.exit(0)

old = m.group(0)
new = ("\t/* " + MARK + ": upstream pulls P0.13 to disable the external 3V3\n"
       "\t * regulator found on real promicro / nice!nano boards. The modules\n"
       "\t * this builder targets have no such regulator, so leave P0.13 as a\n"
       "\t * plain GPIO (a PRE_KERNEL_1 pull would fight whatever uses it). */\n"
       "\t/* " + old.strip() + " */").replace("\n", NL)

s = s.replace(old, new, 1)
open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_promicro_p013: board.c OK (P0.13 pull removed)")
