import os
import csv
import io
import asyncio
import atexit
import pickle
import datetime as dt
from collections import defaultdict
from secrets import token_hex
from typing import List, Dict, Tuple, IO

import discord
from discord.ext import commands
from bidict import bidict
from bidict._exc import *

from tabot import config
from tabot.utils import generate_file, generate_csv_file, get_text_channel, get_guild, get_role, get_text_channel_or_curr

class StudentInformation:
    def __init__(self, name: str, number: int, email: str):
        self.name = name
        self.number = number
        self.email = email
        self.discord_name = None # type: str
        self.is_registered = False
        self.generate_new_secret()

    def __repr__(self):
        return f'Student(name={self.name}, number={self.number})'

    def __hash__(self):
        return hash(self.name) ^ hash(self.number)

    def __eq__(self, other):
        return self.name == other.name and self.number == other.number

    def generate_new_secret(self):
        self.secret = token_hex(32)

    def assign_discord_name(self, discord_name: str):
        self.discord_name = discord_name

    @classmethod
    def csv_header(cls) -> Tuple[str, str, str, str, str]:
        return ('name', 'number', 'email', 'discord_name', 'secret')

    def csv_row(self) -> Tuple[str, int, str, str, str]:
        return (self.name, self.number, self.email, self.discord_name, self.secret)

    def to_csv_file(self) -> discord.File:
        return generate_csv_file(f'{self.name}_{self.number}.csv', self.csv_header(), [self.csv_row()])

class StudentManager:
    def __init__(self, _hash: str):
        self.students = bidict({}) # type: bidict[str, StudentInformation]
        self.hash = _hash

    def add_student(self, name: str, number: int, email: str, overwrite: bool = False) -> StudentInformation:
        student = StudentInformation(name, number, email)
        if overwrite:
            self.students.forceput(student.secret, student)
        else:
            try:
                self.students[student.secret] = student
            except ValueDuplicationError:
                raise ValueDuplicationError(f'Refusing to update existing {repr(student)}. You may wish to set overwrite to True.') from None
        return student

    def student_by_secret(self, secret: str) -> StudentInformation:
        """
        Get a student by their secret.
        """
        try:
            return self.students[secret]
        except KeyError:
            raise KeyError(f'No student with secret {secret}') from None

    def to_csv_file(self) -> discord.File:
        return generate_csv_file(f'student_information.csv', StudentInformation.csv_header(), [student.csv_row() for student in self.students.values()])

    @classmethod
    def get_filename(cls, _hash: str) -> str:
        """
        Return the canonical filename of the StudentManager for guild hash @_hash.
        """
        return os.path.join(config.STUDENTS_DIR, f'students_{_hash}.dat')

    def to_disk(self):
        """
        Write StudentManager to disk.
        """
        fname = self.get_filename(self.hash)
        print(f'Saving {fname}...')
        with open(fname, 'wb+') as f:
            pickle.dump(self, f)

    @classmethod
    def from_disk(cls, _hash: str) -> 'StudentManager':
        """
        Load StudentManager from the canonical file for guild hash @_hash.
        """
        fname = cls.get_filename(_hash)
        print(f'Loading {fname}...')
        with open(fname, 'rb') as f:
            obj = pickle.load(f)
        assert type(obj) == cls
        return obj

    def populate_from_csv_file(self, fp: IO[str], has_header: bool, overwrite: bool = False) -> 'StudentInformation':
        """
        Populate this student manager from an open CSV file.
        """
        reader = csv.reader(fp)
        if has_header:
            reader = reader[1:]
        for name, number, email in reader:
            try:
                self.add_student(name, int(number), email, overwrite)
            except KeyError as e:
                print(f'Unable to add student: {e}')

