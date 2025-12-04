from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import discord

# ========= 時區 =========
def get_taipei_tz():
    try:
        return ZoneInfo("Asia/Taipei")
    except Exception:
        return timezone(timedelta(hours=8))  # 台灣無 DST，固定 UTC+8 可接受

TW_TZ = get_taipei_tz()

# ========= 通用工具 =========
def _hms(seconds: int):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return h, m, s

def format_hms(secs: int) -> str:
    h, m, s = _hms(secs)
    return f"{h:02d}:{m:02d}:{s:02d}"

def study_date_of(ts: datetime) -> str:
    local = ts.astimezone(TW_TZ)
    shifted = local - timedelta(hours=6)
    return shifted.date().isoformat()

def yesterday_study_date_str() -> str:
    today_local = datetime.now(TW_TZ).date()
    return (today_local - timedelta(days=1)).isoformat()

def current_week_start_study_date() -> str:
    today = datetime.now(TW_TZ).date()
    weekday = today.weekday()  # 週一=0
    monday = today - timedelta(days=weekday)
    return monday.isoformat()

def current_week_range():
    start = current_week_start_study_date()
    end = (datetime.fromisoformat(start).date() + timedelta(days=6)).isoformat()
    return start, end

def make_rank_map(rows):
    rank_map = {}
    rank = 1
    prev = None
    for i, (uid, secs) in enumerate(rows, start=1):
        if secs != prev:
            rank = i
            prev = secs
        rank_map[uid] = rank
    return rank_map

def format_table(guild: discord.Guild, rows, title="排行榜"):
    lines = [f"**{title}**"]
    for i, (uid, secs) in enumerate(rows, start=1):
        member = guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        lines.append(f"{i}. **{name}** — {format_hms(secs)}")
    return "\n".join(lines)
