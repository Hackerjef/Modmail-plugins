from core import checks
from core.models import getLogger, PermissionLevel
from discord.ext import commands

logger = getLogger(__name__)


class Topicplugin(commands.Cog):
    """Plugin to change thread Topics without breaking modmail"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    @checks.thread_only()
    async def topic(self, ctx, *topic):
        """change thread Topics"""
        logger.info("Setting thread topic")
        topic_complete = " ".join(topic)
        await self.bot.get_channel(ctx.thread.channel.id).edit(
            topic=f"User ID: {ctx.thread._recipient.id} | {topic_complete}")
        sent_emoji, _ = await self.bot.retrieve_emoji()
        await self.bot.add_reaction(ctx.message, sent_emoji)


def setup(bot):
    bot.add_cog(Topicplugin(bot))
