from discord.ext import commands
from core import checks
from core.models import PermissionLevel


class Userid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def userid(self, ctx):
        thread = ctx.thread
        if not thread:
            member = ctx.author
        else:
            member = thread.recipient
        await ctx.send(f"{member.id}")


async def setup(bot):
    await bot.add_cog(Userid(bot))
