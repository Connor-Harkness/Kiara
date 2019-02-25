import discord
from discord.ext import commands


class Helpful(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.has_any_role('Staff')
    @commands.command(hidden=True)
    async def avatar(self, ctx, user: discord.Member = None):
        """Show someones avatar."""
        if not user:
            user = ctx.author
        await ctx.send(embed=discord.Embed().set_image(url=user.avatar_url).set_footer(text=str(user)))

    @commands.has_any_role('Staff')
    @commands.group(invoke_without_command=True, hidden=True)
    async def snippet(self, ctx, key):
        await ctx.send(await ctx.redis.get(f'snippet:{key}', encoding='utf8'))

    @commands.has_any_role('Staff')
    @snippet.command(hidden=True, name="create")
    async def snippet_create(self, ctx, key, *, content):
        content = self.cleanup_code(content)
        await ctx.redis.set(f'snippet:{key}', content)



def setup(bot):
    bot.add_cog(Helpful(bot))
