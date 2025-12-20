import psycopg2
from psycopg2 import extras
import os

# ========= DB 設定 =========
# Railway 會自動提供 DATABASE_URL 環境變數，本地測試時需手動設定
DATABASE_URL = os.environ.get('DATABASE_URL')

def db_exec(sql: str, params=(), commit=False):
    """執行 SQL 指令並回傳結果"""
    # PostgreSQL 使用 %s 而不是 ?
    sql = sql.replace('?', '%s')
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if commit:
                    conn.commit()
                if cur.description: # 如果有回傳結果 (SELECT)
                    return cur.fetchall()
                return []
    finally:
        conn.close()

def ensure_db():
    """初始化資料庫表結構"""
    commands = [
        # 使用 BIGINT 確保 Discord ID 不會報錯
        """
        CREATE TABLE IF NOT EXISTS time_log (
            guild_id   BIGINT NOT NULL,
            user_id    BIGINT NOT NULL,
            study_date TEXT   NOT NULL,
            seconds    INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id, study_date)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS config (
            guild_id BIGINT PRIMARY KEY,
            announce_channel_id BIGINT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS active_sessions (
            guild_id   BIGINT NOT NULL,
            user_id    BIGINT NOT NULL,
            session_type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, session_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS paused_sessions (
            guild_id   BIGINT NOT NULL,
            user_id    BIGINT NOT NULL,
            session_type TEXT NOT NULL,
            pause_time TEXT NOT NULL,
            accumulated_seconds INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, session_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS monitor_channels (
            guild_id   BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            PRIMARY KEY (guild_id, channel_id)
        );
        """
    ]
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    try:
        with conn:
            with conn.cursor() as cur:
                for cmd in commands:
                    cur.execute(cmd)
    finally:
        conn.close()

# ------- 查詢功能 -------

def fetch_by_date(guild_id: int, sdate: str):
    return db_exec(
        "SELECT user_id, seconds FROM time_log WHERE guild_id = ? AND study_date = ? ORDER BY seconds DESC",
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
        "SELECT COALESCE(SUM(seconds), 0) FROM time_log WHERE guild_id = ? AND user_id = ? AND study_date = ?",
        (guild_id, user_id, sdate),
    )
    return int(res[0][0]) if res else 0

def fetch_user_sum_between(guild_id: int, user_id: int, start_date: str, end_date: str) -> int:
    res = db_exec(
        "SELECT COALESCE(SUM(seconds), 0) FROM time_log WHERE guild_id = ? AND user_id = ? AND study_date BETWEEN ? AND ?",
        (guild_id, user_id, start_date, end_date),
    )
    return int(res[0][0]) if res else 0

# ------- Config & Monitor -------

def get_config(guild_id: int, default_channel_id: int = 0):
    res = db_exec("SELECT announce_channel_id FROM config WHERE guild_id = ?", (guild_id,))
    return res[0][0] if res and res[0][0] else (default_channel_id or None)

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

def get_monitor_channels(guild_id: int) -> list[int]:
    res = db_exec("SELECT channel_id FROM monitor_channels WHERE guild_id = ?", (guild_id,))
    return [row[0] for row in res]

def add_monitor_channel(guild_id: int, channel_id: int):
    # PostgreSQL 的 INSERT IGNORE 要改成 ON CONFLICT DO NOTHING
    db_exec(
        "INSERT INTO monitor_channels(guild_id, channel_id) VALUES(?, ?) ON CONFLICT DO NOTHING",
        (guild_id, channel_id),
        commit=True
    )

def remove_monitor_channel(guild_id: int, channel_id: int):
    db_exec("DELETE FROM monitor_channels WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id), commit=True)

# ------- 核心邏輯 -------

def add_seconds(guild_id: int, user_id: int, study_date: str, seconds: int):
    db_exec(
        """
        INSERT INTO time_log(guild_id, user_id, study_date, seconds)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id, study_date)
        DO UPDATE SET seconds = time_log.seconds + excluded.seconds
        """,
        (guild_id, user_id, study_date, seconds),
        commit=True
    )

def save_session(guild_id: int, user_id: int, session_type: str, start_time_iso: str):
    db_exec(
        """
        INSERT INTO active_sessions(guild_id, user_id, session_type, start_time)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id, session_type)
        DO UPDATE SET start_time = excluded.start_time
        """,
        (guild_id, user_id, session_type, start_time_iso),
        commit=True
    )

def get_session(guild_id: int, user_id: int, session_type: str):
    res = db_exec("SELECT start_time FROM active_sessions WHERE guild_id = ? AND user_id = ? AND session_type = ?", (guild_id, user_id, session_type))
    return res[0][0] if res else None

def delete_session(guild_id: int, user_id: int, session_type: str):
    db_exec("DELETE FROM active_sessions WHERE guild_id = ? AND user_id = ? AND session_type = ?", (guild_id, user_id, session_type), commit=True)

def pause_session(guild_id: int, user_id: int, session_type: str, pause_time_iso: str, accumulated_secs: int = 0):
    db_exec(
        """
        INSERT INTO paused_sessions(guild_id, user_id, session_type, pause_time, accumulated_seconds)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id, session_type)
        DO UPDATE SET pause_time = excluded.pause_time, accumulated_seconds = excluded.accumulated_seconds
        """,
        (guild_id, user_id, session_type, pause_time_iso, accumulated_secs),
        commit=True
    )

def get_paused_session(guild_id: int, user_id: int, session_type: str):
    res = db_exec("SELECT pause_time, accumulated_seconds FROM paused_sessions WHERE guild_id = ? AND user_id = ? AND session_type = ?", (guild_id, user_id, session_type))
    return res[0] if res else None

def delete_paused_session(guild_id: int, user_id: int, session_type: str):
    db_exec("DELETE FROM paused_sessions WHERE guild_id = ? AND user_id = ? AND session_type = ?", (guild_id, user_id, session_type), commit=True)