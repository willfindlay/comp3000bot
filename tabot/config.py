import os
from typing import List

from decouple import RepositoryEnv, RepositoryIni, Config, config

env = Config(RepositoryEnv('.env'))

API_TOKEN = env('API_TOKEN')

DATA_DIR = os.path.abspath(os.path.expanduser(config('DATA_DIR', default='~/.tabot')))
STUDENTS_DIR = os.path.join(DATA_DIR, config('STUDENTS_FILE', default='students'))

AUTOSAVE_INTERVAL = config('AUTOSAVE_INTERVAL', default=600, cast=int)

INSTRUCTOR_ROLES = config(
    'INSTRUCTOR_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Instructor, instructor, Prof, prof, Professor, Professor',
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
