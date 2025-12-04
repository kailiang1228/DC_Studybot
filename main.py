import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from src import database as db

# 讀 .env
load_dotenv()

# ========= 環境變數 =========
TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
DEV_GUILD_ID = int(os.getenv("DEV_GUILD_ID", "0"))
USE_MEMBERS_INTENT = os.getenv("USE_MEMBERS_INTENT", "0") == "1"

# ========= Intents =========
INTENTS = discord.Intents.default()
INTENTS.voice_states = True
if USE_MEMBERS_INTENT:
    INTENTS.members = True  # 啟用時請在 Portal 打開 Server Members Intent

class StudyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='.', # 雖然主要用 slash command，但 commands.Bot 需要 prefix
            intents=INTENTS,
            application_commands=True
        )
        db.ensure_db()

    async def setup_hook(self):
        # 載入 Cogs
        initial_extensions = [
            'src.cogs.study',
            'src.cogs.admin',
            'src.cogs.help'
        ]
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"已載入模組: {extension}")
            except Exception as e:
                print(f"載入模組 {extension} 失敗: {e}")

        # 先對測試伺服器做 guild 同步（即時）
        if DEV_GUILD_ID:
            try:
                await self.tree.sync(guild=discord.Object(id=DEV_GUILD_ID))
                print(f"已同步測試伺服器: {DEV_GUILD_ID}")
            except Exception as e:
                print(f"同步測試伺服器失敗: {e}")
        
        # 再做 global 同步（給所有伺服器；可能有延遲）
        # 注意：頻繁 global sync 可能會被 rate limit，建議開發時用 guild sync
        # await self.tree.sync() 

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("請在 .env 設定 DISCORD_BOT_TOKEN（或 DISCORD_TOKEN）")
    
    bot = StudyBot()
    bot.run(TOKEN)
