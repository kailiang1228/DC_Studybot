import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import os

from .. import database as db
from .. import utils

class Study(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: dict[tuple[int, int], datetime] = {}  # (guild_id, user_id) -> start UTC
        self.announce_channel_id = int(os.getenv("ANNOUNCE_CHANNEL_ID", "0"))
        
        # 啟動定時任務
        self.daily_announce_loop.start()

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
            return

        # 離開語音：結束計時
        if joined_before and (not joined_after):
            start = self.active_sessions.pop(key, None)
            if start:
                self._add_interval(member.guild.id, member.id, start, now)
            return
        # 在語音內換頻道：忽略

    # ------- 定時任務 -------
    @tasks.loop(minutes=1)
    async def daily_announce_loop(self):
        now_local = datetime.now(utils.TW_TZ)
        if now_local.hour == 6 and now_local.minute == 0:
            await self._perform_daily_cut_and_announce()

    @daily_announce_loop.before_loop
    async def _before_daily_announce(self):
        await self.bot.wait_until_ready()

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

async def setup(bot):
    await bot.add_cog(Study(bot))
