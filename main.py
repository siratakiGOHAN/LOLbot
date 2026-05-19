import asyncio
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

import core
import data_collector
import database
import ui

_HERE = Path(__file__).parent
load_dotenv(_HERE / ".env")

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
RIOT_API_KEY = os.environ["RIOT_API_KEY"]
_db_raw = os.getenv("DB_PATH", "lolbot.db")
DB_PATH = str(_HERE / _db_raw) if not Path(_db_raw).is_absolute() else _db_raw


class LoLBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await database.init_db(DB_PATH)
        await core.load_champion_cache()
        await core.load_item_cache()
        await core.load_rune_cache()
        ui.setup_commands(self.tree, DB_PATH, RIOT_API_KEY)
        await self.tree.sync()
        print("[main] スラッシュコマンドを同期しました")

    async def on_ready(self) -> None:
        print(f"[main] {self.user} としてログインしました")
        print(f"[main] DB パス: {Path(DB_PATH).resolve()}")
        if not self.weekly_update.is_running():
            self.weekly_update.start()

    @tasks.loop(hours=24)
    async def weekly_update(self) -> None:
        print("[main] 日次データ更新を開始します")
        try:
            await data_collector.collect_high_elo_data(RIOT_API_KEY, DB_PATH)
            await data_collector.sync_champion_names(DB_PATH)
            print("[main] 日次データ更新完了")
        except Exception as e:
            print(f"[main] 日次データ更新エラー: {e}")

    @weekly_update.before_loop
    async def before_weekly_update(self) -> None:
        await self.wait_until_ready()


def main() -> None:
    bot = LoLBot()
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
