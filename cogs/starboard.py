from discord.ext import commands
import discord


STAR_CHANNEL = 415464201809690624
STAR_THRESHOLD = 5

IGNORED = [271695900718399488, 415464201809690624]


class Starboard(commands.Cog):
    """Starboard pinning quotes stuff"""

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id in IGNORED:
            return
        if str(payload.emoji) not in ['\N{WHITE MEDIUM STAR}', '✨']:
            return
        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.get_message(payload.message_id)

        if str(payload.emoji) == '✨':
            if not discord.utils.get(channel.guild.get_member(payload.user_id).roles, name="Staff"):
                return
        else:
            if await self.count_stars(msg) < STAR_THRESHOLD:
                return

        if not await self.bot.db.fetchone(f'SELECT * FROM `starboard` WHERE message_id={payload.message_id}'):
            emb = self.make_embed(msg)
            post = await self.bot.get_channel(STAR_CHANNEL).send(embed=emb)
            await self.bot.db.execute(
                f'INSERT INTO `starboard` (message_id, bot_message_id) VALUES ({payload.message_id}, {post.id})')

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        pass

    def make_embed(self, msg):
        emb = discord.Embed(description=msg.content)
        emb.set_author(name=msg.author.name, icon_url=msg.author.avatar_url_as(size=64))
        if msg.attachments:
            emb.set_image(url=msg.attachments[0].url)
        elif msg.embeds:
             emb.set_image(url=msg.embeds[0].image.url)
        emb.timestamp = msg.created_at
        return emb

    async def count_stars(self, msg):
        n = 0
        u = []
        for r in msg.reactions:
            if str(r.emoji) == '\N{WHITE MEDIUM STAR}':
                async for user in r.users():
                    if user.id not in u:
                        n += 1
                        u.append(user.id)
        return n

    def __init__(self, bot):
        self.bot = bot

def setup(bot):
    bot.add_cog(Starboard(bot))
