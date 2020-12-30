import os
import re
from typing import List

from decouple import RepositoryEnv, RepositoryIni, Config, config

quoted_string_re = re.compile(r"(?:\"([^\"]+)\"|'([^']+)')")

API_TOKEN = config('API_TOKEN')

GUILD_ID = config('GUILD_ID', cast=lambda v: int(v))

DATA_DIR = os.path.abspath(
    os.path.expanduser(config('DATA_DIR', default='~/.comp3000bot'))
)
STUDENTS_DIR = os.path.join(DATA_DIR, config('STUDENTS_FILE', default='students'))
LOG_FILE = os.path.join(DATA_DIR, config('LOG_FILE', default='comp3000bot.log'))

AUTOSAVE_INTERVAL = config('AUTOSAVE_INTERVAL', default=600, cast=int)

INSTRUCTOR_ROLES = config(
    'INSTRUCTOR_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Prof',
)

TA_ROLES = config(
    'TA_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='TA',
)

STUDENT_ROLES = config(
    'STUDENT_ROLE',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='Student',
)

WELCOME_CHANNELS = config(
    'WELCOME_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='welcome',
)

POLL_CHANNELS = config(
    'POLL_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='polls',
)

LECTURE_CHANNELS = config(
    'LECTURE_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
    default='lecture',
)

TUTORIAL_TEXT_CHANNELS = config(
    'TUTORIAL_TEXT_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
)

TUTORIAL_VOICE_CHANNELS = config(
    'TUTORIAL_VOICE_CHANNEL',
    cast=lambda v: [s.strip() for s in v.split(',')],
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
