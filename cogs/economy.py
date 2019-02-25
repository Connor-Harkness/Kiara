import asyncio
import datetime
import random
from enum import Enum
import logging

import discord
from discord.ext import commands
from async_generator import asynccontextmanager

from .utils.cooldowns import basic_cooldown
from .utils import fuzzy
from .utils import time

log = logging.getLogger(__name__)


def exp_needed(level):
    return level * 250


def exp_total(level):
    return sum([exp_needed(x) for x in range(level + 1)])


def levelup_gold(lvl):
    if lvl <= 5:
        amount = random.randint(1, 10)
    elif lvl <= 10:
        amount = random.randint(5, 10)
    elif lvl <= 20:
        amount = random.randint(5, 15)
    elif lvl <= 30:
        amount = random.randint(10, 20)
    elif lvl <= 40:
        amount = random.randint(15, 20)
    elif lvl <= 50:
        amount = random.randint(20, 30)
    else:
        amount = random.randint(25, 35)
    return amount


class Shop:
    __slots__ = ('id', 'name', 'description', 'icon', 'items')

    def __init__(self, *, id, name, description, icon=None, items=[]):
        self.id = id

    @classmethod
    def from_data(cls, data):
        self = cls.__new__(cls)

        self.id = data.get('id')
        self.name = data.get('name')
        self.description = data.get('description')
        self.icon = data.get('icon')
        self.items = []

        return self

    async def populate(self):
        pass

    def add_item(self, item):
        self.items += [item]

    def get(self, item):
        return discord.utils.get(self.items, name=item)

    def __name__(self):
        return self.name

    def __repr__(self):
        return f"<Shop id='{self.id}' name='{self.name}' items={len(self.items)}>"


class ShopItem:
    __slots__ = ('id', 'shop_id', 'name', 'type', 'cost', 'item_id', 'data', 'active')

    def __init__(self, id, shop_id, name, type, cost, item_id, data):
        self.shop_id = shop_id
        self.name = name
        self.type = type
        self.cost = cost
        self.item_id = item_id
        self.data = data

    @classmethod
    def from_data(cls, data):
        self = cls.__new__(cls)

        self.id = data.get('id')
        self.shop_id = data.get('shop_id')
        self.name = data.get('name')
        self.type = data.get('type')
        self.cost = data.get('cost')
        self.item_id = data.get('item_id')
        self.data = data.get('data')
        self.active = data.get('active')

        return self

    def get_role_id(self):
        if self.type != 'color_role':
            return None
        return self.data

    def __repr__(self):
        return f"<ShopItem name='{self.name} type={self.type} cost={self.cost} data={self.data}>"

    def get_name(self):
        if self.type == 'color_role':
            return f'<@&{self.data}>'
        else:
            return self.name

    def get_raw_text(self):
        ticks = ['<:redtick:526847326669504554>', '<:greentick:526847326812110933>']
        return f'{ticks[self.active]} `{self.id:03d}` {self.get_name()} | {self.cost}g'


class ShopItemType(Enum):
    BASIC = 1
    COLOR_ROLE = 2


class Buff:
    __slots__ = ('id', 'user_id', 'name', 'expires', 'value', '_economy', '_db')

    def __init__(self, data, *, economy):
        self._economy = economy
        self._db = economy.bot.db

        for k in data:
            setattr(self, k, data[k])

    async def remove(self):
        await self._db.execute('DELETE FROM active_buffs WHERE id=%s', (self.id,))
        await self._economy.update_buffs(self.user_id)


class Profile:
    __slots__ = ('user_id', 'level', 'experience', 'fame', 'coins', '_economy', '_db')

    def __init__(self, data, *, economy):
        self._economy = economy
        self._db = economy.bot.db

        for k in data:
            setattr(self, k, data[k])

    async def save(self, db=None):
        s = ','.join([f'{s}={getattr(self,s)}' for s in self.__slots__[1:-2] if getattr(self, s, None) is not None])
        await self._db.execute(f"UPDATE profiles SET {s} WHERE user_id={self.user_id}")

    async def has_item(self, name=None):
        pass


