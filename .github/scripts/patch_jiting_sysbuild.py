#!/usr/bin/env python3
# jiting sysbuild.cmake: overlay 適用順序の修正。
#
# fork はユーザーの EXTRA_DTC_OVERLAY_FILE を先に、socs/ overlay を後に並べる。
# これだと socs の `&cpuapp_sram { reg = 0x3f000 }` がこちらの mcuboot 追記
# (boot-mode retention 用の 0x3ee00 縮小) を上書きし、カーネル RAM が
# boot-mode retention 領域 (0x2003ee00) と重なってメモリ破壊が起きる。
# 正しい意味論 (公式/Zephyr ネイティブと同じ): SoC デフォルトが先、
# ユーザー overlay が最後 = 最優先。
import sys

MARK = "SLIMENRF_OVERLAY_ORDER"
f = "sysbuild.cmake"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_jiting_sysbuild: already applied"); sys.exit(0)

USER_APPEND = (
"if(DEFINED EXTRA_DTC_OVERLAY_FILE)\n"
"  list(APPEND ${DEFAULT_IMAGE}_EXTRA_DTC_OVERLAY_FILE ${EXTRA_DTC_OVERLAY_FILE})\n"
"endif()\n").replace("\n", NL)

SOCS_LOOP_END = (
"foreach(extra_dtc_overlay_candidate ${extra_dtc_overlay_candidates})\n"
"  if(EXISTS ${extra_dtc_overlay_candidate})\n"
"    list(APPEND ${DEFAULT_IMAGE}_EXTRA_DTC_OVERLAY_FILE ${extra_dtc_overlay_candidate})\n"
"  endif()\n"
"endforeach()\n").replace("\n", NL)

if USER_APPEND not in s or SOCS_LOOP_END not in s:
    sys.exit("patch_jiting_sysbuild: FAILED, anchors not found in sysbuild.cmake")

# 1) ユーザー overlay の先行 append を削除
s = s.replace(USER_APPEND, "# (" + MARK + ": user overlays moved below socs/ - applied last)" + NL, 1)
# 2) socs ループの直後に移動 (ユーザー overlay = 最後 = 最優先)
s = s.replace(SOCS_LOOP_END,
    SOCS_LOOP_END + NL +
    "# " + MARK + ": user overlays apply AFTER socs/ defaults (same semantics as" + NL +
    "# non-sysbuild builds), so e.g. the mcuboot cpuapp_sram shrink is not undone." + NL +
    "if(DEFINED EXTRA_DTC_OVERLAY_FILE)" + NL +
    "  list(APPEND ${DEFAULT_IMAGE}_EXTRA_DTC_OVERLAY_FILE ${EXTRA_DTC_OVERLAY_FILE})" + NL +
    "endif()" + NL, 1)

# ---- 2) pm_static 探索の uf2 ゲート解除 ----
# fork は pm_static 探索を "uf2" ボード限定にしたが、公式は全ボード無条件。
# これにより test54l 等で凍結レイアウト (pm_static_*.yml) が無視され、
# Partition Manager が動的配置 -> update.bin のアドレス安定性が壊れる
# (実測: 動的 app@0xC000 vs 凍結 app@0x10800)。公式と同じ無条件探索に戻す。
GATE = ('if((DEFINED SB_CONFIG_BOARD AND SB_CONFIG_BOARD MATCHES "uf2") OR '
        '(DEFINED SB_CONFIG_BOARD_QUALIFIERS AND SB_CONFIG_BOARD_QUALIFIERS MATCHES "uf2"))')
if GATE not in s:
    sys.exit("patch_jiting_sysbuild: FAILED, pm_static uf2 gate anchor not found")
s = s.replace(GATE, "if(1) # " + MARK + ": pm_static hunt for ALL boards (upstream-official behavior; was uf2-gated)", 1)

open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_jiting_sysbuild: overlay order fixed (socs first, user overlays last)")
print("patch_jiting_sysbuild: pm_static hunt un-gated (all boards)")
