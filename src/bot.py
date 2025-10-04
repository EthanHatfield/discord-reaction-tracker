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

# Initialize bot and tracker
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
reaction_tracker = ReactionTracker()

@bot.event
async def on_ready():
    """Handle bot startup."""
    print(f'Bot is ready! Logged in as {bot.user.name} ({bot.user.id})')
    print('-------------------')
    await bot.change_presence(activity=discord.Game(name="tracking reactions | !help"))

@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction events."""
    if user.bot:
        return
    
    message = reaction.message
    await reaction_tracker.track_reaction(
        reactor_id=user.id,
        reactee_id=message.author.id,
        message_id=message.id,
        channel_id=message.channel.id,
        emoji=str(reaction.emoji)
    )

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.errors.CommandNotFound):
        await ctx.send("❌ Unknown command. Use !help to see available commands.")
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument. Use !help to see command usage.")
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.send("❌ Invalid argument provided. Use !help to see command usage.")
    else:
        print(f'Error: {error}')
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send("❌ An error occurred while executing the command.")

@bot.command()
async def help(ctx):
    """Show help message."""
    commands_list = [
        "**🤖 Reaction Tracker Commands**",
        "\n**Scanning Commands:**",
        "`!scan` - Start scanning message history for reactions",
        "`!scan_status` - Check scanning progress",
        "`!scan_stop` - Stop the scanning process",
        "\n**Report Commands:**",
        "`!report [days] [emoji]` - Get a detailed report",
        "  • `days` (optional): Number of days to look back (e.g., 7 for last week)",
        "  • `emoji` (optional): Filter by specific emoji",
        "`!emoji_stats [days]` - Show most used emojis",
        "  • `days` (optional): Number of days to look back",
        "\nExamples:",
        "`!report` - All-time reaction report",
        "`!report 7` - Last week's reactions",
        "`!report 30 👍` - Last month's 👍 reactions",
        "`!emoji_stats 7` - Most used emojis in the last week"
    ]
    await ctx.send("\n".join(commands_list))

@bot.command(name="scan")
async def scan_history(ctx):
    """Start scanning message history for reactions."""
    async def progress_callback(channel, message):
        if message.id % 100 == 0:  # Update progress every 100 messages
            await ctx.send(f"Scanning channel {channel.name}: {message.created_at}")

    started = await reaction_tracker.start_scanning(ctx.guild, progress_callback)
    if started:
        embed = discord.Embed(
            title="🔍 Scanning Started",
            description="Started scanning message history for reactions. This may take a while.",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="⚠️ Scanning Already in Progress",
            description="A scan is already running. Use !scan_status to check progress.",
            color=discord.Color.orange()
        )
    await ctx.send(embed=embed)

@bot.command(name="scan_stop")
async def stop_scanning(ctx):
    """Stop the scanning process."""
    await reaction_tracker.stop_scanning()
    embed = discord.Embed(
        title="🛑 Scanning Stopped",
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
            title="🔍 Scanning in Progress",
            description="Currently scanning message history.",
            color=discord.Color.blue()
        )
        # Add progress for each channel
        for channel_id, last_message_id in status["progress"].items():
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name=channel.name,
                    value=f"Last message ID: {last_message_id}",
                    inline=False
                )
    else:
        embed = discord.Embed(
            title="💤 Scanner Idle",
            description="No scan currently in progress.",
            color=discord.Color.grey()
        )
    await ctx.send(embed=embed)

@bot.command(name="report")
async def report(ctx, days: Optional[int] = None, emoji: Optional[str] = None):
    """
    Generate a detailed report.
    
    Args:
        days: Optional number of days to look back
        emoji: Optional emoji to filter by
    """
    report_text = await reaction_tracker.get_report(days, emoji)
    
    # Split long messages if needed
    if len(report_text) > 2000:
        parts = [report_text[i:i+1900] for i in range(0, len(report_text), 1900)]
        for i, part in enumerate(parts, 1):
            await ctx.send(f"{part}\n(Part {i}/{len(parts)})")
    else:
        await ctx.send(report_text)

@bot.command(name="emoji_stats")
async def emoji_stats(ctx, days: Optional[int] = None):
    """Show statistics about emoji usage."""
    stats = await reaction_tracker.get_emoji_stats(days)
    
    if not stats:
        await ctx.send("No emoji statistics available for the specified timeframe!")
        return
        
    report = ["📊 **Most Used Emojis**"]
    if days:
        report.append(f"Time period: Last {days} days\n")
        
    for emoji, count in list(stats.items())[:10]:  # Show top 10
        report.append(f"{emoji}: {count} uses")
        
    await ctx.send("\n".join(report))

@bot.command(name="start")
async def start_tracking(ctx):
    """Start tracking reactions."""
    reaction_tracker.start_tracking()
    embed = discord.Embed(
        title="🎯 Tracking Started",
        description="Now tracking all reactions in this server!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="stop")
async def stop_tracking(ctx):
    """Stop tracking reactions."""
    reaction_tracker.stop_tracking()
    embed = discord.Embed(
        title="🛑 Tracking Stopped",
        description="Reaction tracking has been stopped.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="report")
async def report(ctx, days: Optional[int] = None, emoji: Optional[str] = None):
    """
    Generate a detailed report.
    
    Args:
        days: Optional number of days to look back
        emoji: Optional emoji to filter by
    """
    report_text = reaction_tracker.get_report(days, emoji)
    
    # Split long messages if needed
    if len(report_text) > 2000:
        parts = [report_text[i:i+1900] for i in range(0, len(report_text), 1900)]
        for i, part in enumerate(parts, 1):
            await ctx.send(f"{part}\n(Part {i}/{len(parts)})")
    else:
        await ctx.send(report_text)

@bot.command(name="emoji_stats")
async def emoji_stats(ctx, days: Optional[int] = None):
    """Show statistics about emoji usage."""
    stats = reaction_tracker.get_emoji_stats(days)
    
    if not stats:
        await ctx.send("No emoji statistics available for the specified timeframe!")
        return
        
    report = ["📊 **Most Used Emojis**"]
    if days:
        report.append(f"Time period: Last {days} days\n")
        
    for emoji, count in list(stats.items())[:10]:  # Show top 10
        report.append(f"{emoji}: {count} uses")
        
    await ctx.send("\n".join(report))

@bot.command(name="status")
async def status(ctx):
    """Check tracking status."""
    status = "🟢 Active" if reaction_tracker.tracking else "🔴 Inactive"
    embed = discord.Embed(
        title="Tracking Status",
        description=status,
        color=discord.Color.green() if reaction_tracker.tracking else discord.Color.red()
    )
    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    if not config.BOT_TOKEN:
        print("Error: Bot token not configured!")
        exit(1)
        
    try:
        bot.run(config.BOT_TOKEN)
    except discord.LoginFailure:
        print("Error: Invalid bot token!")
    except Exception as e:
        print(f"Error: {e}")