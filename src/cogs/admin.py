import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from .. import database as db
from .. import utils

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="announce_now", description="（管理員）立刻發布昨天＋本週目前的公告")
    async def cmd_announce_now(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        
        await interaction.response.send_message("準備公告…", ephemeral=True)
        
        # 呼叫 Study Cog 的方法
        study_cog = self.bot.get_cog("Study")
        if study_cog:
            await study_cog._perform_daily_cut_and_announce()
            await interaction.followup.send("已嘗試發布（若昨天無紀錄則不會貼）。", ephemeral=True)
        else:
            await interaction.followup.send("錯誤：找不到 Study 模組。", ephemeral=True)

    @app_commands.command(name="debug_add_time", description="（管理員）人工加某使用者在指定學習日的秒數")
    @app_commands.describe(user="要加給誰", seconds="要加幾秒（正整數）", study_date="學習日（YYYY-MM-DD），預設=今天的學習日")
    async def cmd_debug_add_time(self, interaction: discord.Interaction, user: discord.Member, seconds: int, study_date: str | None = None):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        if seconds <= 0:
            return await interaction.response.send_message("seconds 必須 > 0", ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("僅能在伺服器內使用。", ephemeral=True)
        if not study_date:
            study_date = utils.study_date_of(datetime.now(timezone.utc))
        
        db.add_seconds(guild.id, user.id, study_date, seconds)
        await interaction.response.send_message(
            f"已為 {user.mention} 在學習日 {study_date} 增加 {seconds} 秒（{seconds//60} 分 {seconds%60} 秒）。",
            ephemeral=True
        )

    @app_commands.command(name="sync", description="（管理員）同步 slash 指令。scope=guild|global|both")
    @app_commands.describe(scope="同步範圍：guild（快）、global（可能延遲）、both")
    async def cmd_sync(self, interaction: discord.Interaction, scope: str = "guild"):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        if scope not in {"guild", "global", "both"}:
            return await interaction.followup.send("scope 必須是 guild / global / both", ephemeral=True)
        if scope in {"guild", "both"}:
            if interaction.guild:
                await self.bot.tree.sync(guild=interaction.guild)
            else:
                return await interaction.followup.send("請在伺服器內執行 guild 同步。", ephemeral=True)
        if scope in {"global", "both"}:
            await self.bot.tree.sync()
        await interaction.followup.send(f"同步完成（scope={scope}）。", ephemeral=True)

    @app_commands.command(name="sync_clear_guild", description="（管理員）清除此伺服器舊指令後再同步（謹慎）")
    async def cmd_sync_clear_guild(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.bot.tree.clear_commands(guild=interaction.guild)
        await self.bot.tree.sync(guild=interaction.guild)
        await interaction.followup.send("已清除並重新同步此伺服器指令。", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
