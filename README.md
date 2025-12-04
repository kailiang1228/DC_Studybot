# Discord Study Bot (DC_StudyBot)

這是一個專注於「語音頻道讀書計時」的 Discord 機器人。它會自動記錄使用者在語音頻道的時間，並提供排行榜、每日公告等功能。

## ✨ 功能特色

*   **自動計時**: 只要進入語音頻道，機器人就會自動開始記錄讀書時間。
*   **每日結算**: 每天早上 06:00 自動結算前一天的讀書時間。
*   **排行榜**:
    *   `/help`: 查看指令說明。
    *   `/today`: 查看今天的讀書排行。
    *   `/week`: 查看本週累積排行。
    *   `/leaderboard`: 查看最近 7 天排行。
    *   `/me`: 查看個人統計。
*   **自動公告**: 可設定特定頻道，每天早上自動發布昨天的讀書統計與本週進度。

## 📂 專案結構

```text
DC_StudyBot/
├── main.py              # 機器人啟動入口
├── requirements.txt     # 依賴套件清單
├── .env                 # 環境變數 (Token, 設定)
├── study_time.db        # SQLite 資料庫 (自動生成，勿上傳)
└── src/
    ├── database.py      # 資料庫操作
    ├── utils.py         # 時間與工具函式
    └── cogs/            # 功能模組
        ├── study.py     # 讀書計時核心邏輯
        └── admin.py     # 管理員指令
```

## 🚀 快速開始

### 1. 安裝依賴
確保你有安裝 Python 3.9+，然後執行：
```bash
pip install -r requirements.txt
```

### 2. 設定環境變數
在專案根目錄建立 `.env` 檔案，填入以下資訊：
```ini
DISCORD_BOT_TOKEN=你的_TOKEN_貼在這裡
# (選填) 測試伺服器 ID，用於快速同步指令
DEV_GUILD_ID=
# (選填) 是否啟用 Server Members Intent (若要顯示正確的使用者名稱建議開啟)
USE_MEMBERS_INTENT=1
# (選填) 預設公告頻道 ID
ANNOUNCE_CHANNEL_ID=
```

### 3. 啟動機器人
```bash
python main.py
```

## 📝 指令列表

| 指令 | 說明 |
|---|---|
| `/help` | 顯示指令說明 |
| `/today` | 顯示今天（06:00~隔日06:00）的讀書時間排行 |
| `/week` | 顯示本週（週一06:00起）各成員累積讀書時間 |
| `/leaderboard` | 顯示最近 7 天合計讀書時間排行榜 |
| `/me` | 顯示你今天與本週的累積時數 |
| `/set_announce_channel` | (管理員) 設定每日 06:00 公告頻道 |
| `/sync` | (管理員) 同步指令 |

## ⚠️ 注意事項
*   請勿將 `.env` 和 `*.db` 檔案上傳至 GitHub。
*   若要讓機器人正確讀取成員名單，請在 Discord Developer Portal 開啟 **Server Members Intent**。
