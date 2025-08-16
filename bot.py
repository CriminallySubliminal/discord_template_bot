
import discord
from discord.ext import commands
from discord import app_commands
from discord import ui, TextStyle, Embed
import re
import json
import os





SETTINGS_FILE = "bot_settings.json"


ADMIN_ROLE_IDS = []

def load_settings():
    """Load bot settings from file"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    """Save bot settings to file"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


bot_settings = load_settings()


intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix='!', intents=intents)

class TemplateBot:
    def __init__(self):
        
        self.templates = {
            "cashout": """
🔔 **CASHOUT**
═══════════════════
 {role_mention}

 **Player**: {playerName}
 **Deposited Amount:** {loadedAmount}
 **Tag:** {cashtag}
 **Redeemed Amount:** {redeemedAmount}
 **Tip:** {tip}
 **Post Redeem Game Load:** {gameLoad}

 **To pay:** {payAmount}

═══════════════════
            """
        }
        
        
        self.template_fields = {
            "cashout": ["playerName","loadedAmount","cashtag","redeemedAmount","tip","gameLoad","payAmount",]
        }

    def parse_mention_message(self, text, bot_user_id):
        """Parse a message that mentions the bot and extract template data"""
        
        text = re.sub(f'<@!?{bot_user_id}>', '', text).strip()
        
        
        parts = text.split('\n', 1)
        if not parts:
            return None, None
            
        first_line = parts[0].strip()
        template_name = first_line.split()[0].lower() if first_line.split() else None
        
        if template_name not in self.templates:
            return None, None
        
        
        data = {}
        if len(parts) > 1:
            content = parts[1].strip()
            values = [line.strip() for line in content.split('\n') if line.strip()]
            
            
            template_fields = self.template_fields.get(template_name, [])
            for i, value in enumerate(values):
                if i < len(template_fields):
                    data[template_fields[i]] = value
        
        return template_name, data

    def fill_template(self, template_name, data, guild_id=None):
        """Fill template with provided data"""
        template = self.templates[template_name]
        
        
        placeholders = re.findall(r'\{(\w+)\}', template)
        
        
        filled_data = {}
        for placeholder in placeholders:
            if placeholder in data and data[placeholder]:
                filled_data[placeholder] = data[placeholder]
            elif placeholder == "role_mention" and guild_id:
                
                server_settings = bot_settings.get(str(guild_id), {})
                role_id = server_settings.get("notify_role_id")
                if role_id:
                    filled_data[placeholder] = f"<@&{role_id}>"
                else:
                    filled_data[placeholder] = ""
            else:
                
                filled_data[placeholder] = ""
        
        try:
            return template.format(**filled_data)
        except KeyError as e:
            return f"Error: Missing field {e}"

    def get_help_message(self):
        """Generate help message showing available templates and usage"""
        help_msg = """
🤖 **Template Bot Help**

**Usage:** Mention the bot followed by the template name and values (one per line).

**Available Templates:**
• `cashout` - For cashout notifications

**Example Usage:**
```
@TemplateBot cashout
$AAPL
$1,500
$2,000
$50
```

**Format for cashout:**
1. Mention the bot + "cashout"
2. Cash tag (e.g., $AAPL)
3. Amount to pay
4. Amount loaded
5. Tip amount (e.g., $50)

Fields are filled in order - no need to specify field names!

**Admin Commands:**
• `/set_notify_role @RoleName` - Set role to mention automatically
• `/set_command_channel 
• `/set_response_channel 
• `/remove_notify_role` - Remove automatic role mention  
• `/bot_settings` - View current settings
        """
        return help_msg


template_bot = TemplateBot()

