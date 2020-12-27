import os
import sys

import discord
from discord.ext import commands

from comp3000bot import config
from comp3000bot.poll import Polls
from comp3000bot.manage_students import ManageStudents
from comp3000bot.status_message import StatusMessage


class MyHelpCommand(commands.DefaultHelpCommand):
    """
    A help command with longer help messages.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = 300


def main(sys_args=sys.argv[1:]):
    # Create directories to store data, if they don't already exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.STUDENTS_DIR, exist_ok=True)

    # We now need to signal what "Intents" we want to use.
    # Since we require privileged intents, don't forget to turn those on via the
    # bot management interface in Discord's developer portal.
    intents = discord.Intents.all()

    # Create the bot with command prefix '!' and out list of "Intents"
    client = commands.Bot(command_prefix='!', intents=intents)

    # Override the default help command with something more, well, helpful...
    client.help_command = MyHelpCommand()

    # Add cogs, one for each category of operation
    client.add_cog(Polls(client))
    client.add_cog(ManageStudents(client))
    client.add_cog(StatusMessage(client))
    # TODO: Add a participation cog

    # Run the bot
    client.run(config.API_TOKEN)


if __name__ == "__main__":
    main()