class Economy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self._shops = []
        self._active_buffs = {}

        self.cooldowns = {}
        self._locks = dict()

        self.exp_rate = 1
        self.gold_rate = 1

        self.bot.loop.create_task(self.init_econ())

    async def init_econ(self):
        await self.bot.wait_until_ready()
        await self.init_shop()
        await self.init_buffs()

    async def init_shop(self):
        self._shops = []
        count = 0
        for shop_data in await self.bot.db.fetchdicts('SELECT * FROM shops WHERE active=1'):
            shop = Shop.from_data(shop_data)
            qry = 'SELECT * FROM shop_items WHERE shop_id=%s ORDER BY -sort_order DESC'
            for item_data in await self.bot.db.fetchdicts(qry, (shop.id,)):
                shop.add_item(ShopItem.from_data(item_data))
                count += 1
            self._shops.append(shop)
        log.info(f'Loaded {count} items from {len(self._shops)} shops')

    async def init_buffs(self):
        count = 0
        for data in await self.bot.db.fetchdicts('SELECT * FROM active_buffs'):
            self._active_buffs.setdefault(data['user_id'], []).append(Buff(data, economy=self))
            count += 1
        log.info(f'Loaded {count} active buffs from {len(self._active_buffs)} users')

    def remove_buff(self, buff):
        self._active_buffs[buff.user_id].remove(buff)
        log.info(f'New buffs: {self._active_buffs}')

    async def get_buffs(self, user_id):
        for buff in self._active_buffs.setdefault(user_id, []):
            if buff.expires <= datetime.datetime.now():
                await buff.remove()
            else:
                yield buff

    async def get_buff(self, user_id, buff_name):
        async for buff in self.get_buffs(user_id):
            if buff.name == buff_name:
                return buff
        return None

    async def give_buff(self, user_id, buff_name, expires=None):
        await self.bot.db.execute(f'INSERT INTO active_buffs (user_id, name, expires) VALUES (%s,%s,%s)',
                                  (user_id, buff_name, datetime.datetime.now()+datetime.timedelta(seconds=expires)))
        await self.update_buffs(user_id)

    async def update_buffs(self, user_id):
        buffs = await self.bot.db.fetchdicts('SELECT * FROM active_buffs WHERE user_id=%s', (user_id,))
        self._active_buffs[user_id] = [Buff(data, economy=self) for data in buffs]

    async def get_shops(self):
        if not self._shops:
            await self.init_shop()
        return self._shops

    def get_closest_item(self, item_name):
        items = fuzzy.finder(item_name, self.all_shop_items(), key=lambda t: t.name, lazy=False)
        return items[0] if items else None

    def all_shop_items(self, **data):
        for shop in self._shops:
            for item in shop.items:
                if all(getattr(item, key) == val for key, val in data.items() if val is not None):
                    yield item

    @asynccontextmanager
    async def transaction(self, user_id, save=True):
        async with self.get_lock(user_id):
            profile = await self.get_profile(user_id)
            yield profile
            if save:
                await profile.save()

    def get_lock(self, name):
        lock = self._locks.get(name)
        if not lock:
            lock = asyncio.Lock(loop=self.bot.loop)
            self._locks[name] = lock
        return lock

    async def get_profile(self, uid, keys=None):
        profile = await self.bot.db.fetchdict(f'SELECT * FROM profiles WHERE user_id={uid}')
        if not profile:
            await self.bot.db.execute(f'INSERT INTO profiles (user_id) VALUES ("{uid}")')
            return Profile({'user_id': uid, 'level': 0, 'experience': 0, 'coins': 0}, economy=self)
        return Profile(profile, economy=self)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild:
            return
        if msg.channel.id in [269910005837332480, 451729018199212032]:
            return
        if msg.author.bot:
            return
        async with self.transaction(msg.author.id) as profile:

            d = abs(msg.created_at - self.cooldowns.get(profile.user_id, datetime.datetime(2000, 1, 1)))
            if d < datetime.timedelta(seconds=5):
                return

            profile.experience += 10 * self.exp_rate

            # Bonus for images
            if msg.attachments:
                profile.experience += 10 * self.exp_rate

                # Extra bonus for waifu channels
                if msg.channel.id in [467658653273423872, 467658673918050305]:
                    profile.experience += 20
            else:
                self.cooldowns[profile.user_id] = msg.created_at

            needed = exp_needed(profile.level)

            # Terrible temporary levelup
            if profile.experience >= needed:
                profile.level += 1
                profile.experience -= needed
                profile.coins += levelup_gold(profile.level) * self.gold_rate

                # Temporary faithful role, the whole role idea will change in the future.
                if profile.level == 3:
                    await msg.author.add_roles(discord.utils.get(msg.guild.roles, id=457213160504426496))

                if profile.level % 5 == 0:
                    role = discord.utils.get(msg.guild.roles, name=str(profile.level))
                    if role:
                        await msg.author.add_roles(role, reason=f"Reached level {profile.level}")
                        rem = discord.utils.get(msg.guild.roles, name=str(max(profile.level - 5, 1)))
                        await msg.author.remove_roles(rem, reason=f"Reached level {profile.level}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        profile = await self.get_profile(member.id, ('level',))
        role = discord.utils.get(member.guild.roles, name=str(profile.level // 5 * 5))
        if role:
            await member.add_roles(role, reason=f"Re-joined the server at level {profile.level}")

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def givegold(self, ctx, member: discord.Member, gold: int):
        async with self.transaction(member.id) as profile:
            profile.coins += gold
        await ctx.send(f"{member} now has {profile.coins} gold")

    @commands.command(hidden=True, aliases=['givecolour'])
    @commands.has_permissions(administrator=True)
    async def givecolor(self, ctx, member: discord.Member, *, color: discord.Role):

        await self.bot.db.execute(f'INSERT INTO colors (user_id, color) VALUES ({member.id}, {role.id})')
        await ctx.send(f"Gave {member} the color <@&{role.id}>")

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def takegold(self, ctx, member: discord.Member, gold: int):
        async with self.transaction(member.id) as profile:
            profile.coins -= gold
        await ctx.send(f"{member} now has {profile.coins} gold")

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def setlevel(self, ctx, member: discord.Member, level: int, xp: int = None):
        async with self.transaction(member.id) as profile:
            profile.level = level
            if xp:
                profile.experience = xp
        await ctx.send(f"{member} is now level {level}")

    @commands.command()
    async def profile(self, ctx):
        """Display your profile"""
        member = ctx.author
        e = discord.Embed(title=member.display_name)
        e.set_thumbnail(url=member.avatar_url_as(size=128))
        e.add_field(name=f'Created', value=time.time_ago(member.created_at), inline=True)
        if ctx.guild:
            if member.id == 73389450113069056:
                member.joined_at = ctx.guild.created_at
            if member.id == 129034173305454593:
                member.joined_at = datetime.datetime(2017, 9, 3, 8, 48)
            e.add_field(name=f'Joined', value=time.time_ago(member.joined_at), inline=True)
            e.add_field(name=f'Nickname', value=member.nick or "None", inline=False)
            e.add_field(name=f'Roles', value=' '.join([role.mention for role in member.roles[:0:-1]]), inline=False)

            role = self.get_top_color(member.roles) if ctx.guild else None
            if role:
                e.colour = role.color
        econ = self.bot.get_cog('Economy')
        if econ:
            items = await econ.get_inventory(ctx.author.id)
            if items:
                items = [f'<:bs:{item["icon"]}>' for item in items]
                e.add_field(name="Inventory", value=' '.join(items))
        await ctx.send(embed=e)

    @commands.command(hidden=True)
    async def bank(self, ctx, page: int = 1):
        """Display the wealthiest members on the server"""
        guild = self.bot.get_guild(215424443005009920)
        qry = f"""
                select `user_id`, `coins`, `rank` FROM
                (
                select t.*, @r := @r + 1 as `rank`
                from  profiles t,
                (select @r := 0) r
                order by `coins` desc
                ) as t
                limit %s, %s
                """
        r = await ctx.bot.db.fetch(qry, ((page - 1) * 10, 10))
        w = max(len(getattr(guild.get_member(user_id), 'display_name', 'user_left')) for user_id, coins, rank in r)
        output = '```\n' + '\n'.join([
            f"{int(rank):<3} - {getattr(guild.get_member(user_id),'display_name','user_left'):<{w}} - {coins:>10} gold"
            for user_id, coins, rank in r]) + '```'
        await ctx.send(output)

    @commands.command(hidden=True)
    async def rank(self, ctx, member: discord.Member = None):
        if not member:
            member = ctx.author
        qry = f"""
            select `level`, `experience`, `rank` FROM
            (
            select t.*, @r := @r + 1 as `rank`
            from  profiles t,
            (select @r := 0) r
            order by `level` desc, `experience` desc
            ) as t
            where `user_id`={member.id}
            """
        lvl, xp, rank = await ctx.bot.db.fetchone(qry)
        em = discord.Embed(title=f'**{member.display_name}**', color=0x77dd77,
                           description=f'**Rank {round(rank)} - Lv{lvl}** {xp}/{exp_needed(lvl)}xp')
        await ctx.send(embed=em)

    @commands.command(hidden=True, aliases=['leaderboards', 'ranks', 'rankings'])
    async def leaderboard(self, ctx, page: int = 1):
        """Display the server leaderboard"""
        guild = self.bot.get_guild(215424443005009920)
        qry = f"""
            select `user_id`, `level`, `experience`, `rank` FROM
            (
            select t.*, @r := @r + 1 as `rank`
            from  profiles t,
            (select @r := 0) r
            order by `level` desc, `experience` desc
            ) as t
            limit %s, %s
            """
        r = await ctx.bot.db.fetch(qry, ((page - 1) * 10, 10))
        w = max(len(getattr(guild.get_member(user_id), 'display_name', 'user_left')) for user_id, lvl, xp, rank in r)
        output = '```\n' + '\n'.join([
            f"{int(rank):<3} - {getattr(guild.get_member(user_id),'display_name','user_left'):<{w}} - Lv{lvl:<4} {xp:<5} / {exp_needed(lvl):>5}xp"
            for user_id, lvl, xp, rank in r]) + '```'
        await ctx.send(output)

    @commands.command(aliases=['experience'])
    async def xp(self, ctx, *, member: discord.Member = None):
        """Check your xp"""
        if not member:
            member = ctx.author
        p = await self.get_profile(member.id, ('level', 'experience'))
        em = discord.Embed(title=f'{member.display_name}')
        em.add_field(name="Level", value=f'**{p.level}**')
        em.add_field(name="Exp", value=f'{p.experience}/{exp_needed(p.level)}xp')
        em.set_thumbnail(url=member.avatar_url_as(size=64))

        role = self.get_top_color(member.roles)
        if role:
            em.colour = role.color

        await ctx.send(embed=em)

    def get_top_color(self, roles):
        excluded = ['Muted', 'Guardian Angel']
        for role in roles[::-1]:
            if role.color != discord.Colour.default() and role.name not in excluded:
                return role
        return None

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def exprate(self, ctx, rate: float = None):
        if rate:
            self.exp_rate = rate
        await ctx.send(f"Exp rate is now x{self.exp_rate}")

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def goldrate(self, ctx, rate: float = None):
        if rate:
            self.gold_rate = rate
        await ctx.send(f"Gold rate is now x{self.gold_rate}")

    @commands.guild_only()
    @commands.group(invoke_without_command=True)
    async def shop(self, ctx, shop=None, extended=False):
        if ctx.invoked_subcommand:
            return

        shops = await self.get_shops()
        if not shops:
            return await ctx.send("Shop is empty atm.")

        if shop:
            try:
                shop = discord.utils.get(shops, name=shop) or discord.utils.get(shops, id=int(shop))
                if not shop:
                    shop = shops[0]
            except ValueError:
                pass

        else:
            shop = shops[0]

        emojis = ['❤', '💜', '🍉']

        # Fetch profile
        profile = await self.get_profile(ctx.author.id)

        # Fetch data
        owned_colors = await self.get_owned_colors(ctx.author.id)

        # Shop embed
        def get_shop_embed(shop_id):
            shop = discord.utils.get(shops, id=shop_id)
            shop_embed = discord.Embed(title=shop.name, description=shop.description+'\n\nBuy an item with `!buy [item]`.')
            for item in self.all_shop_items(shop_id=shop.id, active=True):
                if item.type == 'color_role':
                    item_name = f'**<@&{item.data}>**'
                    item_price = 'bought~' if item.data in owned_colors else f'{item.cost}g'
                else:
                    item_name = f'**{item.name}**'
                    item_price = f'{item.cost}g'
                shop_embed.add_field(name=f'\u200b', value=f'{item_name}\n{item_price}')

            shop_embed.set_footer(text=f"You have {profile.coins} gold")
            return shop_embed

        # Shop message
        shop_msg = await ctx.send(embed=get_shop_embed(shop.id))
        if not extended:
            return
        for em in emojis:
            await shop_msg.add_reaction(em)

        try:
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in emojis and reaction.message.id == shop_msg.id
            while True:
                r, u = await self.bot.wait_for('reaction_add', timeout=30, check=check)
                await shop_msg.remove_reaction(r, u)
                await shop_msg.edit(embed=get_shop_embed(emojis.index(str(r))+1))

        except asyncio.TimeoutError:
            await shop_msg.clear_reactions()

    @commands.has_role('Staff')
    @shop.command(name='reload', aliases=['update'])
    async def shop_reload(self, ctx):
        await self.init_shop()
        await ctx.send("Dun")

    @commands.has_role('Staff')
    @shop.command(name='raw', aliases=['rawdata'])
    async def shop_raw(self, ctx, shop_id: int = None):
        """Show items from a shop with their id etc"""
        pag = commands.Paginator('', '')
        if shop_id:
            pag.add_line(f'**Items in shop #{shop_id}**')
        else:
            pag.add_line('**Items in all shops**')
        items = self.all_shop_items(shop_id=shop_id)
        if items:
            for item in items:
                pag.add_line(item.get_raw_text())
        else:
            pag.add_line('Nothing')
        for page in pag.pages:
            await ctx.send(page)

    @commands.has_role('Staff')
    @shop.command(name='swap', aliases=['reorder'])
    async def shop_swap(self, ctx, item_one: int, item_two: int):
        """Swap the order of two items"""
        # qry = 'UPDATE shop_items s1, shop_items s2 ' \
        #       'SET s1.sort_order=s1.sort_order, s1.sort_order=s2.sort_order ' \
        #       'WHERE s1.id=s2.id AND s1.id=%s;'
        # await self.bot.db.execute(qry, (item_one, item_two))

    @commands.has_role('Staff')
    @shop.command(name='addcolor', aliases=['addrole'])
    async def shop_addcolor(self, ctx, shop_id: int, color: discord.Role, price: int = 50):
        qry = 'INSERT INTO shop_items (shop_id, type, name, cost, data) VALUES (%s,%s,%s,%s,%s)'
        await self.bot.db.execute(qry, (shop_id, 'color_role', color.name, price, color.id))
        await self.init_shop()
        await ctx.send(f'Added {color.mention} to shop #{shop_id}.')

    @commands.has_role('Staff')
    @shop.command(name='setprice', aliases=['setcost'])
    async def shop_setprice(self, ctx, item_id: int, price: int):
        item = discord.utils.get(self.all_shop_items(), id=item_id)
        if not item:
            return await ctx.send("Unknown item")
        qry = 'UPDATE shop_items SET cost=%s WHERE id=%s'
        await self.bot.db.execute(qry, (price, item_id))
        await self.init_shop()
        await ctx.send(f'Set the price of {item.name} to {price}.')

    @commands.has_role('Staff')
    @shop.command(name='toggle')
    async def shop_toggle(self, ctx, *item_ids: int):
        """Toggle an item's availabilty"""
        out = []
        for item_id in item_ids:
            item = discord.utils.get(self.all_shop_items(), id=item_id)
            qry = "UPDATE shop_items SET active = !active WHERE id=%s"
            await self.bot.db.execute(qry, (item_id,))
            out += [f'{item.name} is {"no longer" if item.active else "now"} for sale.']
        await ctx.send('\n'.join(out))
        await self.init_shop()

    @commands.has_role('Staff')
    @shop.command(name='toggleshop')
    async def shop_toggleshop(self, ctx, shop_id: int):
        """Toggle a whole shop"""
        qry = "UPDATE shops SET active = !active WHERE id=%s"
        await self.bot.db.execute(qry, (shop_id,))
        await ctx.send(f'Shop #{shop_id} is now {not item.active}')
        await self.init_shop()

    @commands.has_role('Staff')
    @shop.command(name='remove', aliases=['deleteitem'])
    async def shop_remove(self, ctx, shop_item_id: int):
        """Delete a whole shop"""
        qry = 'DELETE FROM shop_items WHERE id={shop_item_id}'
        await self.bot.db.execute(qry)
        await self.init_shop()
        await ctx.send(f'Deleted item with id #{shop_item_id}')

    @commands.guild_only()
    @commands.command(aliases=['buyitem', 'buycolor'], hidden=True)
    async def buy(self, ctx, *, item_name):
        """Buy an item from the shop"""
        item_name = item_name.lower()

        # Check if it matches an item
        item = self.get_closest_item(item_name)
        if not item:
            # Check if it matches a role
            role = fuzzy.finder(item_name, ctx.guild.roles, key=lambda t: t.name, lazy=False)
            if role:
                item = discord.utils.find(lambda x: x.data == role[0].id, self.all_shop_items())
                if not item:
                    return await ctx.send("This role isn't for sale.")
            else:
                return await ctx.send("I don't know which item you want to buy.")

        if item.type == 'color_role':
            if item.data in await self.get_owned_colors(ctx.author.id):
                return await ctx.send("You already own this color. Use `!swapcolor [color]` to change colors")

        if not item.active:
            return await ctx.send("This item isn't for sale at the moment.")

        # Handle transaction
        async with self.transaction(ctx.author.id, save=False) as profile:
            if profile.coins < item.cost:
                return await ctx.send("You don't have enough gold")
            profile.coins -= item.cost

            if item.type == 'color_role':
                role = discord.utils.get(ctx.guild.roles, id=item.data)
                if not role:
                    return await ctx.send("The role doesn't exist on the server")

                await self.bot.db.execute(f'INSERT INTO colors (user_id, color) VALUES ({ctx.author.id}, {item.data})')
                await self.swap_member_color(ctx.author, role)

                await profile.save()
                await ctx.send(f'Thanks for buying {item.get_name()}!')
            else:
                await ctx.send(f'{item.type} type items are not implemented yet.')

    async def swap_member_color(self, member, role):
        topcolor = self.get_top_color(member.roles)
        if topcolor:
            await member.remove_roles(topcolor)

        await member.add_roles(role)

    @basic_cooldown(79200)
    @commands.guild_only()
    @commands.command(aliases=['daily'])
    async def dailies(self, ctx, *, receiver: discord.Member=None):
        """Claim your daily gold, or give it to someone else."""
        # Prevent lock freeze
        if receiver and receiver.id == ctx.author.id:
            receiver = None

        async with self.get_lock(ctx.author.id):
            profile = await self.get_profile(ctx.author.id, ('coins', 'level'))
            amount = int(random.randint(1, 5) * (1 + .2 * (profile.level//5)) * self.gold_rate)
            if receiver:
                async with self.get_lock(receiver.id):
                    profile2 = await self.get_profile(receiver.id, ('coins', 'level'))
                    profile2.coins += amount
                    await profile2.save()
            else:
                profile.coins += amount
                await profile.save()

        if receiver:
            await ctx.send(f"You gave <@{receiver.id}> {amount} gold as daily reward.")
        else:
            await ctx.send(f"You got {amount} gold as daily reward.")

    @dailies.error
    async def dailies_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await self.bot.redis.delete(f"cooldown:{ctx.author.id}:{ctx.command.qualified_name}")
        else:
            m, s = divmod(error.retry_after, 60)
            h, m = divmod(m, 60)

            t = f"{h:.0f} hour(s)" if h else f"{m:.0f} minute(s) and {s:.0f} second(s)" if m else f"{s:.0f} second(s)"
            msg = "You already collected your dailies.\nTry again in " + t

            await ctx.send(msg)

    async def get_owned_colors(self, user_id):
        owned = [i[0] for i in await self.bot.db.fetch(f'SELECT color FROM colors WHERE user_id={user_id}')]
        return owned

    @commands.guild_only()
    @commands.command(aliases=['colors', 'setcolor', 'swapcolor', 'setcolour', 'swapcolour'])
    async def colours(self, ctx, *, colour=None):
        """Display your owned colors, or swap your color for a previously owned one."""
        owned = await self.get_owned_colors(ctx.author.id)
        if colour:
            role = discord.utils.find(lambda x: colour.lower() in x.name.lower(), ctx.guild.roles)
            if not role:
                return await ctx.send("This isn't a valid color")
            if role.id in owned:
                topcolor = self.get_top_color(ctx.author.roles)
                if topcolor:
                    await ctx.author.remove_roles(topcolor)
                await ctx.author.add_roles(role)
                await ctx.send(f"I'll swap your color to <@&{role.id}>")
        else:
            if owned:
                await ctx.send("You own the following colors:\n"+'\n'.join([f"<@&{role}>" for role in owned]))
            else:
                await ctx.send("You don't own any colors at the moment.")

    @commands.guild_only()
    @commands.command(aliases=['wallet', 'gold', 'money', 'coins'])
    async def balance(self, ctx, *, member: discord.Member = None):
        """Check how much gold you have"""
        if member is None:
            member = ctx.author

        profile = await self.get_profile(member.id, ('coins',))

        await ctx.send(embed=discord.Embed(title=f"{member.display_name} has {profile.coins} gold"))

    @commands.guild_only()
    @commands.command(aliases=['sendmoney', 'pay', 'tip'])
    async def givemoney(self, ctx, receiver: discord.Member = None, amount: int = 0):
        """Send some gold to someone"""
        if receiver is None:
            return await ctx.send("I don't know who you want to give money to.")
        if amount <= 0:
            return await ctx.send('Please provide an amount above 0.')

        sender = await self.get_profile(ctx.author.id, ('coins',))

        if sender.coins < amount:
            return await ctx.send("You don't have enough gold to transfer that much.")

        await ctx.send(embed=discord.Embed(description=f"Are you sure you want to send {amount}g to {receiver}? `y / n`"))
        response = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id)

        if 'y' in response.content.lower():
            async with self.get_lock(ctx.author.id):
                sender = await self.get_profile(ctx.author.id, ('coins',))
                if sender.coins < amount:
                    return await ctx.send("You somehow don't have the funds to do this anymore.")
                sender.coins -= amount
                await sender.save(self.bot.db)
            async with self.get_lock(receiver.id):
                taker = await self.get_profile(receiver.id, ('coins',))
                taker.coins += amount
                await taker.save(self.bot.db)
            await ctx.send(embed=discord.Embed(description=f"You sent {receiver} {amount}g."))
        else:
            return await ctx.send("Transfer cancelled.")

    async def get_inventory(self, user_id):
        query = "SELECT item.* FROM inventory inv " \
                "INNER JOIN items item ON inv.item_id = item.id " \
                f"WHERE inv.user_id = %s"
        items = await self.bot.db.fetchdicts(query, (user_id,))
        return items

    @commands.command(aliases=['inv'])
    async def inventory(self, ctx, user:discord.User = None):
        items = await self.get_inventory(ctx.author.id)
        items = [f'<:bs:{item["icon"]}>' for item in items]
        await ctx.send(' '.join(items))

    @commands.command()
    async def buffs(self, ctx, *, user: discord.User = None):
        user = user or ctx.author
        await ctx.send(', '.join([buff.name async for buff in self.get_buffs(user.id)] or ['None']))


def setup(bot):
    bot.add_cog(Economy(bot))
