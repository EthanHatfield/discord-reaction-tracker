import discord
from discord.ext import commands
from discord import app_commands
import traceback
from datetime import datetime
from typing import Optional
from tracker import ReactionTracker
import config

# Set up intents
intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
intents.message_content = True
intents.guilds = True

# Bot class with slash command support
class ReactionBot(commands.Bot):
    async def setup_hook(self) -> None:
        self.guilds_cache = {guild.id: await guild.fetch_channels() for guild in self.guilds}
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

bot = ReactionBot(command_prefix="$", intents=intents, help_command=None)  # Use uncommon prefix to avoid conflicts
reaction_tracker = ReactionTracker()

@bot.event
async def on_ready():
    """Handle bot startup."""
    if bot.user:
        print(f"Bot is ready! Logged in as {bot.user.name} ({bot.user.id})")
    else:
        print("Bot is ready but user information is not available!")
    print("-------------------")
    
    for guild in bot.guilds:
        print(f"Starting scan in guild: {guild.name}")
        await reaction_tracker.start_background_scanning(guild)
    
    await bot.change_presence(activity=discord.Game(name="tracking reactions | /help"))

@bot.event
async def on_guild_join(guild):
    """Automatically start scanning when joining a new server."""
    print(f"Joined new guild: {guild.name}")
    await reaction_tracker.start_background_scanning(guild)

@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction events."""
    if user.bot:
        return
    
    message = reaction.message
    await reaction_tracker.track_reaction(
        user.id,
        message.author.id,
        message.id,
        message.channel.id,
        message.guild.id,
        str(reaction.emoji)
    )

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors - we only use slash commands now, so ignore prefix command errors."""
    # Since we only use slash commands, silently ignore all prefix command errors
    if isinstance(error, commands.errors.CommandNotFound):
        # Don't respond to unknown prefix commands
        return
    
    # Log other errors but don't respond to user
    if not isinstance(error, (commands.errors.CheckFailure, commands.errors.MissingRequiredArgument, commands.errors.BadArgument)):
        print(f"Command error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)

# Slash Commands
@bot.tree.command(name="help", description="Show help information about bot commands")
async def show_help_slash(interaction: discord.Interaction):
    """Show help message."""
    embed = discord.Embed(
        title="🔧 Reaction Tracker Commands",
        description="Use these slash commands to interact with the bot:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📊 Main Commands",
        value="`/report [days] [emoji]` - Get reaction statistics\n`/scan` - Start scanning message history\n`/emoji_stats [days]` - Show emoji usage statistics",
        inline=False
    )
    embed.add_field(
        name="⚙️ Control Commands", 
        value="`/start` - Start tracking\n`/stop` - Stop tracking\n`/status` - Check status",
        inline=False
    )
    embed.add_field(
        name="🌟 Examples",
        value="`/report` - Last 30 days of 😹 reactions\n`/report days:7 emoji:all` - All reactions from last week",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="scan", description="Start scanning message history for reactions")
async def scan_history_slash(interaction: discord.Interaction):
    """Start scanning message history for reactions."""
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
        
    started = await reaction_tracker.start_scanning(interaction.guild)
    if started:
        embed = discord.Embed(
            title="📊 Scanning Started",
            description="Started scanning message history for reactions. This may take a while.",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="⚠️ Scanning Already in Progress",
            description="A scan is already running. Use `/scan_status` to check progress.",
            color=discord.Color.orange()
        )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="scan_status", description="Check scanning progress")
async def scan_status_slash(interaction: discord.Interaction):
    """Check scanning progress."""
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
        
    status = reaction_tracker.get_scan_status()
    if status["scanning"]:
        embed = discord.Embed(
            title="📊 Scanning in Progress",
            description="Currently loading message history for reaction tracking.\nThis may take a while depending on server size.",
            color=discord.Color.blue()
        )
        
        channels_added = False
        for channel_id, last_message_id in status["progress"].items():
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                channels_added = True
                embed.add_field(
                    name=f"📝 {channel.name}",
                    value=f"Processing messages...\nLast message scanned: {last_message_id}",
                    inline=False
                )
        
        if not channels_added:
            embed.add_field(
                name="Starting Up",
                value="Initializing channel scan...",
                inline=False
            )
            
        embed.set_footer(text="Use /scan_stop to cancel the scan")
    else:
        embed = discord.Embed(
            title="📊 Scanner Status",
            description="No scan is currently running.\n\nUse `/scan` to start loading message history for:\n✅ Past reactions\n✅ Message history\n✅ Reaction statistics",
            color=discord.Color.greyple()
        )
        
        if status["progress"]:
            embed.add_field(
                name="Last Scan Progress",
                value="Previous scan data is available. You can start a new scan with `/scan` if needed.",
                inline=False
            )
        else:
            embed.add_field(
                name="Getting Started",
                value="Run `/scan` to start tracking reactions in this server!",
                inline=False
            )
            
        embed.set_footer(text="Tip: Scanning is only needed once when the bot joins or if you want to reload history")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="scan_stop", description="Stop the scanning process")
