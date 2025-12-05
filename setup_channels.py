import sqlite3
import json

DB = r'd:/Lesson_CODE/code/P_BOT/DC_StudyBot/study_time.db'
CONFIG = 'config.json'

con = sqlite3.connect(DB)
cur = con.cursor()

# 讀 config.json
with open(CONFIG) as f:
    config = json.load(f)

monitor_list = config.get('monitor_channels', [])
guild_id = 875016226240352266  # DEV_GUILD_ID

# 已知的 ID 對應（從你提供的資料）
channel_name_to_id = {
    'note': 875016226240352269,
    '簽到區': 1426174162665472143
}

# 把所有 monitor_channels 項目轉成 (guild_id, channel_id) 並寫入 DB
cur.execute('CREATE TABLE IF NOT EXISTS monitor_channels (guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, PRIMARY KEY (guild_id, channel_id))')

for item in monitor_list:
    # 如果是字串，嘗試轉成數字（channel ID）
    if isinstance(item, str):
        if item in channel_name_to_id:
            channel_id = channel_name_to_id[item]
        else:
            try:
                channel_id = int(item)
            except ValueError:
                print(f"警告：無法解析頻道 '{item}'，跳過")
                continue
    else:
        channel_id = item
    
    cur.execute('INSERT OR IGNORE INTO monitor_channels(guild_id, channel_id) VALUES(?, ?)', (guild_id, channel_id))
    print(f"已新增：guild_id={guild_id}, channel_id={channel_id}")

con.commit()

# 列出結果
cur.execute('SELECT * FROM monitor_channels WHERE guild_id = ?', (guild_id,))
rows = cur.fetchall()
print(f"\n目前 monitor_channels（guild_id={guild_id}）：")
for row in rows:
    print(f"  {row}")

con.close()
