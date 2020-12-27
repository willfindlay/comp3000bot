import os
import re
from typing import List

from decouple import RepositoryEnv, RepositoryIni, Config, config

quoted_string_re = re.compile(r"(?:\"([^\"]+)\"|'([^']+)')")

API_TOKEN = config('API_TOKEN')

SERVER_NAME = config('SERVER_NAME')

DATA_DIR = os.path.abspath(
    os.path.expanduser(config('DATA_DIR', default='~/.comp3000bot'))
)
STUDENTS_DIR = os.path.join(DATA_DIR, config('STUDENTS_FILE', default='students'))

AUTOSAVE_INTERVAL = config('AUTOSAVE_INTERVAL', default=600, cast=int)

INSTRUCTOR_ROLES = config(
    'INSTRUCTOR_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Instructor, instructor, Prof, prof, Professor, professor, Teacher, teacher',
)

TA_ROLES = config(
    'TA_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='TA, Ta, ta',
)

STUDENT_ROLES = config(
    'STUDENT_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Student, student',
)

WELCOME_CHANNELS = config(
    'WELCOME_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Welcome, welcome',
)

POLL_CHANNELS = config(
    'POLL_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Poll, poll, Polls, polls',
)

LECTURE_CHANNELS = config(
    'LECTURE_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Lecture, lecture, Lectures, lectures',
)

STATUS_CHANGE_WAIT = config(
    'STATUS_CHANGE_WAIT',
    cast=int,
    default=f'{60 * 60 * 6}',
)

STATUS_MESSAGES = config(
    'STATUS_MESSAGES',
    cast=lambda v: [m[1].strip() for m in quoted_string_re.finditer(v)],
    default='"Ready for action!", "Enjoy the course!", "Happy GNU/Year!", "What is my purpose?"',
)
