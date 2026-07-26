#!/usr/bin/env python3
# Zephyr の ws2812-spi ドライバを「スケジューラ無し」環境でも使えるようにする。
#
# ws2812_reset_delay() は k_usleep() を使うが、mcuboot は
# CONFIG_MULTITHREADING=n (単一スレッド) でビルドされるため
# z_impl_k_usleep が存在せずリンクエラーになる。
#
# この待ちは「データ送出後にストリップの状態機械をラッチさせる」ための
# 数マイクロ秒 (既定 8us) の遅延であり、k_busy_wait() と意味は同じ。
# アプリ側 (マルチスレッド) でも 8us のビジーウェイトになるだけで実害はない。
#
# mcuboot ビルド時のみ実行される (fileformat=mcuboot)。
import os, sys

CANDIDATES = (
    "../zephyr/drivers/led_strip/ws2812_spi.c",
    "../../zephyr/drivers/led_strip/ws2812_spi.c",
)

path = sys.argv[1] if len(sys.argv) > 1 else next(
    (p for p in CANDIDATES if os.path.isfile(p)), None)
if not path or not os.path.isfile(path):
    print("patch_ws2812_nosched: ws2812_spi.c not found, skipped")
    sys.exit(0)

MARK = "SLIMENRF_NOSCHED"
s = open(path, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print(f"patch_ws2812_nosched: already applied ({path})")
    sys.exit(0)

OLD = "\tk_usleep(delay);".replace("\n", NL)
NEW = ("\t/* " + MARK + ": k_busy_wait works without a scheduler (mcuboot builds\n"
       "\t * use CONFIG_MULTITHREADING=n); same few-microsecond latch delay. */\n"
       "\tk_busy_wait(delay);").replace("\n", NL)

if OLD not in s:
    print("patch_ws2812_nosched: WARNING anchor not found (upstream changed?)", file=sys.stderr)
    sys.exit(0)

s = s.replace(OLD, NEW, 1)
open(path, "w", encoding="utf-8", newline="").write(s)
print(f"patch_ws2812_nosched: applied ({path})")
