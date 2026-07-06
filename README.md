# SlimeNRF Firmware Builder

[![Open SlimeNRF Firmware Builder](https://img.shields.io/badge/Open-SlimeNRF%20Firmware%20Builder-blue?style=for-the-badge)](https://nekodakohaku.github.io/SlimeNRF-Web-Builder/)

[日本語](#日本語) | [English](#english) | [中文](#中文)

---

## 日本語

### SlimeVR nRF ファームウェアを、ブラウザだけで生成

**SlimeNRF Firmware Builder** は、SlimeVR nRF トラッカー / レシーバー用のファームウェアをオンラインで生成できる Web ツールです。

ローカルに開発環境を構築したり、ソースコードを編集したりする必要はありません。
使用するモジュール、センサー、通信バス、ピン設定を選択するだけで、クラウド上でファームウェアをビルドし、完成した `.hex` ファイルをダウンロードできます。

[SlimeNRF Firmware Builder を開く](https://nekodakohaku.github.io/SlimeNRF-Web-Builder/)

---

### できること

* SlimeVR nRF トラッカー用ファームウェアの生成
* SlimeVR nRF レシーバー用ファームウェアの生成
* モジュール、IMU、地磁気センサー、通信バスの選択
* SPI / I2C 構成の設定
* 必須ピンと任意ピンの割り当て
* バッテリー、スリープ、LED 極性、出力形式の設定
* 生成された `.hex` ファイルのダウンロード
* 同一設定または互換設定のビルド結果キャッシュ

---

### 使い方

1. Web Builder を開きます。
2. デバイス種別を選択します。

   * Tracker
   * Receiver
3. 使用するモジュールを選択します。
4. IMU、地磁気センサー、通信バスを設定します。
5. 必要なピンを割り当てます。

   * 必須項目には一般的な初期値が入っています。
   * 任意項目は空欄のままでも問題ありません。
   * ボタン、UART、電源ラッチなどは、必要な場合のみ設定してください。
6. バッテリー、スリープ、出力形式、LED 極性を確認します。
7. **ファームを生成** を押します。
8. ビルド完了後、`.hex` ファイルをダウンロードします。
9. SWD を使用して、ファームウェアをボードへ書き込みます。

---

### ビルドについて

ファームウェアのビルドはクラウド上で実行されます。
すでに誰かが互換性のあるバージョンで同じ設定のファームウェアを生成していた場合、システムはキャッシュ済みの `.hex` ファイルを直接返します。
そのため、再コンパイルを待つ必要がなく、すぐにダウンロードできます。

---

### 注意事項

このプロジェクトは現在テスト中です。
環境や設定によっては、予期しない失敗が発生する場合があります。

ビルドに失敗した場合や問題を見つけた場合は、[GitHub Issues](../../issues) で報告してください。

---

## English

### Generate SlimeVR nRF firmware directly in your browser

**SlimeNRF Firmware Builder** is a web-based tool for generating firmware for SlimeVR nRF trackers and receivers.

You do not need to install a local toolchain, edit source code, or set up a development environment.
Choose your module, sensors, bus type, and pin configuration, then let the cloud build the firmware for you. When the build is complete, you can download the generated `.hex` file and flash it to your board.

[Open SlimeNRF Firmware Builder](https://nekodakohaku.github.io/SlimeNRF-Web-Builder/)

---

### Features

* Generate firmware for SlimeVR nRF trackers
* Generate firmware for SlimeVR nRF receivers
* Select module, IMU, magnetometer, and bus type
* Configure SPI or I2C
* Assign required and optional pins
* Configure battery, sleep, LED polarity, and output format
* Download the generated `.hex` firmware file
* Reuse cached builds for identical or compatible configurations

---

### How to use

1. Open the Web Builder.
2. Select the device type.

   * Tracker
   * Receiver
3. Choose your module.
4. Select the IMU, magnetometer, and bus type.
5. Assign the required pins.

   * Common default values are pre-filled.
   * Optional fields can be left empty.
   * Button, UART, power-hold, and other optional pins only need to be configured if your hardware uses them.
6. Review the battery, sleep, output format, and LED polarity settings.
7. Click **Build firmware**.
8. When the build is complete, download the `.hex` file.
9. Flash the firmware to your board using SWD.

---

### Build behavior

Firmware builds are handled in the cloud.
If someone has already generated firmware with the same configuration on a compatible version, the system will return the cached `.hex` file directly.
This avoids recompiling and allows the file to be downloaded immediately.

---

### Notes

This project is currently under testing.
Unexpected failures may occur depending on the environment or configuration.

If a build fails or you find a problem, please report it in [GitHub Issues](../../issues).

---

## 中文

### 直接在瀏覽器產生 SlimeVR nRF 固件

**SlimeNRF Firmware Builder** 是一個用來產生 SlimeVR nRF 追蹤器 / 接收器固件的線上工具。

你不需要安裝開發環境，也不需要修改原始碼。
只要選擇模組、感測器、匯流排與腳位設定，系統就會在雲端幫你編譯固件。建置完成後，可以直接下載產生好的 `.hex` 檔案，並燒錄到你的板子。

[開啟 SlimeNRF Firmware Builder](https://nekodakohaku.github.io/SlimeNRF-Web-Builder/)

---

### 功能

* 產生 SlimeVR nRF 追蹤器固件
* 產生 SlimeVR nRF 接收器固件
* 選擇模組、IMU、磁力計與匯流排類型
* 設定 SPI 或 I2C
* 指定必填與選填腳位
* 設定電池、睡眠、LED 極性與輸出格式
* 下載產生好的 `.hex` 固件檔案
* 相同或相容設定可直接使用快取結果，避免重複編譯

---

### 使用方式

1. 開啟 Web Builder。
2. 選擇裝置類型。

   * Tracker
   * Receiver
3. 選擇使用的模組。
4. 選擇 IMU、磁力計與匯流排類型。
5. 指定需要的腳位。

   * 必填項目已預先帶入常見預設值。
   * 選填項目可以留白。
   * 按鈕、UART、電源自鎖等功能，只有在硬體需要時才需要設定。
6. 確認電池、睡眠、輸出格式與 LED 極性設定。
7. 按下 **產生固件**。
8. 建置完成後，下載 `.hex` 檔案。
9. 使用 SWD 將固件燒錄到板子。

---

### 建置機制

固件會在雲端進行編譯。
如果已經有人製作過相容版本，且使用相同設定產生過固件，系統會直接回傳已快取的 `.hex` 固件檔案。
這樣就不需要重新編譯，可以立即下載。

---

### 注意事項

此專案目前仍在測試中。
依照不同環境與設定，可能會發生不預期的失敗。

如果建置失敗，或發現任何問題，請在 [GitHub Issues](../../issues) 中回報。
