#!/usr/bin/env python3
import json
import re
import sys

AIN_NRF52 = {"P0.02": 0, "P0.03": 1, "P0.04": 2, "P0.05": 3,
             "P0.28": 4, "P0.29": 5, "P0.30": 6, "P0.31": 7}

AIN_NRF54L = {"P1.04": 0, "P1.05": 1, "P1.06": 2, "P1.07": 3,
              "P1.11": 4, "P1.12": 5, "P1.13": 6, "P1.14": 7}


def parse_pin(p):
    m = re.fullmatch(r"P(\d)\.(\d+)", (p or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def psel(func, p):
    q = parse_pin(p)
    return f"NRF_PSEL({func}, {q[0]}, {q[1]})" if q else None


def gpio(p, flags):
    q = parse_pin(p)
    return f"<&gpio{q[0]} {q[1]} {flags}>" if q else None


def need(pins, key, human):
    if not parse_pin(pins.get(key)):
        sys.exit(f"missing or invalid pin: {human} ({key}) = {pins.get(key)!r}")


def battery_divider(opts, ain_map):
    if (opts or {}).get("adc") != "external":
        return []
    pin = opts.get("adc_pin")
    if pin not in ain_map:
        return []
    ain = ain_map[pin]
    r1 = int(opts.get("adc_r1", 0) or 0) * 1000
    r2 = int(opts.get("adc_r2", 0) or 0) * 1000
    if r2 > 0:
        output, full = r2, r1 + r2
    else:
        output, full = 1, 1
    return [
        "\tbattery-divider {",
        f"\t\tio-channels = <&adc {ain}>;",
        f"\t\toutput-ohms = <{output}>;",
        f"\t\tfull-ohms = <{full}>;",
        "\t};",
    ]


MAG_I2C_DEV = '{ compatible = "i2c-device"; label = "mag"; reg = <0>; }'
MAG_SPI_DEV = '{ compatible = "vnd,spi-device"; spi-max-frequency = <DT_FREQ_M(8)>; label = "mag-spi"; reg = <1>; }'


def mag_device_nodes(mcu, pins, mc):
    if mcu == "nrf54l15":
        imu_i2c, imu_spi, sep_i2c = "i2c21", "spi20", "i2c22"
    else:
        imu_i2c, imu_spi, sep_i2c = "i2c0", "spi3", "i2c1"
    L = []
    if mc == "i2c_shared":
        L.append(f"&{imu_i2c} {{ mag: mag@0 {MAG_I2C_DEV}; }};")
    elif mc == "i2c" and pins.get("mag_sda") and pins.get("mag_scl"):
        L.append(f'&{sep_i2c} {{ status = "okay"; pinctrl-0 = <&{sep_i2c}_default>; pinctrl-1 = <&{sep_i2c}_sleep>; pinctrl-names = "default", "sleep"; mag: mag@0 {MAG_I2C_DEV}; }};')
    elif mc == "spi" and pins.get("mag_cs"):
        L.append(f"&{imu_spi} {{ mag_spi: mag_spi@1 {MAG_SPI_DEV}; }};")
    return L


def build_nrf52(bus, pins, opts):
    mc = (opts or {}).get("mag_conn", "none")
    L = ["&pinctrl {"]
    if bus == "i2c":
        need(pins, "sda", "IMU SDA"); need(pins, "scl", "IMU SCL")
        grp = f"<{psel('TWIM_SDA', pins['sda'])}>, <{psel('TWIM_SCL', pins['scl'])}>"
        L.append(f"\ti2c0_default {{ group1 {{ psels = {grp}; bias-disable; }}; }};")
        L.append(f"\ti2c0_sleep  {{ group1 {{ psels = {grp}; bias-disable; low-power-enable; }}; }};")
    else:
        for k, h in [("sck", "SCK"), ("mosi", "MOSI"), ("miso", "MISO")]:
            need(pins, k, "IMU " + h)
        grp = (f"<{psel('SPIM_MISO', pins['miso'])}>, "
               f"<{psel('SPIM_MOSI', pins['mosi'])}>, "
               f"<{psel('SPIM_SCK', pins['sck'])}>")
        L.append(f"\tspi3_default {{ group1 {{ psels = {grp}; }}; }};")
        L.append(f"\tspi3_sleep  {{ group1 {{ psels = {grp}; low-power-enable; }}; }};")
    if pins.get("led"):
        need(pins, "led", "LED")
        L.append(f"\tpwm0_default {{ group1 {{ psels = <{psel('PWM_OUT0', pins['led'])}>; "
                 f"nordic,drive-mode = <NRF_DRIVE_D0S1>; }}; }};")
        L.append(f"\tpwm0_sleep  {{ group1 {{ psels = <{psel('PWM_OUT0', pins['led'])}>; low-power-enable; }}; }};")
    if pins.get("tx") and pins.get("rx"):
        ugrp = f"<{psel('UART_TX', pins['tx'])}>, <{psel('UART_RX', pins['rx'])}>"
        L.append(f"\tuart0_default {{ group1 {{ psels = {ugrp}; }}; }};")
        L.append(f"\tuart0_sleep  {{ group1 {{ psels = {ugrp}; low-power-enable; }}; }};")
    if mc == "i2c" and pins.get("mag_sda") and pins.get("mag_scl"):
        mgrp = f"<{psel('TWIM_SDA', pins['mag_sda'])}>, <{psel('TWIM_SCL', pins['mag_scl'])}>"
        L.append(f"\ti2c1_default {{ group1 {{ psels = {mgrp}; bias-disable; }}; }};")
        L.append(f"\ti2c1_sleep  {{ group1 {{ psels = {mgrp}; bias-disable; low-power-enable; }}; }};")
    L.append("};")
    if bus == "spi":
        need(pins, "cs", "IMU CS")
        cs = gpio(pins['cs'], 'GPIO_ACTIVE_LOW')
        if mc == "spi" and pins.get("mag_cs"):
            cs += f", {gpio(pins['mag_cs'], 'GPIO_ACTIVE_LOW')}"
        L.append(f"&spi3 {{ cs-gpios = {cs}; }};")
    if pins.get("tx") and pins.get("rx"):
        L.append('&uart0 { status = "okay"; pinctrl-0 = <&uart0_default>; pinctrl-1 = <&uart0_sleep>; pinctrl-names = "default", "sleep"; current-speed = <115200>; };')
    need(pins, "int", "IMU INT")
    L.append("/ {")
    if pins.get("tx") and pins.get("rx"):
        L.append("\tchosen { zephyr,console = &uart0; zephyr,shell-uart = &uart0; };")
    L.append("\tzephyr,user {")
    L.append(f"\t\tint0-gpios = {gpio(pins['int'], '0')};")
    if pins.get("led"):
        led_flag = "GPIO_OPEN_DRAIN" if (opts or {}).get("led_polarity") == "low" else "GPIO_OPEN_SOURCE"
        L.append(f"\t\tled-gpios = {gpio(pins['led'], led_flag)};")
    if pins.get("clk"):
        L.append(f"\t\tclk-gpios = {gpio(pins['clk'], 'GPIO_OPEN_DRAIN')};")
    if pins.get("vcc"):
        L.append(f"\t\tvcc-gpios = {gpio(pins['vcc'], '0')};")
    if pins.get("pwr"):
        L.append(f"\t\tpwr-gpios = {gpio(pins['pwr'], 'GPIO_ACTIVE_HIGH')};")
    L.append("\t};")
    if pins.get("sw0") and parse_pin(pins["sw0"]):
        L.append("\taliases { sw0 = &button0; };")
    L += battery_divider(opts, AIN_NRF52)
    L.append("};")
    if pins.get("sw0") and parse_pin(pins["sw0"]):
        q = parse_pin(pins["sw0"])
        L.append(f"&button0 {{ gpios = <&gpio{q[0]} {q[1]} (GPIO_PULL_UP | GPIO_ACTIVE_LOW)>; }};")
    if pins.get("led") and (opts or {}).get("led_polarity") == "low":
        L.append("&pwm_led0 { pwms = <&pwm0 0 PWM_MSEC(1) PWM_POLARITY_INVERTED>; };")
    L += mag_device_nodes("nrf52", pins, mc)
    return L


def build_nrf54l(bus, pins, opts):
    mc = (opts or {}).get("mag_conn", "none")
    L = ["&pinctrl {"]
    txq = parse_pin(pins.get("tx"))
    uart_node = "uart30" if (txq and txq[0] == 0) else "uart22"
    if bus == "i2c":
        need(pins, "sda", "IMU SDA"); need(pins, "scl", "IMU SCL")
        grp = f"<{psel('TWIM_SDA', pins['sda'])}>, <{psel('TWIM_SCL', pins['scl'])}>"
        L.append(f"\ti2c0_default {{ group1 {{ psels = {grp}; bias-disable; }}; }};")
        L.append(f"\ti2c0_sleep  {{ group1 {{ psels = {grp}; bias-disable; low-power-enable; }}; }};")
    else:
        for k, h in [("sck", "SCK"), ("mosi", "MOSI"), ("miso", "MISO")]:
            need(pins, k, "IMU " + h)
        grp = (f"<{psel('SPIM_SCK', pins['sck'])}>, "
               f"<{psel('SPIM_MOSI', pins['mosi'])}>, "
               f"<{psel('SPIM_MISO', pins['miso'])}>")
        L.append(f"\tspi00_default {{ group1 {{ psels = {grp}; }}; }};")
        L.append(f"\tspi00_sleep  {{ group1 {{ psels = {grp}; low-power-enable; }}; }};")
    if pins.get("tx") and pins.get("rx"):
        ugrp = f"<{psel('UART_TX', pins['tx'])}>, <{psel('UART_RX', pins['rx'])}>"
        L.append(f"\t{uart_node}_default {{ group1 {{ psels = {ugrp}; }}; }};")
        L.append(f"\t{uart_node}_sleep  {{ group1 {{ psels = {ugrp}; low-power-enable; }}; }};")
    if mc == "i2c" and bus == "spi" and pins.get("mag_sda") and pins.get("mag_scl"):
        mgrp = f"<{psel('TWIM_SDA', pins['mag_sda'])}>, <{psel('TWIM_SCL', pins['mag_scl'])}>"
        L.append(f"\ti2c0_default {{ group1 {{ psels = {mgrp}; bias-disable; }}; }};")
        L.append(f"\ti2c0_sleep  {{ group1 {{ psels = {mgrp}; bias-disable; low-power-enable; }}; }};")
    L.append("};")
    if bus == "spi":
        need(pins, "cs", "IMU CS")
        cs = gpio(pins['cs'], 'GPIO_ACTIVE_LOW')
        if mc == "spi" and pins.get("mag_cs"):
            cs += f", {gpio(pins['mag_cs'], 'GPIO_ACTIVE_LOW')}"
        L.append(f"&spi20 {{ cs-gpios = {cs}; }};")
    if mc in ("i2c", "i2c_shared"):
        L.append('&i2c21 { status = "okay"; };')
    if mc == "spi" and pins.get("mag_cs"):
        L.append(f"&spi20 {{ mag_spi: mag_spi@1 {MAG_SPI_DEV}; }};")
    if pins.get("tx") and pins.get("rx"):
        L.append(f'&{uart_node} {{ status = "okay"; pinctrl-0 = <&{uart_node}_default>; pinctrl-1 = <&{uart_node}_sleep>; pinctrl-names = "default", "sleep"; current-speed = <115200>; }};')
    need(pins, "int", "IMU INT")
    ports = set()
    for key in ("int", "cs", "pwr", "tx", "rx"):
        q = parse_pin(pins.get(key))
        if q:
            ports.add(q[0])
    gpiote_for = {0: 30, 1: 20, 2: 20}
    for p in sorted(ports):
        L.append(f'&gpio{p} {{ status = "okay"; }};')
    for g in sorted({gpiote_for.get(p, 20) for p in ports}):
        L.append(f'&gpiote{g} {{ status = "okay"; }};')
    for n in ("dppic10", "ppib11", "ppib21", "dppic20", "ppib22", "ppib30", "dppic30"):
        L.append(f'&{n} {{ status = "okay"; }};')
    if (opts or {}).get("adc") == "external" and (opts or {}).get("adc_pin") in AIN_NRF54L:
        L.append('&adc { status = "okay"; };')
    L.append("/ {")
    if pins.get("tx") and pins.get("rx"):
        L.append(f"\tchosen {{ zephyr,console = &{uart_node}; zephyr,shell-uart = &{uart_node}; }};")
    L.append("\tzephyr,user {")
    L.append(f"\t\tint0-gpios = {gpio(pins['int'], '0')};")
    if pins.get("pwr"):
        L.append(f"\t\tpwr-gpios = {gpio(pins['pwr'], 'GPIO_ACTIVE_HIGH')};")
    L.append("\t};")
    L += battery_divider(opts, AIN_NRF54L)
    L.append("};")
    return L


def main():
    cfg = json.loads(sys.argv[1])
    mcu = cfg.get("mcu", "nrf52840")
    bus = cfg.get("bus", "spi")
    pins = cfg.get("pins", {}) or {}
    opts = cfg.get("options", {}) or {}
    if mcu == "nrf54l15":
        L = build_nrf54l(bus, pins, opts)
    else:
        L = build_nrf52(bus, pins, opts)
    print("\n".join(L))


if __name__ == "__main__":
    main()
