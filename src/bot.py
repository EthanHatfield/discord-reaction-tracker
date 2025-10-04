import discord
from discord.ext import commands
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
intents.guilds = True  # For server-wide features

# Initialize bot and tracker
class ReactionBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Fetch all guilds to ensure proper cache
        self.guilds_cache = {guild.id: await guild.fetch_channels() for guild in self.guilds}

bot = ReactionBot(command_prefix="!", intents=intents, help_command=None)  # Disable the default help command
reaction_tracker = ReactionTracker()

@bot.event
async def on_ready():
    """Handle bot startup."""
    if bot.user:
        print(f"Bot is ready! Logged in as {bot.user.name} ({bot.user.id})")
    else:
        print("Bot is ready but user information is not available!")
    print("-------------------")
    
    # Start scanning in all guilds
    for guild in bot.guilds:
        print(f"Starting scan in guild: {guild.name}")
        await reaction_tracker.start_background_scanning(guild)
    
    await bot.change_presence(activity=discord.Game(name="tracking reactions | !help"))

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
    """Handle command errors."""
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send(" You dont have permission to use this command.")
    elif isinstance(error, commands.errors.CommandNotFound):
        await ctx.send(" Unknown command. Use !help to see available commands.")
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send(" Missing required argument. Use !help to see command usage.")
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.send(" Invalid argument provided. Use !help to see command usage.")
    else:
        print(f"Error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send(" An error occurred while executing the command.")

@bot.command(name="scan")
async def scan_history(ctx):
    """Start scanning message history for reactions."""
    started = await reaction_tracker.start_scanning(ctx.guild)
    if started:
        embed = discord.Embed(
            title=" Scanning Started",
            description="Started scanning message history for reactions. This may take a while.",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title=" Scanning Already in Progress",
            description="A scan is already running. Use !scan_status to check progress.",
            color=discord.Color.orange()
        )
    await ctx.send(embed=embed)

@bot.command(name="scan_stop")
async def stop_scanning(ctx):
    """Stop the scanning process."""
    await reaction_tracker.stop_scanning()
    embed = discord.Embed(
        title=" Scanning Stopped",
        description="Stopped scanning message history.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="scan_status")
async def scan_status(ctx):
    """Check scanning progress."""
    status = reaction_tracker.get_scan_status()
    if status["scanning"]:
        embed = discord.Embed(
            title=" Scanning in Progress",
            description="Currently loading message history for reaction tracking.\nThis may take a while depending on server size.",
            color=discord.Color.blue()
        )
        
        channels_added = False
        for channel_id, last_message_id in status["progress"].items():
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                channels_added = True
                embed.add_field(
                    name=f" {channel.name}",
                    value=f"Processing messages...\nLast message scanned: {last_message_id}",
                    inline=False
                )
        
        if not channels_added:
            embed.add_field(
                name="Starting Up",
                value="Initializing channel scan...",
                inline=False
            )
            
        embed.set_footer(text="Use !scan_stop to cancel the scan")
    else:
        embed = discord.Embed(
            title=" Scanner Status",
            description="No scan is currently running.\n\nUse `!scan` to start loading message history for:\n Past reactions\n Message history\n Reaction statistics",
            color=discord.Color.greyple()
        )
        
        if status["progress"]:
            embed.add_field(
                name="Last Scan Progress",
                value="Previous scan data is available. You can start a new scan with `!scan` if needed.",
                inline=False
            )
        else:
            embed.add_field(
                name="Getting Started",
                value="Run `!scan` to start tracking reactions in this server!",
                inline=False
            )
            
        embed.set_footer(text="Tip: Scanning is only needed once when the bot joins or if you want to reload history")
    
    await ctx.send(embed=embed)

@bot.command(name="report")
async def report(ctx, days: Optional[int] = 30, emoji: Optional[str] = None):
    """Generate a detailed report of reactions."""
    
    # Get the guild_id from the context
    guild_id = ctx.guild.id

    # Process emoji parameter
    if emoji is None:
        emoji = "😹"  # Default to cat with tears of joy emoji
    elif emoji.lower() == "all":
        emoji = None
    elif emoji.startswith("<") and emoji.endswith(">"):
        # This is a custom emoji, keep as is
        pass
    elif emoji.startswith(":") and emoji.endswith(":"):
        # Handle Discord emoji name format
        emoji_name = emoji.lower()
        if emoji_name in [":joy_cat:", ":cat:", ":joycat:", ":smiley_cat:"]:
            emoji = "😹"  # Cat with tears of joy emoji
        elif emoji_name == ":heart:":
            emoji = "❤️"
        elif emoji_name == ":thumbsup:":
            emoji = "👍"
        # Keep original if no mapping found
    
    # Get the report
    report_text = await reaction_tracker.get_report(guild_id=ctx.guild.id, days=days, emoji=emoji)
    
    # Split long messages if needed
    if len(report_text) > 2000:
        parts = [report_text[i:i+1900] for i in range(0, len(report_text), 1900)]
        for i, part in enumerate(parts, 1):
            await ctx.send(f"{part}\n(Part {i}/{len(parts)})")
    else:
        await ctx.send(report_text)

@bot.command(name="emoji_stats")
async def emoji_stats(ctx, days: Optional[int] = 30):
    """Show statistics about emoji usage."""
    stats = await reaction_tracker.get_emoji_stats(ctx.guild.id, days)
    
    if not stats:
        await ctx.send("No emoji statistics available for the specified timeframe!")
        return
        
    report = [" **Most Used Emojis**"]
    if days:
        report.append(f"Time period: Last {days} days\n")
        
    for emoji, count in list(stats.items())[:10]:  # Show top 10
        report.append(f"{emoji}: {count} uses")
        
    await ctx.send("\n".join(report))

@bot.command(name="help")
async def show_help(ctx):
    """Show help message."""
    commands_list = [
        "** Reaction Tracker Commands**",
        "\n**Main Commands:**",
        "`!report [days] [emoji]` - Get reaction statistics",
        "   `days` (optional): Number of days to look back (default: 30)",
        "   `emoji` (optional): Filter by emoji type (default: 😹)",
        "`!emoji_stats [days]` - Show most used emojis",
        "   `days` (optional): Number of days to look back (default: 30)",
        "\n**Report Options:**",
        " Default: Shows 😹 reactions from last 30 days",
        "  `!report`  Last 30 days of cat reactions",
        "  `!report 7`  Last week's cat reactions",
        "\n All Emojis: Use the 'all' keyword",
        "  `!report 30 all`  All reactions from last month",
        "  `!report 7 all`  All reactions from last week",
        "\n Specific Emoji: Several formats supported",
        "  `!report 30 👍`  Standard emoji",
        "  `!report 7 😹`  Cat emoji",
        "  `!report 7 ❤️`  Heart emoji",
        "  `!report 7 :custom:`  Custom server emoji",
        "\n**Examples:**",
        "`!report`  Last 30 days of cat reactions",
        "`!report 90 all`  All reactions from last 3 months",
        "`!emoji_stats`  Top 10 emojis from last 30 days",
        "`!emoji_stats 7`  Last week's most used emojis"
    ]
    
    try:
        # Send help message as DM
        await ctx.author.send("\n".join(commands_list))
        # Send acknowledgment in channel
        embed = discord.Embed(
            description=" I've sent you a DM with the help information!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        # If user has DMs disabled
        embed = discord.Embed(
            title=" Cannot send DM",
            description="I couldn't send you a DM. Please enable direct messages from server members and try again.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name="start")
async def start_tracking(ctx):
    """Start tracking reactions."""
    reaction_tracker.start_tracking()
    embed = discord.Embed(
        title=" Tracking Started",
        description="Now tracking all reactions in this server!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="stop")
async def stop_tracking(ctx):
    """Stop tracking reactions."""
    reaction_tracker.stop_tracking()
    embed = discord.Embed(
        title=" Tracking Stopped",
        description="Reaction tracking has been stopped.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="status")
async def status(ctx):
    """Check tracking status."""
    status = " Active" if reaction_tracker.tracking else " Inactive"
    embed = discord.Embed(
        title="Tracking Status",
        description=status,
        color=discord.Color.green() if reaction_tracker.tracking else discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="debug_db")
@commands.is_owner()  # Only bot owner can use this command
async def debug_db(ctx):
    """Debug command to check database contents."""
    stats = await reaction_tracker.db.get_statistics(guild_id=ctx.guild.id)  # Get all reactions for this guild
    stats_list = list(stats)  # Convert to list for counting
    
    if not stats_list:
        await ctx.send("No reactions found in database!")
        return
        
    unique_emojis = set()
    unique_users = set()
    
    for reaction in stats_list:
        unique_emojis.add(reaction["emoji"])
        unique_users.add(reaction["reactor_id"])
        unique_users.add(reaction["reactee_id"])
    
    overview = [
        "** Database Overview**",
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
    
    await ctx.send("\n".join(overview))

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
