import discord
from discord.ext import commands


class Wordfilter(commands.Cog):
    """Kiara attempting to detect bad words"""

    def __init__(self, bot):
        self.bot = bot
        self.words = []

        self.moderation = bot.get_cog("Moderation")

        self.bot.loop.create_task(self.update_filtered_words())

    async def update_filtered_words(self):
        self.words = await self.bot.redis.lrange('wordfilter', 0, -1, encoding='utf8')
        return self.words

    def test_sentence(self, sentence):
        # if any(word in sentence for word in self.words):
        #     return True
        for word in self.words:
            if word in sentence.lower():
                return word
        return False

    @commands.group()
    @commands.has_role('Staff')
    async def wordfilter(self, ctx):
        """Base word filter command"""
        pass

    @wordfilter.command(name='add')
    async def wordfilter_add(self, ctx, *, phrase):
        """Add a word to the word filter"""
        phrase = phrase.lower()
        await self.bot.redis.rpush('wordfilter', phrase)
        self.words.append(phrase)
        await ctx.send(f'Added `{phrase}` to the filtered words')

    @wordfilter.command(name='remove')
    async def wordfilter_remove(self, ctx, *, phrase):
        """Remove a word from the word filter"""
        phrase = phrase.lower()
        await self.bot.redis.lrem('wordfilter', 0, phrase)
        self.words.remove(phrase)
        await ctx.send(f'Removed `{phrase}` from the filtered words')

    @wordfilter.command(name='list')
    async def wordfilter_list(self, ctx):
        """List the currently filtered words"""
        await ctx.send(f'Current filtered words ({len(self.words)}):\n||{", ".join(self.words)}||')

    @wordfilter.command(name='test')
    async def wordfilter_test(self, ctx, *, message):
        """Test if a sentence would get detected by the word filter"""
        found = self.test_sentence(message)
        if found:
            await ctx.send(f"Message contains `{found}`")
        else:
            await ctx.send("Couldn't detect any filtered words")

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return

        # Ignore kiara
        if msg.author.id == self.bot.user.id:
            return

        # Ignore staff for everything else
        if discord.utils.get(msg.author.roles, id=293008190843387911):
            return

        found = self.test_sentence(msg.content)

        if found:
            await msg.delete()
            await self.moderation.mute_user_id(msg.author.id, 10, "Auto mute")
            await self.moderation.warn_user(msg.author.id, self.bot.user.id, f"Auto-mute: Triggered the word filter (`{found}`)")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild:
            return

        # Ignore kiara
        if after.author.id == self.bot.user.id:
            return

        # Ignore staff for everything else
        if discord.utils.get(after.author.roles, id=293008190843387911):
            return

        found = self.test_sentence(after.content)

        if found:
            await after.delete()
            await self.moderation.mute_user_id(after.author.id, 10, "Auto mute")
            await self.moderation.warn_user(after.author.id, self.bot.user.id, f"Auto-mute: Triggered the word filter (`{found}`)")

def setup(bot):
    bot.add_cog(Wordfilter(bot))
