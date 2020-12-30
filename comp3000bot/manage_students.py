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


class ManageStudents(commands.Cog):
    """
    Manage access to the Student role.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.loop.create_task(self._autosave())
        atexit.register(self.save)

        self.students = Students.factory()

    def save(self):
        """
        Save all student managers to disk.
        """
        logger.info('Saving all student information to disk...')
        self.students.to_disk()

    async def _autosave(self):
        """
        An autosave task for asyncio.
        """
        while 1:
            await asyncio.sleep(config.AUTOSAVE_INTERVAL)
            self.save()

    async def cog_before_invoke(self, ctx: commands.Context):
        """
        Hooks every command to ensure the bot is ready.
        """
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Hook a @member joining the server. Send a welcome message prompting them for their secret.
        """
        # Send a welcome message
        try:
            welcome_channel = get_text_channel(member.guild, *config.WELCOME_CHANNELS)
            await welcome_channel.send(
                f'Welcome to the server <@{member.id}>. Please check your private messages from me for further instructions.'
            )
        except Exception as e:
            await member.guild.owner.send(
                f'Unable to send a welcome message: {repr(e)}'
            )

        # Send a challenge DM to new member
        await member.send(
            f'Welcome to {member.guild.name}. You should have been emailed a **secret access token**. Please check your **Carleton email** for your token (if it\'s not there, **check your junk folder**). To get full access to {member.guild.name}, please reply to this message with `!secret your_secret` where you replace `your_secret` with the token from the email. If you are **not** a student, disregard this message.'
        )

    @commands.command()
    @commands.dm_only()
    async def secret(self, ctx: commands.Context, your_secret: str):
        """
        Provide your secret and desired server name. The bot will change your name and grant you the Student role.
        """
        try:
            guild = get_guild_by_id(self.bot, config.GUILD_ID)  # type: discord.Guild
        except IndexError:
            await ctx.send(
                "Unable to find the server. Please contact the instructor or a TA."
            )
            raise Exception("Unable to find the server.")

        member = guild.get_member(ctx.author.id)

        if not member:
            await ctx.send(
                f'I was unable to find you in the server {guild.name}. Perhaps you have been removed automatically. Try joining again.'
            )
            raise Exception(f"Unable to find `{ctx.author.name}` in `{guild.name}`")

        try:
            student = self.students.student_by_secret(your_secret)
        except Exception as e:
            await ctx.send(f'Incorrect secret, please try again.')
            raise e from None

        if student.is_registered:
            await ctx.send(
                f'You are already registered as a student with {guild.name}. Please contact an instructor or TA for assistance.'
            )
            raise Exception(
                f"Student with Discord account `{ctx.author.name}` is already registered"
            )

        # Name needs to be short enough
        name = student.name
        max_name_len = 32
        if len(name) > max_name_len:
            name = name[:max_name_len]
            await ctx.send(
                "I had to shorten your server nickname due to Discord's max nickname length. If you want to request a manual namechange, please message the instructor or a TA."
            )

        try:
            await member.edit(nick=name)
        except Exception as e:
            await ctx.send(
                f'Error setting nickname, please contact an instructor or TA.'
            )
            raise e from None

        try:
            await member.add_roles(get_role(guild, *config.STUDENT_ROLES))
        except Exception as e:
            await ctx.send(
                f'Error changing server role, please contact an instructor or TA.'
            )
            raise e from None

        self.students.register_student(student, member)

        await ctx.send(
            f'Role updated successfully. Welcome to {guild.name}, {name}. If you would like to request a namechange, please message the instructor or a TA.'
        )

    @secret.error
    async def secret_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send(repr(error))
        logger.error(
            f"Failed to register student {ctx.author.name} due to an exception:",
            exc_info=error,
        )

    # @commands.command(hidden=True)
    # @commands.guild_only()
    # @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    # async def update_students(self, ctx: commands.Context):
    #    """
    #    Update all stutdents.
    #    """
    #    guild = ctx.guild  # type: discord.Guild
    #    sm = self.get_student_manger(guild)
    #    sm.registered_students = bidict({})
    #    for member in guild.members:
    #        for student in sm.students.values():  # type: StudentInformation
    #            if student.discord_name == member.name:
    #                sm.registered_students[member.id] = student
    #                logger.info(f'Associated {member.name}, {member.id} with {student}')
    #                break
    #    logger.info('Students updated successfully')

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def create_student(
        self,
        ctx: commands.Context,
        name: str,
        number: int,
        email: str = '',
        overwrite: bool = False,
    ):
        """
        Create a new student with a unique secret. The bot will reply in a DM.
        """
        try:
            student = self.students.add_student(name, number, email, overwrite)
        except Exception as e:
            await ctx.send(f'Error adding student information: {repr(e)}')
            raise e

        await ctx.author.send('Student record created:', file=student.to_csv_file())

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def remove_student(self, ctx: commands.Context, number: int):
        """
        Remove the student with student number @number.
        """
        try:
            student = self.students.remove_student(number)
        except Exception as e:
            await ctx.send(f'Error removing student information: {repr(e)}')
            raise e

        await ctx.author.send(f'Student record removed for {repr(student)}')

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def reset_student(self, ctx: commands.Context, number: int):
        """
        Reset the student with student number @number. This will allow them to re-register with their secret.
        """
        try:
            student = self.students.reset_student(number)
        except Exception as e:
            await ctx.send(f'Error resetting student information: {repr(e)}')
            raise e

        await ctx.author.send(f'Student record reset for {repr(student)}')

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def export_students(self, ctx: commands.Context):
        """
        Send a private message containing the current student CSV.
        """
        await ctx.author.send(
            f'Student records for {ctx.guild.name}:', file=self.students.to_csv_file()
        )

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def create_students_from_csv(
        self, ctx: commands.Context, has_header: bool = False
    ):
        """
        Create new students from the attached CSV file.
        CSV columns should be:
            fname, lname, email, student number
        """
        if not len(ctx.message.attachments):
            await ctx.send('You must attach at least one csv file.')
            return

        for attachment in ctx.message.attachments:  # type: discord.Attachment
            fp = io.StringIO((await attachment.read()).decode('utf-8'))
            await self.students.populate_from_csv_file(ctx, fp, has_header)

        await ctx.author.send(
            f'Student records for {ctx.guild.name}:', file=self.students.to_csv_file()
        )

        await ctx.message.delete()
        await ctx.send('Deleted command message automatically')

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def participation(self, ctx: commands.Context):
        """
        Summarize participation in the Lecture channel.
        """
        channel = get_text_channel_or_curr(ctx, *config.LECTURE_CHANNELS)

        # Calculate time delta for 24h period
        this_morning = dt.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=1
        )
        tomorrow_morning = this_morning + dt.timedelta(days=1)

        participation = defaultdict(lambda: 0)  # type: Dict[str, int]

        sm = self.get_student_manger(ctx.guild)

        messages = channel.history(
            limit=None, before=tomorrow_morning, after=this_morning
        )
        async for message in messages:  # type: discord.Message
            if get_role(ctx.guild, *config.STUDENT_ROLES) not in message.author.roles:
                continue
            try:
                student = sm.student_by_member(message.author)
            except KeyError:
                continue
            nickname = student.name
            participation[nickname] += len(message.content.split())

        if participation.items():
            content = '\n'.join(
                sorted(
                    [f'{name}: {count}' for name, count in participation.items()],
                    key=lambda v: v[0].lower(),
                )
            )
            summary = generate_file(
                'lecture_participation_{this_morning.date()}.txt', content
            )
            await ctx.author.send(
                f'Participation summary (by words typed) for {this_morning.date()}:',
                file=summary,
            )
        else:
            await ctx.author.send(f'No participation data for {this_morning.date()}')
