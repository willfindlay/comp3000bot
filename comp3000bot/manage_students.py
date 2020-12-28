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
from comp3000bot.logger import get_logger
from comp3000bot.utils import (
    generate_file,
    generate_csv_file,
    get_text_channel,
    get_guild,
    get_role,
    get_text_channel_or_curr,
)

logger = get_logger()


class StudentInformation:
    def __init__(self, name: str, number: int, email: str):
        self.name = name
        self.number = number
        self.email = email
        self.discord_name = None  # type: str
        self.discord_id = None  # type: int
        self.is_registered = False
        self.generate_new_secret()

    def __repr__(self):
        return f'Student(name={self.name})'

    def __hash__(self):
        return hash(self.number)

    def __eq__(self, other):
        return self.number == other.number

    def generate_new_secret(self):
        self.secret = token_hex(32)

    def register(self, member: discord.Member):
        self.discord_name = member.name
        self.discord_id = member.id
        self.is_registered = True

    def reset(self):
        self.discord_name = None
        self.discord_id = None
        self.is_registered = False

    @classmethod
    def csv_header(cls) -> Tuple[str, str, str, str, str]:
        return ('name', 'number', 'email', 'discord_name', 'secret')

    def csv_row(self) -> Tuple[str, int, str, str, str]:
        return (self.name, self.number, self.email, self.discord_name, self.secret)

    def to_csv_file(self) -> discord.File:
        return generate_csv_file(
            f'{self.name}_{self.number}.csv', self.csv_header(), [self.csv_row()]
        )


class StudentManager:
    def __init__(self):
        self.students = bidict({})  # type: bidict[str, StudentInformation]
        self.registered_students = bidict({})  # type: bidict[int, StudentInformation]

    @classmethod
    def get_filename(
        cls,
    ) -> str:
        """
        Return the filename for the student manager.
        """
        return os.path.join(config.STUDENTS_DIR, f'students_{config.GUILD_ID}.dat')

    @classmethod
    def from_disk(cls) -> StudentManager:
        """
        Load StudentManager from a file saved on disk.
        """
        fname = cls.get_filename()
        logger.info(f'Loading {fname}...')
        with open(fname, 'rb') as f:
            obj = pickle.load(f)
        assert type(obj) == cls
        return obj

    @classmethod
    def create_or_load(cls) -> StudentManager:
        """
        Load the student manager for config.GUILD_ID or create one if it doesn't exist.
        """
        try:
            return StudentManager.from_disk()
        except Exception as e:
            logger.warn(
                f'Unable to load student manager for {config.GUILD_ID} due to {repr(e)}'
            )
        return StudentManager()

    def add_student(
        self, name: str, number: int, email: str, overwrite: bool = False
    ) -> StudentInformation:
        student = StudentInformation(name, number, email)
        if overwrite:
            self.students.forceput(student.secret, student)
        else:
            try:
                self.students[student.secret] = student
            except ValueDuplicationError:
                raise Exception(
                    f'Refusing to update existing {repr(student)}. You may wish to set overwrite to True.'
                )
        return student

    def remove_student(self, number: int):
        secret = self.students.inverse[StudentInformation('', number, '')]
        try:
            _id = self.registered_students.inverse[StudentInformation('', number, '')]
            self.registered_students.pop(_id)
        except Exception:
            pass
        return self.students.pop(secret)

    def reset_student(self, number: int):
        secret = self.students.inverse[StudentInformation('', number, '')]
        student = self.students[secret]
        student.reset()
        return student

    def register_student(self, student: StudentInformation, member: discord.Member):
        student.register(member)
        self.registered_students[member.id] = student
        return student

    def student_by_secret(self, secret: str) -> StudentInformation:
        """
        Get a student by their secret.
        """
        try:
            return self.students[secret]
        except KeyError:
            raise KeyError(f'No student with secret {secret}') from None

    def student_by_member(self, member: discord.Member) -> StudentInformation:
        """
        Get a student by their discord member.
        """
        try:
            return self.registered_students[member.id]
        except KeyError:
            raise KeyError(f'No student associated with {member.name}') from None

    def to_csv_file(self) -> discord.File:
        return generate_csv_file(
            f'student_information.csv',
            StudentInformation.csv_header(),
            [student.csv_row() for student in self.students.values()],
        )

    def to_disk(self):
        """
        Write StudentManager to disk.
        """
        fname = self.get_filename()
        logger.info(f'Saving {fname}...')
        with open(fname, 'wb+') as f:
            pickle.dump(self, f)

    async def populate_from_csv_file(
        self,
        ctx: commands.Context,
        fp: IO[str],
        has_header: bool,
        overwrite: bool = False,
    ) -> 'StudentInformation':
        """
        Populate this student manager from an open CSV file.
        The format should be as follows:
            fname, lname, email, number
        """
        reader = csv.reader(fp)
        failed_count = 0
        success_count = 0
        if has_header:
            reader = reader[1:]
        for fname, lname, email, number in reader:
            name = f'{fname} {lname}'
            try:
                self.add_student(name, int(number), email, overwrite)
                success_count += 1
            except Exception as e:
                logger.error(f'Unable to add student ({name}, {number})', exc_info=e)
                failed_count += 1
        if failed_count:
            await ctx.send(f'Failed to add {failed_count} students')
        else:
            await ctx.send(f'Added {success_count} students successfully')


class ManageStudents(commands.Cog):
    """
    Manage access to the Student role.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.loop.create_task(self._autosave())
        atexit.register(self.save)

        self.mgr = StudentManager.create_or_load()

    def save(self):
        """
        Save all student managers to disk.
        """
        logger.info('Saving all student information to disk...')
        self.mgr.to_disk()

    async def _autosave(self):
        """
        An autosave task for asyncio.
        """
        while 1:
            await asyncio.sleep(config.AUTOSAVE_INTERVAL)
            self.save()

    def get_student_manger(self, *args, **kwargs) -> StudentManager:
        return self.mgr

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
            guild = self.bot.guilds[0]  # type: discord.Guild
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

        student_manager = self.mgr

        try:
            student = student_manager.student_by_secret(your_secret)
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

        student_manager.register_student(student, member)

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
        student_manager = self.mgr

        try:
            student = student_manager.add_student(name, number, email, overwrite)
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
        student_manager = self.mgr

        try:
            student = student_manager.remove_student(number)
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
        student_manager = self.mgr

        try:
            student = student_manager.reset_student(number)
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
        student_manager = self.mgr

        await ctx.author.send(
            f'Student records for {ctx.guild.name}:', file=student_manager.to_csv_file()
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

        student_manager = self.mgr

        for attachment in ctx.message.attachments:  # type: discord.Attachment
            fp = io.StringIO((await attachment.read()).decode('utf-8'))
            await student_manager.populate_from_csv_file(ctx, fp, has_header)

        await ctx.author.send(
            f'Student records for {ctx.guild.name}:', file=student_manager.to_csv_file()
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
