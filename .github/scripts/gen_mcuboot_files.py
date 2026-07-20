#!/usr/bin/env python3
# fileformat=mcuboot 用: MCUboot serial recovery のビルドファイル一式を生成する。
# SlimeVR-Tracker-nRF 内で実行:
#   gen_mcuboot_files.py "$CONFIG_JSON" [custom_overlay_path]
#
# 生成物:
#   sysbuild.conf                    - MCUboot 有効化、シングルスロット、hash のみ (鍵なし)
#   sysbuild/mcuboot.conf            - serial recovery の設定
#   sysbuild/mcuboot.overlay         - recovery 用 UART ピン + boot-mode retention (SoC 別)
#   pm_static/pm_static_<board>.yml  - 凍結パーティションレイアウト (SoC 別)。
#                                      どのビルドの update.bin も同じアプリアドレスを
#                                      対象にするために必須
#   custom overlay へ boot-mode ノードを追記 (アプリ側)
#   prj.conf へ retention の Kconfig を追記 (アプリ側)
#
# UART ピン: コンソール (gen_overlay.py) と同じ pins.tx / pins.rx を使い、
# UART ノード選択も同じ規則 (nRF52: uart0 / nRF54L: TX がポート 0 なら uart30、
# それ以外は uart22)。recovery とアプリコンソールが同じ配線を共有する。
import json, os, re, sys

cfg = json.loads(sys.argv[1])
custom_overlay = sys.argv[2] if len(sys.argv) > 2 else ""
board = cfg.get("board_target", "")
pins = cfg.get("pins", {}) or {}
tx, rx = pins.get("tx"), pins.get("rx")
if not (tx and rx):
    sys.exit("gen_mcuboot_files: fileformat=mcuboot requires both TX and RX pins")

def parse_pin(p):
    # "P0.06" / "0.06" / "P1_04" / "1,4" / "6" (ポート 0 扱い) を許容
    m = re.match(r"^\s*[Pp]?(\d+)[._,\s](\d+)\s*$", str(p))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^\s*(\d+)\s*$", str(p))
    if m:
        return 0, int(m.group(1))
    sys.exit(f"gen_mcuboot_files: cannot parse pin '{p}'")

# 診断モード: options.mcuboot_debug=="enabled" で mcuboot が UART にログを出す
# (zephyr,uart-mcumgr の代わりに zephyr,console を使う。同一 UART・115200)
_dbg = (cfg.get("options") or {}).get("mcuboot_debug")
debug = _dbg == "enabled"
# minimal: 裸 MCUboot 二分用 — recovery/retention/boot-mode 全部無効、
# console ログのみ有効。「素の MCUboot が app を起動できるか」を単独検証する
minimal = _dbg == "minimal"
# nano: 二分の最終段 — mcuboot を「ラッチ + ジャンプ」だけに剥ぐ。
# UART/console/GPIO ドライバ/entropy/検証 全部なし。観測手段はタップ挙動のみ
nano = _dbg == "nano"

txp, rxp = parse_pin(tx), parse_pin(rx)
is54 = "54l" in board.lower()
uart = ("uart30" if txp[0] == 0 else "uart22") if is54 else "uart0"
psels = (f"<NRF_PSEL(UART_TX, {txp[0]}, {txp[1]})>, "
         f"<NRF_PSEL(UART_RX, {rxp[0]}, {rxp[1]})>")

