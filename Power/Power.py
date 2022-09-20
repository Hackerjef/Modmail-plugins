from discord.ext import commands

from core import checks
from core.models import PermissionLevel, getLogger


class Power(commands.Cog):
    """Shutdown/restart bot with a command - Yes I really needed this at once"""
    def __init__(self, bot):
        self.bot = bot
        self.logger = getLogger("Power")

    @commands.command("shutdown", alias=['restart', 'poweroff'])
    @checks.has_permissions(PermissionLevel.OWNER)
    async def Power_restart(self, ctx):
        """Literally shutdown or restart the bot

        Usage: `shutdown`
        """
        self.logger.info(f"Power triggered by {ctx.author} ({ctx.author.id})")
        await ctx.send(content="👌")
        await self.bot.close()


async def setup(bot):
    await bot.add_cog(Power(bot))
