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
"""CONFIG_MCUBOOT_SERIAL=y
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

# gpio-hog (電源自锁) 用
CONFIG_GPIO=y

CONFIG_LOG=n
""")

# ---------- sysbuild/mcuboot.overlay + アプリ側 boot-mode ノード ----------
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
		zephyr,uart-mcumgr = &{uart};
		zephyr,boot-mode = &boot_mode_ret;
		zephyr,flash-controller = &rram_controller;
	}};
{retention_nodes}}};

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
		zephyr,uart-mcumgr = &{uart};
		zephyr,boot-mode = &boot_mode0;
		zephyr,flash-controller = &flash_controller;
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

# ---------- 電源自锁 (power latch): mcuboot 実行中・recovery 中も電源を保持 ----------
# アプリ側のラッチは app 起動後にしか効かないため、mcuboot にも同じピンを渡す。
# 54L: test54l board.c (全イメージ共通) が zephyr,user の pwr-gpios を PRE_KERNEL_1 の
#      raw HAL でラッチする -> DT を与えるだけでよい。
# 52:  gpio-hog で GPIO ドライバ初期化時 (PRE_KERNEL_1) に自動的に high を駆動。
pwr = pins.get("pwr")
if pwr:
    pp = parse_pin(pwr)
    if is54:
        mcuboot_overlay += f"""
/ {{
	zephyr,user {{
		pwr-gpios = <&gpio{pp[0]} {pp[1]} GPIO_ACTIVE_HIGH>;
	}};
}};
"""
    else:
        mcuboot_overlay += f"""
&gpio{pp[0]} {{
	status = "okay";

	pwrhold_hog: pwrhold-hog {{
		gpio-hog;
		gpios = <{pp[1]} GPIO_ACTIVE_HIGH>;
		output-high;
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
            "CONFIG_RETAINED_MEM=y\nCONFIG_RETENTION=y\nCONFIG_RETENTION_BOOT_MODE=y\n")
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
