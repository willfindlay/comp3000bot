import os
import sys

import discord
from discord.ext import commands

from tabot import config
from tabot.poll import Polls
from tabot.manage_students import ManageStudents
from tabot.status_message import StatusMessage

class MyHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = 300

def main(sys_args = sys.argv[1:]):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.STUDENTS_DIR, exist_ok=True)

    client = commands.Bot(command_prefix='!')
    client.help_command = MyHelpCommand()

    client.add_cog(Polls(client))
    client.add_cog(ManageStudents(client))
    client.add_cog(StatusMessage(client))

    client.run(config.API_TOKEN)

if __name__ == "__main__":
    main()
