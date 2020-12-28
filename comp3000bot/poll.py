import asyncio
import datetime as dt
from collections import defaultdict
from inspect import cleandoc
import locale

import discord
from discord.ext import commands

from comp3000bot import config
from comp3000bot.students import Students
from comp3000bot.time import to_time
from comp3000bot.utils import generate_file, get_text_channel_or_curr


class Polls(commands.Cog):
    """
    Create polls in a dedicated channel and summarize participation.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.options = {'👍': 'Yes', '👎': 'No'}

    async def _setup_poll(self, ctx: commands.Context, question: str, timeout: float):
        """
        Set up the new poll context. Send a poll message to the polls channel if it
        exists, otherwise use the current channel.
        """
        now = dt.datetime.now()
        delta = dt.timedelta(seconds=timeout)
        end = now + delta

        description = f"Vote using one of {', '.join(self.options.keys())}."
        footer = (
            f'Time limit is {delta} (ends at {end.time().strftime("%I:%M:%S %p")}).'
        )

        message_embed = discord.Embed(
            description=description, color=discord.Color.blurple()
        )
        message_embed.add_field(name='Poll Question:', value=question)
        message_embed.set_footer(text=footer)

        ctx.polls_channel = get_text_channel_or_curr(ctx, *config.POLL_CHANNELS)

        message = await ctx.polls_channel.send(
            'A new poll is available:', embed=message_embed
        )  # type: discord.Message

        for react in self.options.keys():
            await message.add_reaction(react)

        ctx.question = question
        ctx.poll_message = message
        ctx.participation = defaultdict(lambda: [])

    async def _finish_poll(self, ctx: commands.Context):
        """
        Stop the poll and clean up.
        """
        ctx.poll_message = await ctx.polls_channel.fetch_message(ctx.poll_message.id)
        poll_message = ctx.poll_message  # type: discord.Message
        results = defaultdict(int)

        for react in poll_message.reactions:  # type: discord.Reaction
            results[react.emoji] = react.count - 1
            # Count participation
            for user in await react.users().flatten():
                if user != self.bot.user:
                    try:
                        ctx.participation[user].append(self.options[react.emoji])
                    except KeyError:
                        pass

        # Stop the poll
        await poll_message.clear_reactions()
        await poll_message.edit(content='Poll ended. Thanks for participating.')

        try:
            winner = max(results, key=results.get)
            if results[winner] == 0:
                raise Exception("Nobody voted!")
            await ctx.polls_channel.send(f'{winner} won with {results[winner]} votes.')
        except Exception as e:
            await ctx.polls_channel.send(f'Unable to determine a winner: {e}')

    async def _summarize_participation(self, ctx: commands.Context):
        """
        Send a participation summary to the poll author.
        """
        manage_students = self.bot.get_cog('ManageStudents')
        sm = Students.factory()

        # Get invidual votes
        results = []
        for user, votes in ctx.participation.items():
            try:
                student = sm.student_by_member(user)
            except KeyError:
                continue
            results.append(f'{student.name}: {"/".join(votes)}')

        # Send votes as a file
        results = sorted(results, key=lambda s: s.lower())
        desc = f'Participation summary for poll "{ctx.question}":'
        _file = generate_file('poll_participation_summary.txt', '\n'.join(results))
        await ctx.message.author.send(desc, file=_file)

    async def cog_before_invoke(self, ctx: commands.Context):
        """
        Hooks every command to ensure the bot is ready.
        """
        await self.bot.wait_until_ready()

    @commands.command()
    @commands.has_any_role(*config.INSTRUCTOR_ROLES, *config.TA_ROLES)
    @commands.guild_only()
    async def poll(self, ctx: commands.Context, question: str, timeout: to_time = 300):
        """
        Create a new poll @question with max duration @timeout (default is 5 minutes).  When the poll ends, send a participation summary to the Instructor or TA.
        """
        await self._setup_poll(ctx, question, timeout)
        await asyncio.sleep(timeout)
        await self._finish_poll(ctx)
        await self._summarize_participation(ctx)
