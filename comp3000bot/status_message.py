import asyncio
import random
from typing import List, Dict, Tuple, IO, Optional

import discord
from discord.ext import commands

from comp3000bot import config


class StatusMessage(commands.Cog):
    """
    Manage status messages.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_change_status = True
        self.bot.loop.create_task(self._auto_change_status())

    async def _auto_change_status(self):
        while 1:
            await asyncio.sleep(config.STATUS_CHANGE_WAIT)
            if self.auto_change_status:
                await self._set_status()

    async def _set_status(self, status: Optional[str] = None):
        """
        Set status to @status or choose a random pre-determined status.
        """
        if not status:
            status = random.choice(config.STATUS_MESSAGES)
            self.auto_change_status = True
        else:
            self.auto_change_status = False
        activity = discord.Game(name=status)
        await self.bot.change_presence(activity=activity)
        return status

    async def cog_before_invoke(self, ctx: commands.Context):
        """
        Hooks every command to ensure the bot is ready.
        """
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Hooks the bot being ready.
        """
        await self._set_status()

    @commands.command()
    @commands.is_owner()
    async def set_status(self, ctx: commands.Context, status: Optional[str] = None):
        """
        Set status to @status or choose a random pre-determined status.
        """
        new_status = await self._set_status(status)
        await ctx.send(f'Set status to {new_status}')
