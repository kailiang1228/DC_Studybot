import discord
from discord import app_commands
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="顯示指令說明")
    async def cmd_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📚 讀書機器人指令說明", color=discord.Color.blue())
        
        embed.add_field(
            name="📊 查詢統計",
            value=(
                "`/today` - 查看今天的讀書排行\n"
                "`/week` - 查看本週累積排行\n"
                "`/leaderboard` - 查看最近 7 天排行\n"
                "`/me` - 查看個人統計"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ 設定與管理",
            value=(
                "`/set_announce_channel` - 設定每日公告頻道\n"
                "`/announce_now` - (管理員) 立即發布公告\n"
                "`/debug_add_time` - (管理員) 手動補時數\n"
                "`/sync` - (管理員) 同步指令"
            ),
            inline=False
        )
        
        embed.set_footer(text="進入語音頻道即可自動開始計時！")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))
