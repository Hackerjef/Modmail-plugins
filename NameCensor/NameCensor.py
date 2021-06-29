import asyncio

from discord.ext import commands


class NameCensorPlugin(commands.Cog):
    """Nick/username censor rawruwuxnuzzles"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)

        self.enabled = True
        self.redlist_nicknames: list = list()
        self.redlist_usernames: list = list()
        self.greenlist_users: list = list()
        asyncio.create_task(self._set_options())

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "greenlist_users": self.greenlist_users,
                    "redlist_nicknames": self.redlist_nicknames,
                    "redlist_usernames": self.redlist_usernames
                }
            },
            upsert=True,
        )

    async def _set_options(self):
        config = await self.db.find_one({"_id": "config"})

        if config is None:
            await self._update_config()
            return

        self.enabled = config.get("enabled", True)
        self.redlist_nicknames = config.get("redlist_nicknames", [])
        self.redlist_usernames = config.get("redlist_usernames", [])
        self.greenlist_users = config.get("user_greenlist", [])

    @commands.group(invoke_without_command=True)
    @commands.is_owner()
    async def namecensor(self, ctx, mode: bool):
        """Disable or enable the nick/user filter.

        Usage: `namecensor enable` / `namecensor disable`
        """
        self.enabled = mode
        await self._update_config()
        await ctx.send(("Enabled" if mode else "Disabled") + " the namecensor filter.")


def setup(bot):
    bot.add_cog(NameCensorPlugin(bot))
