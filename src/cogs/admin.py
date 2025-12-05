import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from .. import database as db
from .. import utils


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="announce_now", description="（管理員）立刻發布昨天的公告")
    async def cmd_announce_now(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)

        await interaction.response.send_message("準備公告…", ephemeral=True)

        study_cog = self.bot.get_cog("Study")
        if study_cog:
            await study_cog._perform_daily_cut_and_announce()
            await interaction.followup.send("已發布公告。", ephemeral=True)
        else:
            await interaction.followup.send("錯誤：找不到 Study 模組。", ephemeral=True)

    @app_commands.command(name="debug_add_time", description="（管理員）手動加時數")
    @app_commands.describe(user="要加給誰", seconds="要加幾秒", study_date="學習日 YYYY-MM-DD（預設今天）")
    async def cmd_debug_add_time(self, interaction: discord.Interaction, user: discord.Member, seconds: int, study_date: str = None):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)
        if seconds <= 0:
            return await interaction.response.send_message("seconds 必須 > 0", ephemeral=True)

        if not study_date:
            study_date = utils.study_date_of(datetime.now(timezone.utc))

        db.add_seconds(interaction.guild.id, user.id, study_date, seconds)
        await interaction.response.send_message(
            f"已為 {user.mention} 在 {study_date} 增加 {seconds} 秒（{seconds // 60} 分 {seconds % 60} 秒）。",
            ephemeral=True
        )

    @app_commands.command(name="sync", description="（管理員）同步指令")
    async def cmd_sync(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("需要『管理伺服器』權限。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        if interaction.guild:
            self.bot.tree.copy_global_to(guild=interaction.guild)
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"已同步 {len(synced)} 個指令。", ephemeral=True)
        else:
            await interaction.followup.send("請在伺服器內使用。", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
