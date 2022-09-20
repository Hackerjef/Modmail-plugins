from datetime import datetime, timezone

from core.thread import Thread
from core.utils import days
from discord.ext import commands
from discord.utils import snowflake_time


class Enhancedgenesisplugin(commands.Cog):
    """Refined genesis plugin"""

    def __init__(self, bot):
        self.bot = bot

    # Rewrite genesis message to be formated better
    @commands.Cog.listener()
    async def on_thread_ready(self, thread: Thread, creator, category, initial_message):
        # Grab older embed data from msg (only change description)
        try:
            genesis_message = await thread.get_genesis_message()
            if not genesis_message:
                return
            embed = genesis_message.embeds[0]
        except Exception:
            raise Exception("Message doesn't have an embed/genesis doesn't exist")

        member = self.bot.guild.get_member(thread._recipient.id)
        time = datetime.utcnow().replace(tzinfo=timezone.utc)
        created = str((time - thread._recipient.created_at).days)

        embed_description = []
        embed_description.append(f"**Profile:** {thread._recipient.mention}")

        embed_description.append(f"**Created:** {days(created)} (<t:{snowflake_time(thread._recipient.id).strftime('%s')}>)")

        if member is not None and member.joined_at is not None:
            embed_description.append(f"**Joined:** {days(str((time - member.joined_at).days))} (`<t:{member.joined_at.strftime('%s')}>`)")

        Logs = await self.bot.api.get_user_logs(thread._recipient.id)
        log_count = 0
        for log in Logs:
            if not log['open']:
                log_count += 1

        if log_count:
            thread_word = "Thread" if log_count == 1 else "Threads"
            embed_description.append(f"**{thread_word} Created:** {str(log_count)}")

        embed.description = "\n".join(embed_description)
        await genesis_message.edit(content=genesis_message.content, embed=embed)


async def setup(bot):
    await bot.add_cog(Enhancedgenesisplugin(bot))
