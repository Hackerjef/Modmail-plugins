from discord.ext import commands
import discord

lol = [("hello", "Hello, is there anything I can help with?"), ("meme", "Modmail is a tool used for moderation purposes pertaining to serious reports, requests, or inquiries, please do not spam this service or use it as a meme, or it will result in a block from further usage."), ("support", "We are sorry to hear you are experiencing issues with Discord, however, as we are server moderation and not official support or Discord staff, we have no ability to troubleshoot these issues. If you have any problems regarding Discord, please contact their support department using the following link: https://support.discordapp.com/hc/en-us/"), ("uid", "often during moderation cases, we will need a users ID to properly handle the report, pleas obtain the user ID by following this guide:\nhttps://support.discordapp.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-"), ("default", "Thank you for bringing this to our attention! I will look into the issue and make sure it\'s handled accordingly. For user privacy reasons, we will not be able to inform you of the outcome of our investigation."), ("inactive", "Hello! We would like to be able to assist you with this. This thread has been marked as inactive and will be closed for the time being. Please create a new thread explaining the situation so that we can better help you."), ("phone", "Hi there! Apparently phone verification is broken on discord (rate limits n such) Because of how many people are joining the server, you are going to have to have them wait/or retry at a later time, sorry for the inconvenience!"), ("staff", "I do apologize, but as moderation staff we have very limited communication with the them they may associate with, this means we are unable to forward questions or statements to them, nor can we have them contact specific users."), ("xp", "https://i.nadie.dev/ZDgSrfwhhvVAzqXsOck.png"), ("about", "ModMail is an open sourced moderation contact bot available to self-host and configure, developed by Kyb3r and the team at https://github.com/kyb3r/modmail")]

class Valcbad(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="valcbad")
    async def valcbad_cmd(self, ctx):
        for x, y in lol:
            if x in self.bot.snippets:
                continue
            self.bot.snippets[x] = y

        await self.bot.config.update()
        await ctx.send("Done! Valcrye is bad")
        await ctx.send("unload plugin")

def setup(bot):
    bot.add_cog(Valcbad(bot))
