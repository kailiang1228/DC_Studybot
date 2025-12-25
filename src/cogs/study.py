import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import os
import json

from .. import database as db
from .. import utils

# 載入設定檔
CONFIG_PATH = "config.json"

def load_config():
    """載入 config.json"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "study_keywords": ["讀", "讀書", "開始", "start"],
        "rest_keywords": ["休", "休息", "結束", "end", "stop"],
        "pause_keywords": ["拉", "暫停"],
        "resume_keywords": ["拉完", "繼續"]
    }

class Study(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: dict[tuple[int, int], datetime] = {}  # (guild_id, user_id) -> start UTC
        self.text_sessions: dict[tuple[int, int], datetime] = {}    # 文字頻道觸發的計時 (guild_id, user_id) -> start UTC
        self.announce_channel_id = int(os.getenv("ANNOUNCE_CHANNEL_ID", "0"))
        self.config = load_config()
        print("[LOG] StudyCog __init__ 啟動，準備啟動 daily_announce_loop")
        # 啟動定時任務
        self.daily_announce_loop.start()

    def _restore_sessions(self):
        """從資料庫恢復進行中的計時"""
        sessions = db.get_all_active_sessions()
        for guild_id, user_id, session_type, start_time_iso in sessions:
            try:
                start_dt = datetime.fromisoformat(start_time_iso)
                key = (guild_id, user_id)
                if session_type == "voice":
                    self.active_sessions[key] = start_dt
                elif session_type == "text":
                    self.text_sessions[key] = start_dt
                print(f"✅ 恢復計時: {session_type} {guild_id}/{user_id} 開始於 {start_time_iso}")
            except Exception as e:
                print(f"❌ 恢復計時失敗: {e}")

    def cog_unload(self):
        self.daily_announce_loop.cancel()


    # ------- 輔助邏輯 -------
    def _add_interval(self, guild_id: int, user_id: int, start_dt: datetime, end_dt: datetime):
        if end_dt <= start_dt:
            return

        def next_boundary(ts: datetime) -> datetime:
            local = ts.astimezone(utils.TW_TZ)
            boundary_local = local.replace(hour=6, minute=0, second=0, microsecond=0)
            if local >= boundary_local:
                boundary_local += timedelta(days=1)
            return boundary_local.astimezone(ts.tzinfo)

        cur_start = start_dt
        while True:
            boundary = next_boundary(cur_start)
            cur_end = min(boundary, end_dt)
            secs = int((cur_end - cur_start).total_seconds())
            if secs > 0:
                sdate = utils.study_date_of(cur_start)
                db.add_seconds(guild_id, user_id, sdate, secs)
            if cur_end >= end_dt:
                break
            cur_start = cur_end

    async def _perform_daily_cut_and_announce(self):
        print(f"[LOG] 進入 _perform_daily_cut_and_announce {datetime.now()} (UTC)")
        # 1) 把仍在語音的人，06:00 前那段切到「昨天學習日」
        now = datetime.now(timezone.utc)
        now_local = now.astimezone(utils.TW_TZ)
        boundary_local = now_local.replace(hour=6, minute=0, second=0, microsecond=0)
        boundary = boundary_local.astimezone(now.tzinfo)

        for (gid, uid), start in list(self.active_sessions.items()):
            if start < boundary < now:
                self._add_interval(gid, uid, start, boundary)
                self.active_sessions[(gid, uid)] = boundary

        # 2) 昨日榜 + 本週目前（週一~昨天）公告
        y_sdate = utils.yesterday_study_date_str()
        wk_start = utils.current_week_start_study_date()
        wk_end_for_now = y_sdate

        for guild in self.bot.guilds:
            ch_id = db.get_config(guild.id, self.announce_channel_id)
            channel = guild.get_channel(ch_id) if ch_id else None
            if channel is None:
                continue

            y_rows = db.fetch_by_date(guild.id, y_sdate)
            if not y_rows:
                continue

            w_rows = db.fetch_sum_between(guild.id, wk_start, wk_end_for_now)
            y_rank = utils.make_rank_map(y_rows)
            w_rank = utils.make_rank_map(w_rows)
            w_dict = dict(w_rows)

            mentions = []
            lines = [f"**{y_sdate}（06:00 ~ 今日06:00）讀書統計｜含本週目前累積**"]

            # 依昨日榜排序列印
            for uid, y_secs in y_rows:
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                mention = member.mention if member else f"<@{uid}>"
                mentions.append(mention)

                y_rank_no = y_rank.get(uid)
                w_secs = w_dict.get(uid, 0)
                w_rank_no = w_rank.get(uid, None)

                lines.append(
                    f"{y_rank_no}. **{name}** — 昨天：{utils.format_hms(y_secs)}（#{y_rank_no}）｜本週目前：{utils.format_hms(w_secs)}（#{'—' if w_rank_no is None else w_rank_no}）"
                )

            header = " ".join(mentions)
            body = "\n".join(lines)
            text = f"{header}\n{body}\n（每日 06:00 自動公告）"
            try:
                await channel.send(text)
            except Exception as e:
                print(f"[WARN] announce send failed in guild {guild.id}: {e}")

    # ------- 事件監聽 -------
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if self.announce_channel_id:
            db.set_config(guild.id, self.announce_channel_id)

    def _is_monitor_channel(self, channel) -> bool:
        """檢查是否為監聽的頻道（從 config.json 讀取）"""
        monitor_list = self.config.get("monitor_channels", [])
        for item in monitor_list:
            # 支援頻道 ID（字串或數字）或頻道名稱
            if str(channel.id) == str(item):
                return True
            if channel.name == item:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽文字頻道訊息，偵測讀/休關鍵字"""
        # 忽略機器人訊息
        if message.author.bot:
            return
        
        # 檢查是否在伺服器內
        if message.guild is None:
            return
        
        # 檢查是否為監聽的頻道（從 config.json）
        if not self._is_monitor_channel(message.channel):
            return
        
        content = message.content.strip()
        key = (message.guild.id, message.author.id)
        now = datetime.now(timezone.utc)
        
        # 從 config 讀取關鍵字
        study_keywords = self.config.get("study_keywords", ["讀", "讀書", "開始", "start"])
        rest_keywords = self.config.get("rest_keywords", ["休", "休息", "結束", "end", "stop"])
        pause_keywords = self.config.get("pause_keywords", ["拉", "暫停"])
        resume_keywords = self.config.get("resume_keywords", ["拉完", "爽", "繼續"])
        
        # 開始讀書
        if content in study_keywords:
            # 檢查是否有暫停的計時
            paused = db.get_paused_session(message.guild.id, message.author.id, "text")
            if paused:
                # 恢復暫停的計時
                pause_time_iso, accumulated_secs = paused
                self.text_sessions[key] = now
                db.delete_paused_session(message.guild.id, message.author.id, "text")
                db.save_session(message.guild.id, message.author.id, "text", now.isoformat())
                # 存儲累積時間在記憶體
                if not hasattr(self, 'accumulated_text_time'):
                    self.accumulated_text_time = {}
                self.accumulated_text_time[key] = accumulated_secs
                await message.add_reaction("📚")
                await message.reply(f"繼續讀書！已累積 {utils.format_hms(accumulated_secs)} 📖", mention_author=False)
                return
            
            if key in self.text_sessions:
                # 已經在讀書中
                start_time = self.text_sessions[key]
                elapsed = now - start_time
                await message.reply(
                    f"你已經在讀書中了！開始時間：<t:{int(start_time.timestamp())}:T>，已經過 {utils.format_hms(int(elapsed.total_seconds()))}",
                    mention_author=False
                )
            else:
                self.text_sessions[key] = now
                db.save_session(message.guild.id, message.author.id, "text", now.isoformat())
                if not hasattr(self, 'accumulated_text_time'):
                    self.accumulated_text_time = {}
                self.accumulated_text_time[key] = 0
                await message.add_reaction("📚")
                await message.reply(f"開始計時！加油！ 📖", mention_author=False)
            return
        
        # 暫停讀書
        if content in pause_keywords:
            if key in self.text_sessions:
                start = self.text_sessions.pop(key)
                elapsed = int((now - start).total_seconds())
                if not hasattr(self, 'accumulated_text_time'):
                    self.accumulated_text_time = {}
                accumulated = self.accumulated_text_time.get(key, 0) + elapsed
                db.pause_session(message.guild.id, message.author.id, "text", now.isoformat(), accumulated)
                db.delete_session(message.guild.id, message.author.id, "text")
                await message.add_reaction("⏸️")
                await message.reply(f"暫停了！已累積 {utils.format_hms(accumulated)} ⏸️", mention_author=False)
            else:
                paused = db.get_paused_session(message.guild.id, message.author.id, "text")
                if paused:
                    _, accumulated_secs = paused
                    await message.reply(f"已暫停，累積時間 {utils.format_hms(accumulated_secs)}。打「繼續」繼續讀書。", mention_author=False)
                else:
                    await message.reply("你還沒開始讀書喔！", mention_author=False)
            return
        
        # 繼續讀書（從暫停狀態）
        if content in resume_keywords:
            if key in self.text_sessions:
                await message.reply("你已經在讀書中了！", mention_author=False)
                return
            paused = db.get_paused_session(message.guild.id, message.author.id, "text")
            if not paused:
                await message.reply("沒有暫停的計時。打「讀」開始新的計時。", mention_author=False)
                return
            # 恢復計時
            pause_time_iso, accumulated_secs = paused
            self.text_sessions[key] = now
            db.delete_paused_session(message.guild.id, message.author.id, "text")
            db.save_session(message.guild.id, message.author.id, "text", now.isoformat())
            if not hasattr(self, 'accumulated_text_time'):
                self.accumulated_text_time = {}
            self.accumulated_text_time[key] = accumulated_secs
            await message.add_reaction("📚")
            await message.reply(f"繼續讀書！已累積 {utils.format_hms(accumulated_secs)} 📖", mention_author=False)
            return
        
        # 結束讀書
        if content in rest_keywords:
            if key in self.text_sessions:
                start = self.text_sessions.pop(key)
                elapsed = int((now - start).total_seconds())
                if not hasattr(self, 'accumulated_text_time'):
                    self.accumulated_text_time = {}
                accumulated = self.accumulated_text_time.pop(key, 0) + elapsed
                # 計算結束時間
                self._add_interval(message.guild.id, message.author.id, start, now)
                db.delete_session(message.guild.id, message.author.id, "text")
                db.delete_paused_session(message.guild.id, message.author.id, "text")
                await message.add_reaction("🎉")
                await message.reply(
                    f"辛苦了！這次讀書時間：{utils.format_hms(elapsed)}（含暫停累積 {utils.format_hms(accumulated)}） ☕",
                    mention_author=False
                )
            else:
                await message.reply("還沒讀書就想休息喔，傻屌。滾去讀書吧!", mention_author=False)
            return

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or member.guild is None:
            return

        key = (member.guild.id, member.id)
        now = datetime.now(timezone.utc)

        joined_before = before.channel is not None
        joined_after  = after.channel is not None

        # 進入語音：開始計時
        if (not joined_before) and joined_after:
            self.active_sessions[key] = now
            db.save_session(member.guild.id, member.id, "voice", now.isoformat())
            return

        # 離開語音：結束計時
        if joined_before and (not joined_after):
            start = self.active_sessions.pop(key, None)
            if start:
                self._add_interval(member.guild.id, member.id, start, now)
            db.delete_session(member.guild.id, member.id, "voice")
            return
        # 在語音內換頻道：忽略

    # ------- 定時任務 -------
    @tasks.loop(minutes=1)
    async def daily_announce_loop(self):
        now_local = datetime.now(utils.TW_TZ)
        print(f"[LOG] daily_announce_loop tick: {now_local.isoformat()} (TW_TZ)")
        if now_local.hour == 6 and now_local.minute == 0:
            print(f"[LOG] daily_announce_loop 命中 6:00，呼叫 _perform_daily_cut_and_announce")
            await self._perform_daily_cut_and_announce()

    @daily_announce_loop.before_loop
    async def _before_daily_announce(self):
        print("[LOG] 等待 bot ready (before daily_announce_loop)")
        await self.bot.wait_until_ready()
        print("[LOG] bot 已 ready，daily_announce_loop 即將啟動")

    # ------- Slash Commands -------
    @app_commands.command(name="today", description="顯示今天（06:00~隔日06:00）的讀書時間排行")
    async def cmd_today(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("僅能在伺服器內使用。", ephemeral=True)

        sdate = utils.study_date_of(datetime.now(timezone.utc))
        rows = db.fetch_by_date(guild.id, sdate)
        if not rows:
            return await interaction.followup.send("今天目前還沒有記錄。", ephemeral=True)

        await interaction.followup.send(utils.format_table(guild, rows, title=f"今天（學習日 {sdate}）"), ephemeral=True)

    @app_commands.command(name="week", description="顯示本週（週一06:00起）各成員累積讀書時間")
    async def cmd_week(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("僅能在伺服器內使用。", ephemeral=True)

        start_date, end_date = utils.current_week_range()
        rows = db.fetch_sum_between(guild.id, start_date, end_date)
        if not rows:
            return await interaction.followup.send("本週尚無記錄。", ephemeral=True)

        await interaction.followup.send(utils.format_table(guild, rows, title=f"本週（{start_date} ~ {end_date}）"), ephemeral=True)

    @app_commands.command(name="leaderboard", description="顯示最近 7 天合計讀書時間排行榜")
    async def cmd_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("僅能在伺服器內使用。", ephemeral=True)

        end_date = utils.study_date_of(datetime.now(timezone.utc))
        start_date = (datetime.fromisoformat(end_date).date() - timedelta(days=6)).isoformat()
        rows = db.fetch_sum_between(guild.id, start_date, end_date)
        if not rows:
            return await interaction.followup.send("最近 7 天沒有記錄。", ephemeral=True)

        await interaction.followup.send(utils.format_table(guild, rows, title=f"最近 7 天（{start_date} ~ {end_date}）"), ephemeral=True)

    @app_commands.command(name="me", description="顯示你今天與本週的累積時數")
    async def cmd_me(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        if guild is None:
            return await interaction.followup.send("僅能在伺服器內使用。", ephemeral=True)

        today = utils.study_date_of(datetime.now(timezone.utc))
        wk_start = utils.current_week_start_study_date()
        me_today = db.fetch_user_sum_on(guild.id, user.id, today)
        me_week  = db.fetch_user_sum_between(guild.id, user.id, wk_start, today)

        await interaction.followup.send(
            f"{user.mention}\n今天：{utils.format_hms(me_today)}\n本週：{utils.format_hms(me_week)}",
            ephemeral=True
        )

    @app_commands.command(name="set_announce_channel", description="設定每日 06:00 公告頻道")
    @app_commands.describe(channel="選擇要公告的文字頻道")
    async def cmd_set_announce_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        db.set_config(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"已設定公告頻道為 {channel.mention}。", ephemeral=True)

    @app_commands.command(name="add_monitor_channel", description="新增監聽頻道（在此頻道打「讀」「休」可計時）")
    @app_commands.describe(channel="選擇要監聽的文字頻道")
    async def cmd_add_monitor_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        db.add_monitor_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"已新增監聽頻道 {channel.mention}。\n"
            f"成員可在此頻道輸入「讀」開始計時，「休」結束計時。",
            ephemeral=True
        )

    @app_commands.command(name="remove_monitor_channel", description="移除監聽頻道")
    @app_commands.describe(channel="選擇要移除的監聽頻道")
    async def cmd_remove_monitor_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        db.remove_monitor_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"已移除監聽頻道 {channel.mention}。", ephemeral=True)

    @app_commands.command(name="list_monitor_channels", description="列出所有監聽頻道")
    async def cmd_list_monitor_channels(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("僅能在伺服器內使用。", ephemeral=True)
        
        channel_ids = db.get_monitor_channels(guild.id)
        if not channel_ids:
            return await interaction.response.send_message("目前沒有設定任何監聽頻道。", ephemeral=True)
        
        channels = []
        for cid in channel_ids:
            ch = guild.get_channel(cid)
            if ch:
                channels.append(ch.mention)
            else:
                channels.append(f"(已刪除的頻道 {cid})")
        
        await interaction.response.send_message(
            f"📢 監聽頻道列表：\n" + "\n".join(f"• {c}" for c in channels),
            ephemeral=True
        )

    @app_commands.command(name="study_status", description="查看目前正在讀書的成員")
    async def cmd_study_status(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("僅能在伺服器內使用。", ephemeral=True)
        
        now = datetime.now(timezone.utc)
        studying = []
        
        # 語音讀書中的成員
        for (gid, uid), start in self.active_sessions.items():
            if gid == guild.id:
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                elapsed = utils.format_hms(int((now - start).total_seconds()))
                studying.append(f"🎧 {name} — {elapsed}（語音）")
        
        # 文字頻道讀書中的成員
        for (gid, uid), start in self.text_sessions.items():
            if gid == guild.id:
                member = guild.get_member(uid)
                name = member.display_name if member else f"User {uid}"
                elapsed = utils.format_hms(int((now - start).total_seconds()))
                studying.append(f"📚 {name} — {elapsed}（文字）")
        
        if not studying:
            return await interaction.response.send_message("目前沒有人在讀書中。", ephemeral=True)
        
        await interaction.response.send_message(
            "**📖 正在讀書中：**\n" + "\n".join(studying),
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Study(bot))
