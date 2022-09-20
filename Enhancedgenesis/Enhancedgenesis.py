from datetime import datetime
from core.utils import days
from discord.ext import commands
from discord.utils import snowflake_time


class Enhancedgenesisplugin(commands.Cog):
    """Refined genesis plugin"""

    def __init__(self, bot):
        self.bot = bot

    # Rewrite genesis message to be formated better
    @commands.Cog.listener()
    async def on_thread_ready(self, thread, creator, category, initial_message):
        # Grab older embed data from msg (only change description)
        try:
            embed = thread.genesis_message.embeds[0]
        except Exception:
            raise Exception("Message doesn't have an embed")

        member = self.bot.guild.get_member(thread._recipient.id)
        time = datetime.utcnow()
        created = str((time - thread._recipient.created_at).days)

        embed_description = []
        embed_description.append(f"**Profile:** {thread._recipient.mention}")
        embed_description.append(
            f"**Created:** {days(created)} (`{snowflake_time(thread._recipient.id).strftime('%m/%d/%y @ %I:%M%p')}`)")

        if member is not None and member.joined_at is not None:
            embed_description.append(
                f"**Joined:** {days(str((time - member.joined_at).days))} (`{member.joined_at.strftime('%m/%d/%y @ %I:%M%p')}`)")

        Logs = await self.bot.api.get_user_logs(thread._recipient.id)
        log_count = 0
        for log in Logs:
            if not log['open']:
                log_count += 1

        if log_count:
            thread_word = "Thread" if log_count == 1 else "Threads"
            embed_description.append(f"**{thread_word} Created:** {str(log_count)}")

        embed.description = "\n".join(embed_description)
        await thread.genesis_message.edit(content=thread.genesis_message.content, embed=embed)


async def setup(bot):
    await bot.add_cog(Enhancedgenesisplugin(bot))
