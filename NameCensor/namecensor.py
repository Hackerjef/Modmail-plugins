import asyncio

from discord.ext import commands


class Nickusercensorplugin(commands.Cog):
    """Nick/username censor rawruwuxnuzzles"""

    def __init__(self, bot):
        self.bot = bot
        self.coll = bot.plugin_db.get_partition(self)
        self.enabled = True
        self.whitelist = set()
        asyncio.create_task(self._set_config())

    async def _set_config(self):
        config = await self.coll.find_one({"_id": "config"})
        self.enabled = config.get("enabled", True)
        self.redlist_nicknames = set(config.get("redlist_nicknames", []))
        self.redlist_usernames = set(config.get("redlist_usernames", []))
        self.greenlist_users = set(config.get("user_greenlist", []))

    @commands.group(invoke_without_command=True)
    @commands.is_owner()
    async def namecensor(self, ctx, mode: bool):
        """Disable or enable the nick/user filter.

        Usage: `namecensor enable` / `namecensor disable`
        """
        self.enabled = mode

        await self.coll.update_one(
            {"_id": "config"}, {"$set": {"enabled": self.enabled}}, upsert=True
        )

        await ctx.send(("Enabled" if mode else "Disabled") + " the namecensor filter.")


def setup(bot):
    bot.add_cog(Nickusercensorplugin(bot))
