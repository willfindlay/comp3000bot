from __future__ import annotations

import os
import sys
import pickle
import csv
import datetime as dt
from secrets import token_hex
from typing import List, Dict, Tuple, IO, Optional

import discord
from discord.ext import commands
from bidict import bidict
from bidict._exc import *

from comp3000bot import config
from comp3000bot.singleton import Singleton
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
        return ('name', 'number', 'email', 'discord_name', 'discord_id', 'secret')

    def csv_row(self) -> Tuple[str, int, str, str, str]:
        return (self.name, self.number, self.email, self.discord_name, self.discord_id, self.secret)

    def to_csv_file(self) -> discord.File:
        return generate_csv_file(
            f'{self.name}_{self.number}.csv', self.csv_header(), [self.csv_row()]
        )


class Students(metaclass=Singleton):
    __FILE_NAME = os.path.join(config.STUDENTS_DIR, f'students_{config.GUILD_ID}.dat')

    def __init__(self):
        self.students = bidict({})  # type: bidict[str, StudentInformation]
        self.registered_students = bidict({})  # type: bidict[int, StudentInformation]

    @staticmethod
    def factory():
        """
        Load students from disk or create an empty Students class.
        """
        try:
            return Singleton._instances[Students]
        except Exception:
            pass
        try:
            Students._from_disk()
        except FileNotFoundError as e:
            logger.warn(f"Unable to load students from disk: {repr(e)}")
        return Students()

    @staticmethod
    def _from_disk() -> Students:
        """
        Load Students from a file saved on disk. Don't call this directly. Use Students.factory() instead.
        """
        fname = Students.__FILE_NAME
        logger.info(f'Loading {fname}...')
        with open(fname, 'rb') as f:
            obj = pickle.load(f)
        if not isinstance(obj, Students):
            raise TypeError("Unpicked object is not of type Students")
        Singleton._instances[Students] = obj
        logger.info(f'Loaded {fname}')
        return obj

    def add_student(
        self, name: str, number: int, email: str, overwrite: bool = False
    ) -> StudentInformation:
        """
        Add a new student to the collection of students.
        """
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
        Write Students to disk.
        """
        fname = Students.__FILE_NAME
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
