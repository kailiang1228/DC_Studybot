# Discord Study Bot (DC_StudyBot)

專注於「讀書計時」的 Discord 機器人。自動記錄語音頻道時間，也支援文字頻道輸入「讀」「休」計時。

## ✨ 功能

- **語音自動計時**: 進入語音頻道自動開始，離開自動記錄
- **文字頻道計時**: 在監聽頻道輸入「讀」開始、「休」結束
- **每日結算**: 每天 06:00 自動結算並公告
- **排行榜**: 今日、本週、7天排行
- **個人統計**: 查看自己的累積時數

## 📂 專案結構

```
DC_StudyBot/
├── main.py              # 機器人入口
├── requirements.txt     # 依賴套件
├── .env                 # 環境變數 (Token)
├── config.json          # 關鍵字設定
├── study_time.db        # SQLite 資料庫 (自動生成)
└── src/
    ├── database.py      # 資料庫操作
    ├── utils.py         # 工具函式
    └── cogs/
        ├── study.py     # 計時核心
        ├── admin.py     # 管理指令
        └── help.py      # 說明指令
```

## 🚀 快速開始

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 設定 .env
```ini
DISCORD_BOT_TOKEN=你的Token
DEV_GUILD_ID=測試伺服器ID
USE_MEMBERS_INTENT=1
ANNOUNCE_CHANNEL_ID=公告頻道ID
```

### 3. 設定 config.json（選填）
```json
{
    "study_keywords": ["讀", "讀書", "開始", "start"],
    "rest_keywords": ["休", "休息", "結束", "end", "stop"],
    "monitor_channels": ["頻道名稱或ID"]
}
```

### 4. 啟動
```bash
python main.py
```

## 📝 指令

### 文字計時（在監聽頻道）
| 關鍵字 | 說明 |
|--------|------|
| `讀` | 開始計時 📚 |
| `休` | 結束計時 🎉 |

### Slash 指令
| 指令 | 說明 |
|------|------|
| `/help` | 顯示說明 |
| `/today` | 今天排行 |
| `/week` | 本週排行 |
| `/leaderboard` | 7天排行 |
| `/me` | 個人統計 |
| `/study_status` | 誰在讀書 |
| `/add_monitor_channel` | 新增監聽頻道 |
| `/remove_monitor_channel` | 移除監聽頻道 |
| `/list_monitor_channels` | 列出監聽頻道 |
| `/set_announce_channel` | 設定公告頻道 |
| `/sync` | 同步指令 |

## ⚠️ 注意

- `.env` 和 `*.db` 請勿上傳 GitHub
- 需在 Discord Developer Portal 開啟：
  - **Server Members Intent**
  - **Message Content Intent**

## 📄 License

MIT