@bot.event
async def on_ready():
    """Event triggered when bot is ready"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready to use in {len(bot.guilds)} servers')
    
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
        
        
        for command in synced:
            print(f"  - /{command.name}")
            
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    """Event triggered when a message is sent"""
    
    if message.author == bot.user:
        return
    
   
    if bot.user.mentioned_in(message):
       
        guild_id = str(message.guild.id)
        server_settings = bot_settings.get(guild_id, {})
        command_channel_id = server_settings.get("command_channel_id")
        
        
        if command_channel_id and message.channel.id != command_channel_id:
            command_channel = message.guild.get_channel(command_channel_id)
            channel_mention = command_channel.mention if command_channel else "the designated channel"
            await message.channel.send(f"❌ Please use commands in {channel_mention}")
            return
        
        
        if 'help' in message.content.lower():
            help_message = template_bot.get_help_message()
            await message.channel.send(help_message)
            return
        
        
        template_name, data = template_bot.parse_mention_message(
            message.content, 
            bot.user.id
        )
        
        if template_name is None:
            available_templates = ', '.join(template_bot.templates.keys())
            await message.channel.send(
                f"❌ Template not found or invalid format.\n\n"
                f"Available templates: {available_templates}\n"
                f"Type '@{bot.user.display_name} help' for usage instructions."
            )
            return
        
        
        result = template_bot.fill_template(template_name, data, message.guild.id)
        
      
        response_channel_id = server_settings.get("response_channel_id")
        
        if response_channel_id:
           
            response_channel = message.guild.get_channel(response_channel_id)
            if response_channel:
                await response_channel.send(result)
                await message.channel.send(f"✅ Template posted in {response_channel.mention}")
            else:
                await message.channel.send("❌ Response channel not found. Please contact an admin.")
        else:
            await message.channel.send(result)
    
    
    await bot.process_commands(message)
    
    


def parse_tip_game(s: str):
    """
    Accepts things like:
      "10,5"  -> tip=10, game=5
      "tip=10 game=5"
      "tip 10 game 5"
      "10"    -> tip=10, game=0
      ""      -> both 0
    Returns (tip:int, game:int)
    """
    s = (s or "").strip()
    if not s:
        return 0, 0
    
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        tip = int(''.join(ch for ch in parts[0] if ch.isdigit() or ch=='-') or "0")
        game = int(''.join(ch for ch in parts[1] if ch.isdigit() or ch=='-') or "0")
        return tip, game
    
    s_low = s.lower().replace("=", " ").replace("tip", " ").replace("game", " ")
    nums = [int(''.join(ch for ch in tok if ch.isdigit() or ch=='-') or "0")
            for tok in s_low.split() if any(c.isdigit() for c in tok)]
    tip = nums[0] if len(nums) >= 1 else 0
    game = nums[1] if len(nums) >= 2 else 0
    return tip, game




class CashoutModal(ui.Modal, title="Cashout Details"):
    def __init__(self, template_bot, bot_settings, guild):
        super().__init__()
        self.template_bot = template_bot
        self.bot_settings = bot_settings
        self.guild = guild

        self.player_name = ui.TextInput(
            label="Player Name", placeholder="e.g. Maria Lopez",
            required=True, max_length=64
        )
        self.cashtag = ui.TextInput(
            label="Cashtag", placeholder="e.g. $pablolose2",
            required=True, max_length=64
        )
        self.loaded_amount = ui.TextInput(
            label="Loaded Amount", placeholder="e.g. 15",
            required=True, max_length=16
        )
        self.redeemed_amount = ui.TextInput(
            label="Redeemed Amount", placeholder="e.g. 100",
            required=True, max_length=16
        )
        self.optional_tip_game = ui.TextInput(
            label="Optional: Tip, Game Load",
            placeholder="Format: (Tip, Game Load)",
            required=False, max_length=32, style=TextStyle.short
        )

        self.add_item(self.player_name)
        self.add_item(self.cashtag)
        self.add_item(self.loaded_amount)
        self.add_item(self.redeemed_amount)
        self.add_item(self.optional_tip_game)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(self.guild.id)
        server_settings = self.bot_settings.get(guild_id, {})

        def to_int(s, default=0):
            s = (s or "").strip()
            if not s: return default
            try:
                return int(''.join(ch for ch in s if ch.isdigit() or ch == '-'))
            except:
                return default

        loaded = to_int(self.loaded_amount.value, 0)
        redeemed = to_int(self.redeemed_amount.value, 0)
        tip, game = parse_tip_game(self.optional_tip_game.value)

        pay_amount = redeemed - tip - game
        if pay_amount < 0:
            pay_amount = 0

        data = {
            "playerName": self.player_name.value.strip(),
            "loadedAmount": str(loaded),
            "cashtag": self.cashtag.value.strip(),
            "redeemedAmount": str(redeemed),
            "tip": str(tip) if tip else "",
            "gameLoad": str(game) if game else "",
            "payAmount": str(pay_amount),
        }

        
        text_block = self.template_bot.fill_template("cashout", data, self.guild.id)

        
        response_channel_id = server_settings.get("response_channel_id")
        if response_channel_id:
            channel = self.guild.get_channel(response_channel_id)
            if channel:
                
                notify_role_id = server_settings.get("notify_role_id")
                if notify_role_id:
                    await channel.send(f"<@&{notify_role_id}>")
                await channel.send(text_block)
                await interaction.response.send_message(
                    f"✅ Cashout posted in {channel.mention}", ephemeral=True
                )
                return

        
        notify_role_id = server_settings.get("notify_role_id")
        if notify_role_id:
            await interaction.channel.send(f"<@&{notify_role_id}>")
        await interaction.channel.send(text_block)
        await interaction.response.send_message("✅ Cashout posted.", ephemeral=True)












def is_bot_admin(member: discord.Member):
    """Check if a member is allowed to run bot admin commands"""
    guild_id = str(member.guild.id)
    server_settings = bot_settings.get(guild_id, {})
    allowed_roles = server_settings.get("admin_role_ids", [])

    
    if not allowed_roles:
        return member.guild_permissions.administrator

    
    return (
        member.guild_permissions.administrator
        or any(role.id in allowed_roles for role in member.roles))




@bot.tree.command(name="set_admin_roles", description="Set which roles are allowed to use bot admin commands")
@app_commands.describe(
    role1="First admin role",
    role2="Second admin role (optional)",
    role3="Third admin role (optional)",
    role4="Fourth admin role (optional)",
    role5="Fifth admin role (optional)"
)
async def set_admin_roles(
    interaction: discord.Interaction,
    role1: discord.Role,
    role2: discord.Role = None,
    role3: discord.Role = None,
    role4: discord.Role = None,
    role5: discord.Role = None
):
    
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need **Administrator** permissions to set admin roles.",
            ephemeral=True
        )
        return

    roles = [r for r in (role1, role2, role3, role4, role5) if r]
    guild_id = str(interaction.guild.id)
    bot_settings.setdefault(guild_id, {})
    bot_settings[guild_id]["admin_role_ids"] = [role.id for role in roles]
    save_settings(bot_settings)

    await interaction.response.send_message(
        f"✅ Admin roles set: {', '.join(role.mention for role in roles)}",
        ephemeral=True
    )



@bot.tree.command(name="set_notify_role", description="Set the role to mention for cashout notifications")
@app_commands.describe(role="Role to mention in cashout messages")
async def set_notify_role(interaction: discord.Interaction, role: discord.Role):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    bot_settings.setdefault(guild_id, {})

    if "notify_role_id" in bot_settings[guild_id]:
        await interaction.response.send_message(
            f"❌ Notify Role already set! Clear using command   `/remove_notify_role`   to set a new one.",
            ephemeral=True
        )
        return

    bot_settings[guild_id]["notify_role_id"] = role.id
    save_settings(bot_settings)

    await interaction.response.send_message(
        f"✅ Notification role set to {role.mention}",
        ephemeral=True
    )



@bot.tree.command(name="remove_notify_role", description="Remove the automatic role mention from cashout messages")
async def remove_notify_role(interaction: discord.Interaction):

    if not is_bot_admin(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    server_settings = bot_settings.get(guild_id, {})

    if "notify_role_id" in server_settings:
        del server_settings["notify_role_id"]
        save_settings(bot_settings)
        await interaction.response.send_message(
            "✅ Automatic role mention removed.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ No notification role is currently set.",
            ephemeral=True
        )



@bot.tree.command(name="set_command_channel", description="Set the channel where bot listens for commands")
@app_commands.describe(channel="Channel for commands")
async def set_command_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    bot_settings.setdefault(guild_id, {})
    bot_settings[guild_id]["command_channel_id"] = channel.id
    save_settings(bot_settings)

    await interaction.response.send_message(
        f"✅ Command channel set to {channel.mention}",
        ephemeral=True
    )



@bot.tree.command(name="set_response_channel", description="Set the channel where cashout templates are posted")
@app_commands.describe(channel="Channel for cashout templates")
async def set_response_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    bot_settings.setdefault(guild_id, {})
    bot_settings[guild_id]["response_channel_id"] = channel.id
    save_settings(bot_settings)

    await interaction.response.send_message(
        f"✅ Response channel set to {channel.mention}",
        ephemeral=True
    )


@bot.tree.command(name="bot_settings", description="View current bot settings for this server")
async def view_settings(interaction: discord.Interaction):
    
    await interaction.response.defer(ephemeral=True)

    if not is_bot_admin(interaction.user):
        await interaction.followup.send(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    server_settings = bot_settings.get(guild_id, {})

    
    admin_role_ids = server_settings.get("admin_role_ids", [])
    if admin_role_ids:
        admin_roles_text = ", ".join(
            interaction.guild.get_role(rid).mention if interaction.guild.get_role(rid) else f"(deleted role {rid})"
            for rid in admin_role_ids
        )
    else:
        admin_roles_text = "❌ None set (defaults to Discord Administrator permission)"

    
    notify_role_id = server_settings.get("notify_role_id")
    notify_role_mention = interaction.guild.get_role(notify_role_id).mention if notify_role_id else "Not set"

    
    command_channel_id = server_settings.get("command_channel_id")
    command_channel_mention = interaction.guild.get_channel(command_channel_id).mention if command_channel_id else "Any channel"

    
    response_channel_id = server_settings.get("response_channel_id")
    response_channel_mention = interaction.guild.get_channel(response_channel_id).mention if response_channel_id else "Same as command channel"

    await interaction.followup.send(
        f"**Bot Settings for {interaction.guild.name}:**\n\n"
        f"📢 **Notify Role:** {notify_role_mention}\n"
        f"🛡 **Admin Roles:** {admin_roles_text}\n"
        f"📝 **Command Channel:** {command_channel_mention}\n"
        f"📢 **Response Channel:** {response_channel_mention}",
        ephemeral=True
    )








@bot.tree.command(name="cashout", description="Open a form to generate a cashout template")
async def slash_cashout(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    server_settings = bot_settings.get(guild_id, {})
    command_channel_id = server_settings.get("command_channel_id")

    if command_channel_id and interaction.channel.id != command_channel_id:
        command_channel = interaction.guild.get_channel(command_channel_id)
        channel_mention = command_channel.mention if command_channel else "the designated channel"
        await interaction.response.send_message(
            f"❌ Please use this command in {channel_mention}", ephemeral=True
        )
        return

    await interaction.response.send_modal(CashoutModal(template_bot, bot_settings, interaction.guild))



@bot.tree.command(name="help", description="Show bot help and usage instructions")
async def slash_help(interaction: discord.Interaction):
    """Slash command for help"""
    help_message = template_bot.get_help_message()
    await interaction.response.send_message(help_message, ephemeral=True)

@bot.tree.command(name="templates", description="List all available templates")
async def slash_templates(interaction: discord.Interaction):
    """Show available templates"""
    templates_list = "\n".join([f"• `{name}`" for name in template_bot.templates.keys()])
    message = f"**Available Templates:**\n{templates_list}\n\nUse `/cashout` to create a cashout template!"
    await interaction.response.send_message(message, ephemeral=True)







@bot.command(name='help_template')
async def help_command(ctx):
    """Help command"""
    help_message = template_bot.get_help_message()
    await ctx.send(help_message)


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return  
    
    print(f"An error occurred: {error}")
    await ctx.send("An error occurred while processing your request.")