def write(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    print(f"== {path} ==\n{text}")

# ---------- sysbuild.conf (ルート) ----------
write("sysbuild.conf",
"""SB_CONFIG_BOOTLOADER_MCUBOOT=y
SB_CONFIG_MCUBOOT_MODE_SINGLE_APP=y
# DIY: signing key 不要。イメージ整合性は SHA-256 hash のみで検証
SB_CONFIG_BOOT_SIGNATURE_TYPE_NONE=y
""")

# ---------- sysbuild/mcuboot.conf ----------
write("sysbuild/mcuboot.conf",
"""# nano 診断: ラッチ + ジャンプのみ。サブシステム全部なし
CONFIG_FPROTECT=n
CONFIG_BOOT_VALIDATE_SLOT0=n
CONFIG_LOG=n
CONFIG_SERIAL=n
CONFIG_CONSOLE=n
CONFIG_UART_CONSOLE=n
CONFIG_GPIO=n
CONFIG_ENTROPY_GENERATOR=n
""" if nano else """# minimal 診断: 素の MCUboot + console ログのみ (recovery 一切なし)
CONFIG_FPROTECT=n
CONFIG_LOG=y
CONFIG_LOG_MODE_MINIMAL=y
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y
CONFIG_GPIO=y

# board.c の board_early_init_hook (電源自锁) を有効化
CONFIG_BOARD_EARLY_INIT_HOOK=y

# 診断: 起動時の hash 検証も無効化 -> mcuboot は純粋なジャンプ台になる。
# 起動直後の高負荷 (全 app 領域の SHA-256 = CPU+RRAM+CRACEN フル稼働) が
# 電源レール立ち上がりを鈍らせている仮説の切り分け用。
# 注意: この構成は検証しないので破損 app でも起動を試みる (診断専用!)
CONFIG_BOOT_VALIDATE_SLOT0=n
""" if minimal else """CONFIG_MCUBOOT_SERIAL=y
CONFIG_BOOT_SERIAL_UART=y
CONFIG_BOOT_SERIAL_MAX_RECEIVE_SIZE=1024
CONFIG_BOOT_MGMT_ECHO=y

# 壊れた / 書き込み途中のアプリイメージ -> 自動的に recovery に留まる
CONFIG_BOOT_SERIAL_NO_APPLICATION=y

# デフォルトの GPIO 入口は mcuboot-button0 alias を要求するため無効化
CONFIG_BOOT_SERIAL_ENTRANCE_GPIO=n

# 入口 1: アプリからの要求 (dfu コマンド / ボタン 4 回連打)
CONFIG_RETAINED_MEM=y
CONFIG_RETENTION=y
CONFIG_RETENTION_BOOT_MODE=y
CONFIG_BOOT_SERIAL_BOOT_MODE=y

# 入口 2 (レスキュー): 毎起動 500 ms の SMP 待機ウィンドウ。web updater が ping で捕捉
CONFIG_BOOT_SERIAL_WAIT_FOR_DFU=y
CONFIG_BOOT_SERIAL_WAIT_FOR_DFU_TIMEOUT=500

# INDICATION_LED (gpio-leds) 用
CONFIG_GPIO=y

# board.c の board_early_init_hook (電源自锁) を有効化
CONFIG_BOARD_EARLY_INIT_HOOK=y

# recovery 中は LED 点灯 (mcuboot-led0 alias は overlay で定義)
CONFIG_MCUBOOT_INDICATION_LED=y

# nRF54L15 では jump 直前の bootloader flash 保護 (fprotect) が失敗し
# 起動が中断されるため無効化 (DIY・無署名構成では保護不要)
CONFIG_FPROTECT=n

CONFIG_LOG=n
""" if not debug else """# 診断モード: serial recovery (serial_adapter) は UART console と共存不可の
# ため無効化し、起動ログのみ UART に出力する。boot-mode / retention は
# 通常構成と同じに保ち、それらの初期化も検証対象に含める。
CONFIG_RETAINED_MEM=y
CONFIG_RETENTION=y
CONFIG_RETENTION_BOOT_MODE=y
CONFIG_GPIO=y
CONFIG_FPROTECT=n

CONFIG_LOG=y
CONFIG_LOG_MODE_MINIMAL=y
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y

# board.c の board_early_init_hook (電源自锁) を有効化
CONFIG_BOARD_EARLY_INIT_HOOK=y
""")

# ---------- sysbuild/mcuboot.overlay + アプリ側 boot-mode ノード ----------
if nano and is54:
    pass  # 下の is54 分岐の後で上書きする
if is54:
    # nRF54L15: GPREGRET が無いため、boot mode は保持 SRAM 512 B に置く。
    # ファームウェア自身の保持領域 0x2003F000 の直下 (socs overlay が主 SRAM を
    # 0x3F000 に縮小済み。両イメージともさらに 0x3EE00 まで縮小する)。
    retention_nodes = """
	bootmode_sram: sram@2003ee00 {
		compatible = "zephyr,memory-region", "mmio-sram";
		reg = <0x2003ee00 0x200>;
		zephyr,memory-region = "BOOTMODE_RAM";
		status = "okay";

		retainedmem_boot: retainedmem {
			compatible = "zephyr,retained-ram";
			status = "okay";
			#address-cells = <1>;
			#size-cells = <1>;

			boot_mode_ret: retention@0 {
				compatible = "zephyr,retention";
				status = "okay";
				reg = <0x0 0x4>;
				prefix = [42 4d];
				checksum = <1>;
			};
		};
	};
"""
    mcuboot_overlay = f"""/ {{
	chosen {{
		{("zephyr,console" if (debug or minimal) else "zephyr,uart-mcumgr")} = &{uart};
{("" if minimal else chr(9)+chr(9)+"zephyr,boot-mode = &boot_mode_ret;"+chr(10))}		zephyr,flash-controller = &rram_controller;
	}};
{("" if minimal else retention_nodes)}}};

&cpuapp_sram {{
	reg = <0x20000000 0x3ee00>;
}};

&pinctrl {{
	{uart}_dfu_default: {uart}_dfu_default {{ group1 {{ psels = {psels}; }}; }};
	{uart}_dfu_sleep: {uart}_dfu_sleep {{ group1 {{ psels = {psels}; low-power-enable; }}; }};
}};

&{uart} {{
	status = "okay";
	current-speed = <115200>;
	pinctrl-0 = <&{uart}_dfu_default>;
	pinctrl-1 = <&{uart}_dfu_sleep>;
	pinctrl-names = "default", "sleep";
}};
"""
    app_append = f"""
/* mcuboot UART DFU: boot-mode retention (must match sysbuild/mcuboot.overlay) */
/ {{
	chosen {{
		zephyr,boot-mode = &boot_mode_ret;
	}};
{retention_nodes}}};

&cpuapp_sram {{
	reg = <0x20000000 0x3ee00>;
}};
"""
else:
    # nRF52840: boot mode は GPREGRET に置く (ソフトリセット後も保持、RAM 消費なし)
    mcuboot_overlay = f"""/ {{
	chosen {{
		{("zephyr,console" if (debug or minimal) else "zephyr,uart-mcumgr")} = &{uart};
{("" if minimal else chr(9)+chr(9)+"zephyr,boot-mode = &boot_mode0;"+chr(10))}		zephyr,flash-controller = &flash_controller;
	}};
}};

&gpregret1 {{
	status = "okay";
	#address-cells = <1>;
	#size-cells = <1>;

	boot_mode0: retention@0 {{
		compatible = "zephyr,retention";
		status = "okay";
		reg = <0x0 0x1>;
	}};
}};

&pinctrl {{
	{uart}_dfu_default: {uart}_dfu_default {{ group1 {{ psels = {psels}; }}; }};
	{uart}_dfu_sleep: {uart}_dfu_sleep {{ group1 {{ psels = {psels}; low-power-enable; }}; }};
}};

&{uart} {{
	status = "okay";
	current-speed = <115200>;
	pinctrl-0 = <&{uart}_dfu_default>;
	pinctrl-1 = <&{uart}_dfu_sleep>;
	pinctrl-names = "default", "sleep";
}};
"""
    app_append = """
/* mcuboot UART DFU: boot-mode retention (must match sysbuild/mcuboot.overlay) */
/ {
	chosen {
		zephyr,boot-mode = &boot_mode0;
	};
};

&gpregret1 {
	status = "okay";
	#address-cells = <1>;
	#size-cells = <1>;

	boot_mode0: retention@0 {
		compatible = "zephyr,retention";
		status = "okay";
		reg = <0x0 0x1>;
	};
};
"""

# nano: overlay を最小に置き換え (chosen flash-controller + SRAM 縮小のみ。
# pwr の zephyr,user とアプリ側 append は共通処理がこの後で足す)
if nano:
    if is54:
        mcuboot_overlay = """/ {
	chosen {
		zephyr,flash-controller = &rram_controller;
	};
};

&cpuapp_sram {
	reg = <0x20000000 0x3ee00>;
};
"""
    else:
        mcuboot_overlay = """/ {
	chosen {
		zephyr,flash-controller = &flash_controller;
	};
};
"""


# ---------- 電源自锁 (power latch): mcuboot 実行中・recovery 中も電源を保持 ----------
# 52 / 54L 共通: zephyr,user の pwr-gpios を mcuboot の DT に渡し、
# patch_mcuboot_pwr.py が mcuboot 自身の main.c に追記した EARLY init
# (電源投入後 <1ms、raw HAL) がラッチする。
# board.c (PRE_KERNEL_1 prio 40、遅い) や gpio-hog (ドライバ初期化、
# mcuboot 側で確実にリンクされる保証がない) には依存しない。
pwr = pins.get("pwr")
if pwr:
    pp = parse_pin(pwr)
    mcuboot_overlay += f"""
/ {{
	zephyr,user {{
		pwr-gpios = <&gpio{pp[0]} {pp[1]} GPIO_ACTIVE_HIGH>;
	}};
}};
"""

# minimal 診断: mcuboot の CPU を 64MHz に落とす。
# 仮説: 起動初期の消費電流が NiMH 昇圧の 3V3 立ち上がりを鈍らせ、
# VDD が 2.5V を超えるまで Q3 (2N7002) が開かず自锁が効かない。
# クロック半減で初期電流を下げ、レール立ち上がりを速くする実験。
if minimal:
    mcuboot_overlay += """
&cpu {
	clock-frequency = <64000000>;
};
"""

# ---------- LED 診断 / DFU 表示 ----------
# 診断モード: gpio-hog で GPIO 初期化直後に LED 点灯 -> 「MCUboot 生存」の可視信号。
#             点灯したまま = mcuboot で停止 / 消灯・変化 = app が引き継いだ。
# 通常モード: gpio-leds ノード + mcuboot-led0 alias -> recovery 中に LED 点灯 (DFU 表示)。
led = pins.get("led")
if led and not nano:
    lp = parse_pin(led)
    lflag = "GPIO_ACTIVE_LOW" if (cfg.get("options") or {}).get("led_polarity") == "low" else "GPIO_ACTIVE_HIGH"
    if debug or minimal:
        mcuboot_overlay += f"""
&gpio{lp[0]} {{
	status = "okay";

	mcubootled_hog: mcubootled-hog {{
		gpio-hog;
		gpios = <{lp[1]} {lflag}>;
		output-high;
	}};
}};
"""
    else:
        mcuboot_overlay += f"""
/ {{
	mcuboot_leds {{
		compatible = "gpio-leds";

		mcuboot_led0: mcuboot-led-0 {{
			gpios = <&gpio{lp[0]} {lp[1]} {lflag}>;
		}};
	}};

	aliases {{
		mcuboot-led0 = &mcuboot_led0;
	}};
}};
"""

write("sysbuild/mcuboot.overlay", mcuboot_overlay)

if custom_overlay and os.path.isfile(custom_overlay):
    with open(custom_overlay, "a", encoding="utf-8", newline="\n") as f:
        f.write(app_append)
    print(f"== appended boot-mode nodes to {custom_overlay} ==")
else:
    sys.exit("gen_mcuboot_files: custom overlay path missing; boot-mode nodes not applied")

# ---------- アプリ prj.conf ----------
with open("prj.conf", "a", encoding="utf-8", newline="\n") as f:
    f.write("\n\n# mcuboot UART DFU (bootmode_set)\n"
            "CONFIG_RETAINED_MEM=y\nCONFIG_RETENTION=y\nCONFIG_RETENTION_BOOT_MODE=y\n"
            "CONFIG_BOARD_EARLY_INIT_HOOK=y\n")
print("== appended retention Kconfigs to prj.conf ==")

# ---------- 凍結パーティションレイアウト ----------
# storage は swd_direct overlay と同一アドレス / サイズに固定。SWD 直書きファーム
# からの移行でも NVS データ (キャリブレーション / ペアリング) が失われない。
def pm_yaml(parts):
    out = []
    for name, addr, size, span in parts:
        out.append(f"{name}:")
        out.append(f"  address: {hex(addr)}")
        out.append(f"  end_address: {hex(addr + size)}")
        if span:
            anchor = f"id_{name}"
            out.append(f"  orig_span: &{anchor}")
            for s_ in span:
                out.append(f"  - {s_}")
            out.append("  region: flash_primary")
            out.append(f"  size: {hex(size)}")
            out.append(f"  span: *{anchor}")
        else:
            out.append("  region: flash_primary")
            out.append(f"  size: {hex(size)}")
    return "\n".join(out) + "\n"

if is54:
    # nRF54L15: 1524 KB RRAM (0x0 - 0x17D000)
    parts = [
        ("mcuboot",             0x0,      0x10000,  None),
        ("mcuboot_pad",         0x10000,  0x800,    None),
        ("app",                 0x10800,  0x14B800, None),
        ("mcuboot_primary",     0x10000,  0x14C000, ["mcuboot_pad", "app"]),
        ("mcuboot_primary_app", 0x10800,  0x14B800, ["app"]),
        ("storage",             0x15C000, 0x9000,   None),
        ("EMPTY_0",             0x165000, 0x18000,  None),
    ]
else:
    # nRF52840: 1 MB flash
    parts = [
        ("mcuboot",             0x0,      0xC000,   None),
        ("mcuboot_pad",         0xC000,   0x200,    None),
        ("app",                 0xC200,   0xDFE00,  None),
        ("mcuboot_primary",     0xC000,   0xE0000,  ["mcuboot_pad", "app"]),
        ("mcuboot_primary_app", 0xC200,   0xDFE00,  ["app"]),
        ("storage",             0xEC000,  0x8000,   None),
        ("EMPTY_0",             0xF4000,  0xC000,   None),
    ]

# ファイル名はリポジトリ自身の sysbuild.cmake の pm_static 探索規則に合わせる:
#   pm_static/pm_static_<BOARD>_<QUALIFIERS の / を _ に置換>.yml
seg = board.split("/")
pm_name = "pm_static_" + "_".join(seg) + ".yml"
pm_path = os.path.join("pm_static", pm_name)
if os.path.exists(pm_path):
    print(f"== {pm_path} already exists in firmware repo, keeping it (frozen layout) ==")
else:
    write(pm_path, pm_yaml(parts))

print("gen_mcuboot_files: done")