async def stop_scanning_slash(interaction: discord.Interaction):
    """Stop the scanning process."""
    await reaction_tracker.stop_scanning()
    embed = discord.Embed(
        title="🛑 Scanning Stopped",
        description="Stopped scanning message history.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="report", description="Generate a detailed report of reactions")
@app_commands.describe(
    days="Number of days to look back (default: 30)",
    emoji="Emoji to filter by (default: 😹, use 'all' for all emojis)"
)
async def report_slash(interaction: discord.Interaction, days: Optional[int] = 30, emoji: Optional[str] = None):
    """Generate a detailed report of reactions."""
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    # Process emoji parameter
    if emoji is None:
        emoji = "😹"
    elif emoji.lower() == "all":
        emoji = None
    
    report_text = await reaction_tracker.get_report(guild_id=interaction.guild.id, days=days, emoji=emoji)
    
    if len(report_text) > 2000:
        parts = [report_text[i:i+1900] for i in range(0, len(report_text), 1900)]
        await interaction.response.send_message(f"{parts[0]}\n(Part 1/{len(parts)})")
        for i, part in enumerate(parts[1:], 2):
            await interaction.followup.send(f"{part}\n(Part {i}/{len(parts)})")
    else:
        await interaction.response.send_message(report_text)

@bot.tree.command(name="emoji_stats", description="Show statistics about emoji usage")
@app_commands.describe(days="Number of days to look back (default: 30)")
async def emoji_stats_slash(interaction: discord.Interaction, days: Optional[int] = 30):
    """Show statistics about emoji usage."""
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
        
    stats = await reaction_tracker.get_emoji_stats(interaction.guild.id, days)
    
    if not stats:
        await interaction.response.send_message("No emoji statistics available for the specified timeframe!")
        return
        
    report = ["📊 **Most Used Emojis**"]
    if days:
        report.append(f"Time period: Last {days} days\n")
        
    for emoji, count in list(stats.items())[:10]:
        report.append(f"{emoji}: {count} uses")
        
    await interaction.response.send_message("\n".join(report))

@bot.tree.command(name="start", description="Start tracking reactions")
async def start_tracking_slash(interaction: discord.Interaction):
    """Start tracking reactions."""
    reaction_tracker.start_tracking()
    embed = discord.Embed(
        title="✅ Tracking Started",
        description="Now tracking all reactions in this server!",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Stop tracking reactions")
async def stop_tracking_slash(interaction: discord.Interaction):
    """Stop tracking reactions."""
    reaction_tracker.stop_tracking()
    embed = discord.Embed(
        title="🛑 Tracking Stopped",
        description="Reaction tracking has been stopped.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status", description="Check tracking status")
async def status_slash(interaction: discord.Interaction):
    """Check tracking status."""
    status = "✅ Active" if reaction_tracker.tracking else "❌ Inactive"
    embed = discord.Embed(
        title="Tracking Status",
        description=status,
        color=discord.Color.green() if reaction_tracker.tracking else discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="debug_db", description="[Owner only] Debug command to check database contents")
@app_commands.default_permissions(administrator=True)
async def debug_db_slash(interaction: discord.Interaction):
    """Debug command to check database contents."""
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
        
    # Check if user is bot owner
    app_info = await bot.application_info()
    if interaction.user.id != app_info.owner.id:
        await interaction.response.send_message("❌ This command is only available to the bot owner.", ephemeral=True)
        return
    
    stats = await reaction_tracker.db.get_statistics(guild_id=interaction.guild.id)
    stats_list = list(stats)
    
    if not stats_list:
        await interaction.response.send_message("No reactions found in database!", ephemeral=True)
        return
        
    unique_emojis = set()
    unique_users = set()
    
    for reaction in stats_list:
        unique_emojis.add(reaction["emoji"])
        unique_users.add(reaction["reactor_id"])
        unique_users.add(reaction["reactee_id"])
    
    overview = [
        "📋 **Database Overview**",
        f"Total reactions: {len(stats_list)}",
        f"Unique emojis: {len(unique_emojis)}",
        f"Users involved: {len(unique_users)}\n",
        "Top 10 emojis:"
    ]
    
    emoji_counts = {}
    for reaction in stats_list:
        emoji = reaction["emoji"]
        emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1
    
    sorted_emojis = sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for emoji, count in sorted_emojis:
        overview.append(f"{emoji}: {count}")
    
    await interaction.response.send_message("\n".join(overview), ephemeral=True)

# Run the bot
if __name__ == "__main__":
    if not config.TOKEN:
        print("❌ Error: Bot token not found!")
        print("Please create a .env file with your DISCORD_BOT_TOKEN")
        print("Example: DISCORD_BOT_TOKEN=your_token_here")
        raise ValueError("Bot token not found. Please set the DISCORD_BOT_TOKEN environment variable in .env file.")
    
    print("🚀 Starting Discord Reaction Tracker Bot...")
    print(f"📁 Database location: reactions.db")
    print(f"⏰ Reaction timeframe: {config.REACTION_TIMEFRAME} seconds")
    
    try:
        bot.run(config.TOKEN)
    except discord.LoginFailure:
        print("❌ Error: Invalid bot token. Please check your DISCORD_BOT_TOKEN in .env file.")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        raise