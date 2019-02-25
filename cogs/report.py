import asyncio

import discord
from discord.ext import commands

REPORT_CHANNEL = 414544787325059082


class Report(commands.Cog):
    """Report commands"""

    def __init__(self, bot):
        self.bot = bot

    async def update_preview(self, msg):
        pass

    @commands.command()
    async def report(self, ctx):
        """Report a person or situation
        This command will walk you through writing a report. Staff will be notified about reports.
        """
        # Anti fucko check
        ww = self.bot.get_guild(215424443005009920)
        mem = ww.get_member(ctx.author.id)
        if discord.utils.get(mem.roles, name="Member") is None:
            return

        if ctx.guild:
            return await ctx.send('Please use this command in a DM with me.', delete_after=5)

        async def response():
            msg = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id and
                                                                     m.channel.id == ctx.channel.id, timeout=300)
            if msg.content[1:].startswith('report') or msg.content.lower() == 'cancel':
                raise discord.ext.commands.CommandError
            return msg.content, msg.attachments

        try:
            await ctx.send("Write `cancel` at any time to cancel the report.")
            await ctx.send("**Who would you like to report?**\n"
                           "Please write their full username+tag if possible, a user ID is also fine.\n"
                           "If it's not about a specific user but for example a situation, write that instead.")
            report_user, _ = await response()

            await ctx.send("**What is the report about?**\n"
                           "Please write the full reason, but keep it within a single message.")
            report_reason, _ = await response()

            await ctx.send("**Do you have proof?**\n"
                           "If you have any screenshots on the situation please post them now. (Max 5)\n"
                           "Write `finish` if you're finished.")
            proof = []
            for i in range(5):
                report_proof, attachments = await response()
                if report_proof.lower() == 'finish':
                    break

                if attachments:
                    for attachment in attachments[:5]:
                        proof += [attachment.url]
                        await ctx.send(f'Added <{attachment.url}>')
                else:
                    proof += [report_proof]
                    await ctx.send(f'Added <{report_proof}>')

            r_embed = discord.Embed(title=f"Report", colour=discord.Colour.blurple())
            r_embed.add_field(name="About", value=report_user, inline=False)
            r_embed.add_field(name="Your message", value=report_reason, inline=False)
            if proof:
                r_embed.add_field(name="Proof", value="\n".join(proof), inline=False)
            preview = await ctx.send(embed=r_embed)

            await ctx.send("**When you're ready to send your report, write `finish`.**\n"
                           "Or `cancel` if you want to start over.")
            response, _ = await response()

            if 'finish' in response.lower():
                await self.bot.db.execute('INSERT INTO `reports` (`reporter`, `about`, `content`, `proof`) VALUES '
                                          '(%s, %s, %s, %s)',
                                          args=(ctx.author.id, report_user, report_reason, "\n".join(proof)))
                await self.bot.get_channel(REPORT_CHANNEL).send(f'{ctx.author} sent a report.', embed=r_embed)
                await ctx.send("**Thanks for your report**\nIt'll be reviewed shortly.")
        except asyncio.TimeoutError:
            await ctx.send("You took too long, write `~report` if you wish to start over.")
        except discord.ext.commands.CommandError:
            await ctx.send("Report cancelled")

    @commands.command()
    @commands.has_role('Staff')
    async def reports(self, ctx, limit=5):
        """Display the latest reports"""
        reports = await self.bot.db.fetch(f'SELECT `id`,`reporter`,`about`,`content`,`proof` FROM `reports` '
                                          f'ORDER BY `id` DESC LIMIT {limit}')
        em = discord.Embed(title=f"Last {limit} reports")
        for i, r, a, c, p in reports:
            val = f'**About:** `{a[:100]}..`\n**Content:** `{c[:100]}..`'
            em.add_field(name=f'#{i} by {self.bot.get_user(r) or "[user left]"}', value=val, inline=False)
        await ctx.send(embed=em)

    @commands.command()
    @commands.has_role('Staff')
    async def showreport(self, ctx, nr):
        """Show a specific report
        You can get the report numbers from ~reports
        """
        r = await self.bot.db.fetchdict(f'SELECT `reporter`,`about`,`content`,`proof` FROM `reports` '
                                        f'WHERE `id`=%s', (nr,))
        if not r:
            return await ctx.send("Couldn't find that report.")
        reporter = self.bot.get_user(r.get('reporter')) or r.get('reporter') or 'Unknown'
        r_embed = discord.Embed(title=f"Report #{nr} by {reporter}", colour=discord.Colour.blurple())
        r_embed.add_field(name="About", value=r.get('about'), inline=False)
        r_embed.add_field(name="Content", value=r.get('content'), inline=False)
        if r.get('proof'):
            r_embed.add_field(name="Proof", value=r.get('proof'), inline=False)
        await ctx.send(embed=r_embed)



def setup(bot):
    bot.add_cog(Report(bot))
