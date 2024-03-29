from core import checks
from core.utils import create_not_found_embed
from core.models import PermissionLevel
from discord.ext import commands


class Anonsnipetsplugin(commands.Cog):
    """Plugin to allow Anon snipets without making aliases for every one of them"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['a'])
    @checks.has_permissions(PermissionLevel.MODERATOR)
    @checks.thread_only()
    async def anon(self, ctx, name: str.lower = None):
        """Anon snippets"""
        if name is not None:
            snippet = self.bot.snippets.get(name, None)

            if snippet is None:
                embed = create_not_found_embed(name, self.bot.snippets.keys(), "Snippet")
                return await ctx.send(embed=embed)

            ctx.message.content = snippet

            async with ctx.typing():
                await ctx.thread.reply(ctx.message, anonymous=True)


async def setup(bot):
    await bot.add_cog(Anonsnipetsplugin(bot))
