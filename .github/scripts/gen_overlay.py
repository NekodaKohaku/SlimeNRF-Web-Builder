#!/usr/bin/env python3
import json
import re
import sys


def parse_pin(p):
    m = re.fullmatch(r"P(\d)\.(\d+)", (p or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def psel(func, p):
    q = parse_pin(p)
    return f"NRF_PSEL({func}, {q[0]}, {q[1]})" if q else None


def gpio(p, flags):
    q = parse_pin(p)
    return f"<&gpio{q[0]} {q[1]} {flags}>" if q else None


def main():
    cfg = json.loads(sys.argv[1])
    bus = cfg.get("bus", "spi")
    pins = cfg.get("pins", {}) or {}
    imu = cfg.get("imu", "?")
    mag = cfg.get("mag", "none")

    def need(key, human):
        if not parse_pin(pins.get(key)):
            sys.exit(f"missing or invalid pin: {human} ({key}) = {pins.get(key)!r}")

    L = []
    L.append("&pinctrl {")
    if bus == "i2c":
        need("sda", "IMU SDA"); need("scl", "IMU SCL")
        grp = f"<{psel('TWIM_SDA', pins['sda'])}>, <{psel('TWIM_SCL', pins['scl'])}>"
        L.append(f"\ti2c0_default {{ group1 {{ psels = {grp}; bias-disable; }}; }};")
        L.append(f"\ti2c0_sleep  {{ group1 {{ psels = {grp}; bias-disable; low-power-enable; }}; }};")
    else:
        for k, h in [("sck", "SCK"), ("mosi", "MOSI"), ("miso", "MISO")]:
            need(k, "IMU " + h)
        grp = (f"<{psel('SPIM_MISO', pins['miso'])}>, "
               f"<{psel('SPIM_MOSI', pins['mosi'])}>, "
               f"<{psel('SPIM_SCK', pins['sck'])}>")
        L.append(f"\tspi3_default {{ group1 {{ psels = {grp}; }}; }};")
        L.append(f"\tspi3_sleep  {{ group1 {{ psels = {grp}; low-power-enable; }}; }};")
    if pins.get("led"):
        need("led", "LED")
        L.append(f"\tpwm0_default {{ group1 {{ psels = <{psel('PWM_OUT0', pins['led'])}>; "
                 f"nordic,drive-mode = <NRF_DRIVE_D0S1>; }}; }};")
        L.append(f"\tpwm0_sleep  {{ group1 {{ psels = <{psel('PWM_OUT0', pins['led'])}>; low-power-enable; }}; }};")
    L.append("};")

    if bus == "spi":
        need("cs", "IMU CS")
        L.append(f"&spi3 {{ cs-gpios = {gpio(pins['cs'], 'GPIO_ACTIVE_LOW')}; }};")

    need("int", "IMU INT")
    L.append("/ {")
    L.append("\tzephyr,user {")
    L.append(f"\t\tint0-gpios = {gpio(pins['int'], '0')};")
    if pins.get("led"):
        L.append(f"\t\tled-gpios = {gpio(pins['led'], 'GPIO_OPEN_SOURCE')};")
    if pins.get("clk"):
        L.append(f"\t\tclk-gpios = {gpio(pins['clk'], 'GPIO_OPEN_DRAIN')};")
    if pins.get("vcc"):
        L.append(f"\t\tvcc-gpios = {gpio(pins['vcc'], '0')};")
    L.append("\t};")
    if pins.get("sw0") and parse_pin(pins["sw0"]):
        L.append("\taliases { sw0 = &button0; };")
    L.append("};")
    if pins.get("sw0") and parse_pin(pins["sw0"]):
        q = parse_pin(pins["sw0"])
        L.append(f"&button0 {{ gpios = <&gpio{q[0]} {q[1]} (GPIO_PULL_UP | GPIO_ACTIVE_LOW)>; }};")

    print("\n".join(L))


if __name__ == "__main__":
    main()
