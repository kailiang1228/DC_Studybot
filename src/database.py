import sqlite3
import os

# ========= DB =========
# 資料庫檔案放在專案根目錄 (假設 main.py 在根目錄執行)
DB_PATH = "study_time.db"

def db_exec(sql: str, params=(), commit=False):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(sql, params)
    if commit:
        con.commit()
    rows = cur.fetchall()
    con.close()
    return rows

def ensure_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS time_log (
        guild_id   INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        study_date TEXT    NOT NULL,   -- YYYY-MM-DD，以 06:00 為界的「學習日」
        seconds    INTEGER NOT NULL,
        PRIMARY KEY (guild_id, user_id, study_date)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        guild_id INTEGER PRIMARY KEY,
        announce_channel_id INTEGER
    );
    """)
    con.commit()
    con.close()

def fetch_by_date(guild_id: int, sdate: str):
    return db_exec(
        """
        SELECT user_id, seconds FROM time_log
        WHERE guild_id = ? AND study_date = ?
        ORDER BY seconds DESC
        """,
        (guild_id, sdate),
    )

def fetch_sum_between(guild_id: int, start_date: str, end_date: str):
    return db_exec(
        """
        SELECT user_id, SUM(seconds) as total
        FROM time_log
        WHERE guild_id = ? AND study_date BETWEEN ? AND ?
        GROUP BY user_id
        ORDER BY total DESC
        """,
        (guild_id, start_date, end_date),
    )

def fetch_user_sum_on(guild_id: int, user_id: int, sdate: str) -> int:
    res = db_exec(
        """
        SELECT COALESCE(SUM(seconds), 0) FROM time_log
        WHERE guild_id = ? AND user_id = ? AND study_date = ?
        """,
        (guild_id, user_id, sdate),
    )
    return (res[0][0] or 0) if res else 0

def fetch_user_sum_between(guild_id: int, user_id: int, start_date: str, end_date: str) -> int:
    res = db_exec(
        """
        SELECT COALESCE(SUM(seconds), 0) FROM time_log
        WHERE guild_id = ? AND user_id = ? AND study_date BETWEEN ? AND ?
        """,
        (guild_id, user_id, start_date, end_date),
    )
    return (res[0][0] or 0) if res else 0

# ------- DB: config -------
def get_config(guild_id: int, default_channel_id: int = 0):
    res = db_exec("SELECT announce_channel_id FROM config WHERE guild_id = ?", (guild_id,))
    if res and res[0][0]:
        return res[0][0]
    return default_channel_id or None

def set_config(guild_id: int, channel_id: int):
    db_exec(
        """
        INSERT INTO config(guild_id, announce_channel_id)
        VALUES(?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET announce_channel_id=excluded.announce_channel_id
        """,
        (guild_id, channel_id),
        commit=True
    )

# ------- 訊息監聽頻道設定 -------
def ensure_monitor_table():
    """確保 monitor_channels 表存在"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS monitor_channels (
        guild_id   INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        PRIMARY KEY (guild_id, channel_id)
    );
    """)
    con.commit()
    con.close()

def get_monitor_channels(guild_id: int) -> list[int]:
    """取得該伺服器所有監聽的頻道 ID"""
    ensure_monitor_table()
    res = db_exec("SELECT channel_id FROM monitor_channels WHERE guild_id = ?", (guild_id,))
    return [row[0] for row in res]

def add_monitor_channel(guild_id: int, channel_id: int):
    """新增監聽頻道"""
    ensure_monitor_table()
    db_exec(
        """
        INSERT OR IGNORE INTO monitor_channels(guild_id, channel_id)
        VALUES(?, ?)
        """,
        (guild_id, channel_id),
        commit=True
    )

def remove_monitor_channel(guild_id: int, channel_id: int):
    """移除監聽頻道"""
    ensure_monitor_table()
    db_exec(
        "DELETE FROM monitor_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id),
        commit=True
    )

def is_monitor_channel(guild_id: int, channel_id: int) -> bool:
    """檢查是否為監聽頻道"""
    ensure_monitor_table()
    res = db_exec(
        "SELECT 1 FROM monitor_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    )
    return len(res) > 0

# ------- 時段累加（自動切 06:00）-------
def add_seconds(guild_id: int, user_id: int, study_date: str, seconds: int):
    db_exec(
        """
        INSERT INTO time_log(guild_id, user_id, study_date, seconds)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id, study_date)
        DO UPDATE SET seconds = seconds + excluded.seconds
        """,
        (guild_id, user_id, study_date, seconds),
        commit=True
    )
