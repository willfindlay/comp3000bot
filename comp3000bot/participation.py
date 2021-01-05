from __future__ import annotations

import os
import csv
import io
import asyncio
import atexit
import pickle
import datetime as dt
from collections import defaultdict
from secrets import token_hex
from typing import List, Dict, Tuple, IO, Optional

import discord
from discord.ext import commands
from bidict import bidict
from bidict._exc import *

from comp3000bot import config
from comp3000bot.students import Students, StudentInformation
from comp3000bot.logger import get_logger
from comp3000bot.time import to_time
from comp3000bot.utils import (
    generate_file,
    generate_csv_file,
    get_text_channel,
    get_guild,
    get_guild_by_id,
    get_role,
    get_text_channel_or_curr,
)

logger = get_logger()


class Participation(commands.Cog):
    """
    Get participation metrics for text and voice channels.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.students = Students.factory()

    async def cog_before_invoke(self, ctx: commands.Context):
        """
        Hooks every command to ensure the bot is ready.
        """
        await self.bot.wait_until_ready()

    async def _setup_attendance(self, ctx: commands.Context, timeout: float):
        """
        Set up the attendance poll.
        """
        # Get author
        author = ctx.author  # type: discord.Member

        # Get text channel
        channel = ctx.channel  # type: discord.TextChannel
        if channel is None:
            raise Exception("Command must be run in a text channel")

        # Compute delta
        now = dt.datetime.now()
        delta = dt.timedelta(seconds=timeout)
        end = now + delta

        # Set up the message embed
        description = f"Respond by \"reacting\" to this message (for example, with a thumbs up). You should only respond if your TA is `{author.nick or author.name}`."
        footer = (
            f'Time limit is {delta} (ends at {end.time().strftime("%I:%M:%S %p")}).'
        )
        message_embed = discord.Embed(
            description=description, color=discord.Color.blurple()
        )
        message_embed.set_footer(text=footer)

        # Send the message
        message = await channel.send(
            f"Attendance poll for TA `{author.nick or author.name}`",
            embed=message_embed,
        )  # type: discord.Message

        # Pin the message
        await message.pin(reason="start poll")

        # Cache the message for later
        ctx.poll_message = message

    async def _finish_attendance(self, ctx: commands.Context):
        """
        Finish an attendance poll and summarize results.
        """
        # Get author
        author = ctx.author  # type: discord.Member

        # Get message
        message = await ctx.channel.fetch_message(
            ctx.poll_message.id
        )  # type: discord.Message

        attendance = set()
        for react in message.reactions:  # type: discord.Reaction
            for user in await react.users().flatten():
                if user != self.bot.user:
                    name = ""
                    try:
                        student = self.students.student_by_member(user)
                        name = f"{student.name}#{student.number}"
                    except KeyError:
                        name = user.nick or user.name
                    attendance.add(name)

        # Stop the poll
        await message.clear_reactions()
        await message.edit(content='Attendance poll ended. Thanks for participating.')
        await message.unpin(reason="finish poll")

        # Send sorted attendance list in a private message
        attendance = sorted(attendance)
        desc = "Attendance summary"
        _file = generate_file("attendance.txt", "\n".join(attendance))
        await author.send(desc, file=_file)

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def attendance(self, ctx: commands.Context, timeout: to_time = 3600):
        """
        Run an attendance poll in the current channel.
        Students must respond within the allotted time.
        """
        # Get author
        author = ctx.author  # type: discord.Member
        if author is None:
            raise Exception("Failed to get command author")

        try:
            # Set up the poll
            await self._setup_attendance(ctx, timeout)
            await asyncio.sleep(timeout)
            await self._finish_attendance(ctx)
        except Exception as e:
            await author.send(f"Error during attendance poll: {e}")
