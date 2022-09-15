from discord.ext import commands

from core import checks
from core.models import PermissionLevel


class Power(commands.cog):
    """Shutdown/restart bot with a command - Yes I really needed this at once"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command("shutdown", alias=['restart', 'poweroff'])
    @checks.has_permissions(PermissionLevel.OWNER)
    async def Power_restart(self, ctx):
        """Literally shutdown or restart the bot

        Usage: `shutdown`
        """
        await ctx.send(content="👌")
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Power(bot))
