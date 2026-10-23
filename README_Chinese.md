<p align="left">
  <img src="icon.png" alt="Taiwan Work and School Suspension Logo" width="140">
</p>

# 台灣停班停課 – Home Assistant 自訂整合

[English](README.md) | 繁體中文

從 **行政院人事行政總處（DGPA）**「[天然災害停止上班及上課情形](https://www.dgpa.gov.tw/typh/daily/nds.html)」網頁抓取最新公告，為每個你關注的地點（縣市或縣市＋行政區）建立一個 `binary_sensor`，方便在颱風、豪雨期間做自動化通知。

| 項目 | 內容 |
| --- | --- |
| Domain | `tw_suspension` |
| 整合類型 | `service`（雲端輪詢 `cloud_polling`） |
| 平台 | `binary_sensor` |
| 最低 HA 版本 | 2024.11.0 |
| 相依套件 | `beautifulsoup4>=4.12.0`（HA 會自動安裝） |
| 版本 | 0.1.0 |

---

## 功能特色

- **一個地點一個感測器**：可針對整個縣市，或縣市底下特定行政區建立感測器。
- **下拉選單選地點**：縣市／行政區清單即時取自 **國土測繪中心（NLSC）代碼服務 API**；API 失敗時自動切換為手動輸入。
- **智慧比對**：自動統一「台／臺」寫法；指定行政區但公告只到縣市層級時，會自動退回使用縣市或「其他地區」的公告。
- **部分時段判斷**：公告中含「上午、下午、晚上、夜間、中午、X 時、HH:MM」等字樣時，`partial` 屬性會標記為 `true`。
- **共用快取**：多個地點共用同一份網頁資料（快取 60 秒），避免重複請求政府網站。
- **斷線容錯**：更新失敗時保留上次已知狀態，不會立刻變成「無法使用」。
- **可調整更新頻率與 SSL 驗證**：透過整合的「選項」設定，變更後自動重新載入。
- **中英文介面**：內建 `zh-Hant` 與 `en` 翻譯。

---

## 安裝

### 方式一：HACS（建議）

1. HACS → 右上角「⋮」→「自訂儲存庫」。
2. 貼上本專案的 repo URL，類別選 **Integration**。
3. 搜尋「Taiwan Work and School Suspension」並下載。
4. 重新啟動 Home Assistant。

### 方式二：手動安裝

1. 將 `custom_components/tw_suspension` 整個資料夾複製到 HA 的 `/config/custom_components/`。
2. 重新啟動 Home Assistant。

---

## 設定

到「**設定 → 裝置與服務 → 新增整合**」搜尋「**Taiwan Work and School Suspension**」。

### 設定流程

```mermaid
flowchart TD
    A["步驟 1：選擇縣市"] -->|NLSC 取得成功| B["步驟 2：選擇行政區"]
    A -->|NLSC 失敗| M["手動輸入縣市／行政區"]
    B -->|NLSC 失敗| M
    B --> C["建立條目"]
    M --> C
```

1. **選擇縣市**：下拉選單列出全台縣市。
2. **選擇行政區**：
   - 選「**整個縣市**」：看縣市整體公告（詳見下方判斷邏輯）。
   - 選特定行政區：只看該區的公告。
3. **手動輸入（備援）**：若 NLSC 清單無法取得，會顯示錯誤原因並讓你手動輸入。名稱需與 DGPA 網頁一致，行政區可留空。

> [!NOTE]
> - 每新增一個地點，就再新增一次整合。
> - 同一個「縣市＋行政區」組合只能設定一次（unique ID 為 `縣市|行政區`），重複設定會顯示「此地點已設定過」。
> - 條目名稱為「縣市＋行政區」，例如 `臺北市`、`新北市板橋區`。

### 選項（設定完成後調整）

在整合卡片點「**設定**」：

| 選項 | 預設值 | 範圍 | 說明 |
| --- | --- | --- | --- |
| 更新間隔（分鐘） `scan_interval` | `30` | 10 – 1440 | 多久向 DGPA 抓一次資料 |
| 驗證 SSL 憑證 `verify_ssl` | `false` | 開／關 | DGPA 網站憑證缺少 Subject Key Identifier，嚴格驗證會失敗，因此預設關閉 |

儲存後整合會自動重新載入以套用設定。

---

## 實體說明

每個條目會建立一個裝置（類型為「服務」，製造商標示為「行政院人事行政總處 (DGPA)」）以及一個二元感測器。

- **實體名稱**：`停班停課`（英文介面為 `Work/class suspension`）
- **實體 ID 範例**：`binary_sensor.臺北市_ting_ban_ting_ke`（實際 ID 依 HA 產生規則而定，請至實體列表確認）

### 狀態

| 狀態 | 條件 | 圖示 |
| --- | --- | --- |
| `on` | `work_stopped` **或** `class_stopped` 為 `true` | `mdi:cloud-alert` |
| `off` | 無停班也無停課 | `mdi:cloud` |
| `unavailable` | 從未成功取得過資料 | — |

### 屬性

| 屬性 | 型別 | 說明 |
| --- | --- | --- |
| `work_stopped` | bool | 公告文字含「停止上班」 |
| `class_stopped` | bool | 公告文字含「停止上課」 |
| `partial` | bool | 有停班／停課且只限部分時段（如「下午停止上班」）；整縣市彙整模式下有任一區停班停課即為 `true` |
| `raw` | str | 對應到的原始公告文字 |
| `city` | str | 設定的縣市（已統一為「臺」） |
| `district` | str | 設定的行政區（整個縣市時為空字串） |
| `last_updated` | str | 最後成功更新時間（ISO 8601，含時區，精確到秒） |

---

## 運作原理

```mermaid
flowchart LR
    DGPA["DGPA 網頁 nds.html"] --> Client["DgpaClient 共用快取 60 秒"]
    Client --> Parser["parse_page 解析成 縣市→公告"]
    Parser --> Eval["evaluate 依縣市／行政區判斷"]
    Eval --> Coord["WorkClassCoordinator"]
    Coord --> Sensor["binary_sensor"]
```

### 1. 抓取網頁（[api.py](custom_components/tw_suspension/api.py)）

- 以 `aiohttp` 抓取 DGPA 網頁，逾時 10 秒。
- 先以 UTF-8 解碼，失敗則改用 Big5。
- 所有條目共用同一個 `DgpaClient`（依 `verify_ssl` 設定區分），並以鎖＋60 秒快取避免同時重複抓取。
- 網頁抓取失敗或解析不到任何縣市時拋出 `DgpaError`，由協調器轉為 `UpdateFailed`。

### 2. 解析網頁（[parser.py](custom_components/tw_suspension/parser.py)）

- 將網頁轉純文字後逐行掃描，辨識以縣市名稱開頭的行（可帶「北部地區／中部地區…」前綴），遇到「備註」、「語音查詢電話」等字樣即停止。
- 每個縣市的公告會解析成兩種格式之一：
  - **字串**：整個縣市同一則公告，例如 `"今天停止上班、停止上課"`。
  - **字典**：分區公告，例如 `{"板橋區": "今天停止上班", "其他地區": "照常上班"}`。

### 3. 判斷邏輯（`evaluate`）

| 情境 | 判斷方式 |
| --- | --- |
| 網頁上找不到該縣市 | 視為正常上班上課（`off`） |
| 縣市公告為單一字串 | 直接使用該公告 |
| **有指定行政區** | 依序尋找：該行政區 → 縣市整體 → 「其他地區」；都沒有則 `off` |
| **整個縣市**，且有縣市整體公告 | 使用縣市整體公告 |
| **整個縣市**，只有分區公告 | 排除「其他地區」後，**任一區**停班／停課即為 `on`，`partial` 為 `true`，`raw` 會列出所有分區 |

### 4. 縣市／行政區清單

- 縣市：`https://api.nlsc.gov.tw/other/ListCounty`
- 行政區：`https://api.nlsc.gov.tw/other/ListTown1/{縣市代碼}`
- 政府網站常缺中繼憑證，因此先以 SSL 驗證連線，失敗再以不驗證方式重試（僅讀取公開清單）。

---

## 自動化範例

### 停班停課公告時推播通知

```yaml
automation:
  - alias: 停班停課通知
    trigger:
      - platform: state
        entity_id: binary_sensor.xxx_ting_ban_ting_ke
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "停班停課公告"
          message: >
            {{ state_attr(trigger.entity_id, 'city') }}{{ state_attr(trigger.entity_id, 'district') }}：
            {{ state_attr(trigger.entity_id, 'raw') }}
```

### 只在「停課」時觸發

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.xxx_ting_ban_ting_ke
    attribute: class_stopped
    to: true
```

### 範本：區分全天或部分時段

```yaml
{% if is_state('binary_sensor.xxx_ting_ban_ting_ke', 'on') %}
  {{ '部分時段停班停課' if state_attr('binary_sensor.xxx_ting_ban_ting_ke', 'partial') else '全天停班停課' }}
{% else %}
  正常上班上課
{% endif %}
```

---

## 疑難排解

| 現象 | 可能原因與處理 |
| --- | --- |
| 新增整合時直接跳到「手動輸入」 | NLSC API 無法連線，畫面上會顯示錯誤原因；手動輸入與 DGPA 網頁一致的名稱即可 |
| 整合顯示「重試設定中」 | 第一次抓取 DGPA 失敗，HA 會自動重試；請確認 HA 可連到 `www.dgpa.gov.tw` |
| 開啟 SSL 驗證後連線失敗 | DGPA 憑證問題，請在選項中關閉「驗證 SSL 憑證」 |
| 日誌出現「解析不到任何縣市資料」 | DGPA 網頁格式可能已變更，請回報 issue |
| 平常狀態都是 `off`、`raw` 為空 | 正常現象：無天然災害時網頁上沒有該縣市公告 |

開啟除錯日誌：

```yaml
logger:
  default: warning
  logs:
    custom_components.tw_suspension: debug
```

---

## 專案結構

```text
custom_components/tw_suspension/
├── __init__.py        # 進入點：建立共用 client 與協調器、轉送平台、選項變更時重新載入
├── api.py             # DGPA 網頁抓取（含快取）與 NLSC 縣市／行政區清單
├── binary_sensor.py   # 停班停課二元感測器
├── config_flow.py     # 設定流程（縣市 → 行政區 / 手動輸入）與選項流程
├── const.py           # 常數：網址、預設值、設定鍵
├── coordinator.py     # DataUpdateCoordinator：定期更新並判斷單一地點
├── parser.py          # 純解析函式（不依賴 HA，方便單元測試）
├── manifest.json
└── translations/
    ├── en.json
    └── zh-Hant.json
hacs.json
```

---

## 免責聲明

本整合僅解析 DGPA 公開網頁，資料可能因網頁格式變更或網路問題而延遲或不正確。**實際停班停課請以行政院人事行政總處及各縣市政府正式公告為準。**
