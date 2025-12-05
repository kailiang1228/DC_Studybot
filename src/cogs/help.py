import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="顯示所有指令說明")
    async def cmd_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 讀書機器人 - 指令說明",
            description="語音或文字頻道都可以計時！",
            color=0xFFD700
        )

        embed.add_field(
            name="🎧 語音頻道計時",
            value="進入語音 → 自動開始\n離開語音 → 自動記錄",
            inline=False
        )

        embed.add_field(
            name="📖 文字頻道計時",
            value="在監聽頻道輸入：\n• `讀` → 開始計時\n• `休` → 結束計時",
            inline=False
        )

        embed.add_field(
            name="📊 查詢指令",
            value="`/today` 今天排行\n`/week` 本週排行\n`/leaderboard` 7天排行\n`/me` 個人統計\n`/study_status` 誰在讀書",
            inline=False
        )

        embed.add_field(
            name="⚙️ 管理指令",
            value="`/add_monitor_channel` 新增監聽頻道\n`/remove_monitor_channel` 移除監聽頻道\n`/list_monitor_channels` 列出監聽頻道\n`/set_announce_channel` 設定公告頻道",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
