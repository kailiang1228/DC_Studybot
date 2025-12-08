"""
Discord Study Bot - 主程式入口
"""
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from src import database as db

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
DEV_GUILD_ID = int(os.getenv("DEV_GUILD_ID", "0"))
USE_MEMBERS_INTENT = os.getenv("USE_MEMBERS_INTENT", "0") == "1"

# Intents
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
if USE_MEMBERS_INTENT:
    intents.members = True


class StudyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        db.ensure_db()

    async def setup_hook(self):
        # 載入 Cogs
        for ext in ["src.cogs.study", "src.cogs.admin", "src.cogs.help"]:
            try:
                await self.load_extension(ext)
                print(f"📦 已載入: {ext}")
            except Exception as e:
                print(f"❌ 載入失敗 {ext}: {e}")

    async def on_ready(self):
        print(f"✅ 已登入: {self.user} (ID: {self.user.id})")
        
        # 恢復進行中的計時
        study_cog = self.get_cog("Study")
        if study_cog:
            study_cog._restore_sessions()
        
        # 同步指令
        if DEV_GUILD_ID:
            guild = discord.Object(id=DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"✅ 已同步 {len(synced)} 個指令到測試伺服器")
        else:
            synced = await self.tree.sync()
            print(f"✅ 已同步 {len(synced)} 個全域指令")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("請在 .env 設定 DISCORD_BOT_TOKEN")
    bot = StudyBot()
    bot.run(TOKEN)