class ManageStudents(commands.Cog):
    """
    Manage access to the Student role.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.student_managers = {} # type: Dict[str, StudentManager]
        bot.loop.create_task(self._autosave())
        atexit.register(self.save)

    def save(self):
        """
        Save all student managers to disk.
        """
        print('Saving all student information to disk...')
        for mgr in self.student_managers.values():
            mgr.to_disk()

    async def _autosave(self):
        """
        An autosave task for asyncio.
        """
        while 1:
            await asyncio.sleep(config.AUTOSAVE_INTERVAL)
            self.save()

    async def _init_students(self, *guilds: discord.Guild):
        """
        Initialize student manger for all @guilds.
        """
        for guild in guilds:
            _hash = hash(guild)
            try:
                mgr = StudentManager.from_disk(_hash)
            except Exception as e:
                print(f'Unable to load student manager for {guild.name}: {repr(e)}')
                mgr = StudentManager(_hash)
            self.student_managers[_hash] = mgr

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
        await self._init_students(*self.bot.guilds)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """
        Hooks the bot joining @guild.
        """
        await self._init_students(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Hooks a member joining @guild.
        """
        # Send a welcome message
        try:
            welcome_channel = get_text_channel(member.guild, *config.WELCOME_CHANNELS)
            await welcome_channel.send(f'Welcome to the server <@{member.id}>. Please check your private messages from me for further instructions.')
        except Exception as e:
            await member.guild.owner.send(f'Unable to send a welcome message: {repr(e)}')

        # Send a challenge DM to new member
        await member.send(f'Welcome to {member.guild.name}. To get full access to {member.guild.name}, please reply to this message with `!secret <your_secret> {member.guild.name}`. If you are **not** a student, disregard this message.')

    @commands.command()
    @commands.dm_only()
    async def secret(self, ctx: commands.Context, your_secret: str, server_name: str):
        """
        Provide your secret and desired server name. The bot will change your name and grant you the Student role.
        """
        guild = None # type: discord.Guild
        member = None
        for guild in self.bot.guilds:
            if guild.name != server_name:
                continue
            member = guild.get_member(ctx.author.id)
            if member:
                break
        if not member:
            await ctx.send(f'I was unable to find you in the server {server_name}. Please check the spelling and try again.')
            return

        try:
            student_manager = self.student_managers[hash(guild)]
        except Exception as e:
            await ctx.send(f'Error accessing server information: {repr(e)}')
            raise e

        try:
            student = student_manager.student_by_secret(your_secret)
        except Exception as e:
            await ctx.send(f'Bad secret, please try again: {repr(e)}.')
            raise e

        if student.is_registered:
            await ctx.send(f'You are already registered as a student with {guild.name}. Please contact an instructor or TA for assistance.')
            return

        student.assign_discord_name(member.name)
        student.is_registered = True

        # Name needs to be short enough
        name = student.name
        max_name_len = 32 - (len(str(student.number)) + 1)
        if len(name) > max_name_len:
            name = name[:max_name_len]
            await ctx.send("I had to shorten your server nickname due to Discord's max nickname length. If you want to request a manual namechange, please message a TA.")
        nickname = f'{name}#{student.number}'

        try:
            await member.edit(nick=nickname)
        except Exception as e:
            await ctx.send(f'Error setting nickname, please contact an instructor or TA: {repr(e)}')
            raise e

        try:
            await member.add_roles(get_role(guild, *config.STUDENT_ROLES))
        except Exception as e:
            await ctx.send(f'Error changing server role, please contact an instructor or TA: {repr(e)}')
            raise e

        await ctx.send(f'Role updated successfully. Welcome to {guild.name}, {nickname}.')

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def create_student(self, ctx: commands.Context, name: str, number: int, email: str, overwrite: bool = False):
        """
        Create a new student with a unique secret. The bot will reply in a DM.
        """
        try:
            student_manager = self.student_managers[hash(ctx.guild)]
        except Exception as e:
            await ctx.send(f'Error accessing server information: {repr(e)}')
            raise e

        try:
            student = student_manager.add_student(name, number, email, overwrite)
        except Exception as e:
            await ctx.send(f'Error adding student information: {repr(e)}')
            raise e

        await ctx.author.send('Student record created:', file=student.to_csv_file())

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def export_students(self, ctx: commands.Context):
        """
        Force the bot to send a DM with the student CSV attached.
        """
        try:
            student_manager = self.student_managers[hash(ctx.guild)]
        except Exception as e:
            await ctx.send(f'Error accessing server information: {repr(e)}')
            raise e

        await ctx.author.send(f'Student records for {ctx.guild.name}:', file=student_manager.to_csv_file())

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def create_students_from_csv(self, ctx: commands.Context, has_header: bool = False):
        """
        Create new students from the attached CSV file. CSV rows should be (name, student number, email).
        """
        if not len(ctx.message.attachments):
            await ctx.send('You must attach at least one csv file.')
            return

        try:
            student_manager = self.student_managers[hash(ctx.guild)]
        except Exception as e:
            await ctx.send(f'Error accessing server information: {repr(e)}')
            await ctx.message.delete()
            await ctx.send('Command message deleted to protect personal information.')
            raise e

        for attachment in ctx.message.attachments: # type: discord.Attachment
            fp = io.StringIO((await attachment.read()).decode('utf-8'))
            student_manager.populate_from_csv_file(fp, has_header)

        await ctx.message.delete()
        await ctx.send('Command message deleted to protect personal information.')

        await ctx.author.send(f'Student records for {ctx.guild.name}:', file=student_manager.to_csv_file())

    @commands.command()
    @commands.guild_only()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    async def participation(self, ctx: commands.Context):
        """
        Summarize participation in the Lecture channel.
        """
        channel = get_text_channel_or_curr(ctx, *config.LECTURE_CHANNELS)

        # Calculate time delta for 24h period
        this_morning = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=1)
        tomorrow_morning = this_morning + dt.timedelta(days=1)

        participation = defaultdict(lambda: 0) # type: Dict[str, int]

        messages = channel.history(limit=None, before=tomorrow_morning, after=this_morning)
        async for message in messages: # type: discord.Message
            if get_role(ctx.guild, *config.STUDENT_ROLES) not in message.author.roles:
                continue
            nickname = message.author.nick or message.author.name
            participation[nickname] += len(message.content.split())

        if participation.items():
            content = '\n'.join(sorted([f'{name}: {count}' for name, count in participation.items()], key=lambda v: v[0].lower()))
            summary = generate_file('lecture_participation_{this_morning.date()}.txt',content)
            await ctx.author.send(
                f'Participation summary (by words typed) for {this_morning.date()}:',
                file=summary
            )
        else:
            await ctx.author.send(
                f'No participation data for {this_morning.date()}'
            )

