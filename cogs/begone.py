import random

import discord
from discord.ext import commands
from cogs.moderation import MemberID
STAFF_CHANNEL = 231008480079642625


async def generate_embed(title, image_url, reason):
    if reason is not None:
        embed = discord.Embed(title=title, colour=discord.Colour(0xd39466), description=reason)
    else:
        embed = discord.Embed(title=title, colour=discord.Colour(0xd39466))
    embed.set_image(url=image_url)
    return embed


class Begone(commands.Cog):
    """The Begone Thot Command, STAFF ONLY"""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="begonemanage")
    @commands.has_any_role('Staff')
    async def begone_manage(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid sub-command passed')

    @begone_manage.command()
    @commands.has_any_role('Staff')
    async def add_image(self, ctx, image_url, member_id='0'):
        try:
            await self.bot.db.execute('INSERT INTO `begone` (user_id, image_url) VALUES (%s, %s)',
                                      args=(member_id, image_url))
            await ctx.send(f"Successfully added the image for {member_id}")
        except Exception as e:
            print(e)

    @begone_manage.command()
    async def list_images(self, ctx, member_id='0'):
        #Simple Query to obtain all images related to the specified member_id
        r = await self.bot.db.fetchdicts(f'SELECT `id`, `image_url` FROM `begone` WHERE `user_id`={member_id}')
        for item in range(len(r)):
            await ctx.send(f"Image ID: {r[item]['id']}\n"
                           f"Image URL: {r[item]['image_url']}")

    @begone_manage.command()
    @commands.has_any_role('Staff')
    async def remove_image(self, ctx, image_id):
        try:
            await self.bot.db.execute('DELETE FROM begone WHERE id=%s', args = image_id)
        except Exception as e:
            print(e)

    @commands.command(name="begone", aliases=["thot", "begonethot"])
    @commands.has_any_role('Staff')
    async def begone(self, ctx, member: MemberID, *, reason=None):
        permissions = ctx.channel.permissions_for(ctx.author)
        if getattr(permissions, 'ban_members', None):
            try:
                await ctx.guild.ban(discord.Object(id=member), reason=reason)
                member = await self.bot.get_user_info(member)
                r = await self.bot.db.fetchdicts(f'SELECT `id`, `image_url` FROM `begone` WHERE `user_id`={ctx.author.id}')
                if r:
                    rand = random.choice(r)
                    embed = await generate_embed(f'Banned {member}!', rand['image_url'], reason)
                    await ctx.send(embed = embed)
                else:
                    r = await self.bot.db.fetchdicts(f'SELECT `id`, `image_url` FROM `begone` WHERE `user_id`=0')
                    rand = random.choice(r)
                    embed = await generate_embed(f'Banned {member}!', rand['image_url'], reason)
                    await ctx.send(embed = embed)
            except Exception as e:
                await ctx.send(e)
        else:
            ch = self.bot.get_channel(STAFF_CHANNEL)
            member = await self.bot.get_user_info(member)
            await ch.send(f"<@&293008190843387911> {ctx.author.mention} requests banning {member.mention}.")
            await ctx.send('Your ban request has been received.')


def setup(bot):
    bot.add_cog(Begone(bot))
