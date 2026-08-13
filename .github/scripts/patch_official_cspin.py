#!/usr/bin/env python3
# 公式 power.c: シャットダウン時の SPI CS 切り離しでポート番号が抜けている問題。
#
# sys_disconnect_interface_pins() は
#     uint32_t imu_cs_gpios = DT_SPI_DEV_CS_GPIOS_PIN(DT_NODELABEL(imu_spi));
#     nrf_gpio_cfg_default(imu_cs_gpios);
# としているが、DT_SPI_DEV_CS_GPIOS_PIN が返すのは「ポート内の相対ピン番号」
# (P1.13 なら 13)。一方 nrf_gpio_cfg_default() が要求するのは絶対ピン番号
# (port * 32 + pin、P1.13 なら 45)。ポートのオフセットが抜けている。
#
# 実害:
#  - nRF54L15: P0 は 5 本 (P0.00-P0.04) しかないため、13 は存在しないピンと
#    判定され nrf_gpio_pin_present_check() の NRFX_ASSERT で kernel panic。
#    ボタン長押しシャットダウンのたびにリセット -> 勝手に再起動する
#    (実測: ME54BS01 + 公式 main、"ASSERTION FAIL @ nrf_gpio.h" で power_thread が落ちる)
#  - nRF52840: P0.13 は存在するので panic はしないが、まったく無関係の
#    ピンを cfg_default で叩き、本来切り離すべき CS は driven のまま残る
#
# あわせて mag_spi 側の余分な閉じ括弧 (構文エラー) も修正する。
# こちらは SPI 磁力計構成でしかコンパイルされないため露見していない。
#
# 修正方法: ポートを含む PSEL 値 (port << 5 | pin) を自前で組み立てる。
# nrf_gpio_* の絶対ピン番号 (port * 32 + pin) と同じ値になる。
# devicetree.h のマクロのみ使用するので追加の include は不要。
import sys

MARK = "SLIMENRF_CS_PSEL"
f = "src/system/power.c"
s = open(f, encoding="utf-8", newline="").read()
NL = "\r\n" if "\r\n" in s else "\n"
if MARK in s:
    print("patch_official_cspin: already applied"); sys.exit(0)

HELPER = (
"/* " + MARK + ": CS ピンの絶対番号 (port * 32 + pin)。\n"
" * DT_SPI_DEV_CS_GPIOS_PIN はポート内相対番号しか返さないため、\n"
" * nrf_gpio_* にそのまま渡すと別ポートのピンを叩いてしまう。 */\n"
"#define " + MARK + "(spi_dev)                                                       \\\n"
"\t((DT_PROP_BY_PHANDLE_IDX(DT_BUS(spi_dev), cs_gpios,                          \\\n"
"\t\t\t\t DT_REG_ADDR_RAW(spi_dev), port) << 5) |               \\\n"
"\t (DT_GPIO_PIN_BY_IDX(DT_BUS(spi_dev), cs_gpios,                              \\\n"
"\t\t\t     DT_REG_ADDR_RAW(spi_dev)) & 0x1F))\n"
"\n"
"static void sys_disconnect_interface_pins(void)\n")

OLD_FN = "static void sys_disconnect_interface_pins(void)\n"
if OLD_FN.replace("\n", NL) not in s:
    sys.exit("patch_official_cspin: FAILED, sys_disconnect_interface_pins anchor not found")
s = s.replace(OLD_FN.replace("\n", NL), HELPER.replace("\n", NL), 1)

# ---- IMU CS ----
old_imu = "\tuint32_t imu_cs_gpios = DT_SPI_DEV_CS_GPIOS_PIN(DT_NODELABEL(imu_spi));".replace("\n", NL)
new_imu = ("\tuint32_t imu_cs_gpios = " + MARK + "(DT_NODELABEL(imu_spi)); /* " + MARK + " */").replace("\n", NL)
if old_imu not in s:
    sys.exit("patch_official_cspin: FAILED, imu_cs anchor not found")
s = s.replace(old_imu, new_imu, 1)

# ---- Magnetometer CS (余分な ")" も同時に除去) ----
old_mag = "\tuint32_t mag_cs_gpios = DT_SPI_DEV_CS_GPIOS_PIN(DT_NODELABEL(mag_spi)));".replace("\n", NL)
new_mag = ("\tuint32_t mag_cs_gpios = " + MARK + "(DT_NODELABEL(mag_spi)); /* " + MARK + ": also fixes stray ')' */").replace("\n", NL)
if old_mag in s:
    s = s.replace(old_mag, new_mag, 1)
    print("patch_official_cspin: mag_spi CS fixed (incl. stray parenthesis)")
else:
    # 上流が既に直した場合に備えて、括弧なし版も試す
    old_mag2 = "\tuint32_t mag_cs_gpios = DT_SPI_DEV_CS_GPIOS_PIN(DT_NODELABEL(mag_spi));".replace("\n", NL)
    if old_mag2 in s:
        s = s.replace(old_mag2, new_mag, 1)
        print("patch_official_cspin: mag_spi CS fixed")
    else:
        print("patch_official_cspin: WARNING mag_spi anchor not found (upstream changed?)", file=sys.stderr)

open(f, "w", encoding="utf-8", newline="").write(s)
print("patch_official_cspin: power.c OK (CS pin now includes port offset)")
