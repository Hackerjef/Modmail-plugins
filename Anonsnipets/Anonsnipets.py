from core import checks
from core.models import PermissionLevel
from discord.ext import commands

class Anonsnipetsplugin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['a'])
    @checks.has_permissions(PermissionLevel.MODERATOR)
    @checks.thread_only()
    async def anon(self, ctx, name: str.lower = None):
        if name is not None:
            snippet = self.bot.snippets.get(name, None)

            if snippet is None:
                return await ctx.send('No snippet found')

            async with ctx.typing():
                await ctx.thread.reply('{snippet}', anonymous=True)
            

def setup(bot):
    bot.add_cog(Anonsnipetsplugin(bot))
