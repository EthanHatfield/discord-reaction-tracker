from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Any, DefaultDict
import asyncio
import discord
from database import Database
import config

class ReactionTracker:
    def __init__(self):
        self.db = Database()
        self.scanning = False
        self.scan_progress: DefaultDict[int, int] = defaultdict(int)
        self.scan_task: Optional[asyncio.Task] = None
        self.reactions: List[Dict[str, Any]] = []  # In-memory storage for reactions
        self.tracking = True  # Tracking state
        self.retry_delay = 60  # Initial retry delay in seconds
        self.max_retry_delay = 3600  # Maximum retry delay (1 hour)
        self.rate_limit_hits: DefaultDict[int, int] = defaultdict(int)  # Track rate limit hits per channel
        self._background_task: Optional[asyncio.Task] = None
        
    def start_tracking(self) -> None:
        """Start tracking reactions."""
        self.tracking = True

    def stop_tracking(self) -> None:
        """Stop tracking reactions."""
        self.tracking = False
        
    async def track_reaction(self, reactor_id: int, reactee_id: int, message_id: int, 
                           channel_id: int, guild_id: int, emoji: str, timestamp: Optional[datetime] = None):
        """Track a new reaction."""
        await self.db.add_reaction(
            reactor_id=reactor_id,
            reactee_id=reactee_id,
            message_id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            emoji=emoji,
            timestamp=timestamp
        )

    async def scan_channel_history(self, channel: discord.TextChannel, guild_id: Optional[int] = None, progress_callback=None):
        """Scan a channel's message history for reactions."""
        # Strict type checking
        if not isinstance(channel, discord.TextChannel):
            print(f"Error: Expected TextChannel object, got {type(channel)} for {channel}")
            return
            
        # Ensure we have a valid guild_id
        if guild_id is None:
            if not hasattr(channel, 'guild'):
                print(f"Error: Channel {channel.name} has no guild attribute")
                return
            guild_id = channel.guild.id
        
        last_message_id = await self.db.get_scan_progress(channel.id)
        retry_count = self.rate_limit_hits[channel.id]
        current_delay = min(self.retry_delay * (2 ** retry_count), self.max_retry_delay)
        
        # Convert message ID to discord.Object if we have one
        after_object = discord.Object(id=last_message_id) if last_message_id else None
        
        try:
            async for message in channel.history(limit=None, after=after_object):
                if not self.scanning:
                    break
                    
                for reaction in message.reactions:
                    try:
                        async for user in reaction.users():
                            if user.bot:
                                continue
                                
                            await self.track_reaction(
                                user.id,
                                message.author.id,
                                message.id,
                                channel.id,
                                guild_id,
                                str(reaction.emoji),
                                message.created_at
                            )
                            
                            # Successful request, reduce retry count
                            if retry_count > 0:
                                self.rate_limit_hits[channel.id] = max(0, retry_count - 1)
                            
                            # Dynamic rate limit handling
                            await asyncio.sleep(0.1 * (2 ** retry_count))
                            
                    except discord.errors.HTTPException as e:
                        if e.code == 429:  # Rate limit hit
                            self.rate_limit_hits[channel.id] += 1
                            retry_count = self.rate_limit_hits[channel.id]
                            await asyncio.sleep(current_delay)
                            continue
                        raise
                
                await self.db.update_scan_progress(channel.id, message.id)
                self.scan_progress[channel.id] = message.id
                
        except discord.errors.Forbidden:
            print(f"No access to channel {channel.name}")
        except Exception as e:
            print(f"Error scanning channel {channel.name}: {e}")

    async def start_background_scanning(self, guild: discord.Guild):
        """Start the background scanning process."""
        if not isinstance(guild, discord.Guild):
            print(f"Error: Expected Guild object, got {type(guild)}")
            return False
            
        if self._background_task and not self._background_task.done():
            return False  # Already running
            
        self.scanning = True
        self._background_task = asyncio.create_task(self._background_scan_loop(guild))
        return True
        
    async def _background_scan_loop(self, guild: discord.Guild):
        """Continuously scan for reactions in the background."""
        while True:
            try:
                # Ensure we have a valid guild object
                if not isinstance(guild, discord.Guild):
                    print(f"Error: Expected Guild object, got {type(guild)}")
                    return
                
                # Fetch and filter text channels
                try:
                    channels = await guild.fetch_channels()
                    text_channels = [
                        channel for channel in channels 
                        if isinstance(channel, discord.TextChannel)
                    ]
                except Exception as e:
                    print(f"Error fetching channels for guild {guild.name}: {e}")
                    await asyncio.sleep(300)  # Wait 5 minutes before retry
                    continue
                
                # Process each text channel
                for channel in text_channels:
                    if not self.scanning:
                        return
                    
                    if not isinstance(channel, discord.TextChannel):
                        print(f"Warning: Skipping invalid channel type: {type(channel)}")
                        continue
                        
                    try:
                        await self.scan_channel_history(channel, guild.id)
                    except Exception as e:
                        print(f"Error scanning {channel.name}: {e}")
                        continue
                        
                # All channels scanned, wait before next cycle
                await asyncio.sleep(3600)  # Wait an hour between full scans
                
            except Exception as e:
                print(f"Background scan error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
                continue
    
    async def start_scanning(self, guild: discord.Guild):
        """Start scanning the server's message history."""
        if self.scanning:
            return False
        
        await self.start_background_scanning(guild)
        return True
        
    async def stop_scanning(self):
        """Stop the scanning process."""
        self.scanning = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

    def get_scan_status(self):
        """Get the current scanning status."""
        return {
            "scanning": self.scanning,
            "progress": dict(self.scan_progress)
        }

    async def get_report(self, guild_id: int, days: Optional[int] = None, emoji: Optional[str] = None) -> str:
        """Generate a detailed report of reaction statistics."""
        start_time = None
        if days:
            start_time = datetime.now() - timedelta(days=days)

        report_lines: List[str] = []

        stats = await self.db.get_statistics(guild_id=guild_id, start_time=start_time, emoji=emoji)
        if not stats:
            return "No reactions found for the specified criteria!"

        # Process statistics
        reactor_stats: Dict[int, Dict[str, Any]] = {}
        reactee_stats: Dict[int, Dict[str, Any]] = {}

        for row in stats:
            reactor_id = row["reactor_id"]
            reactee_id = row["reactee_id"]
            emoji = row["emoji"]
            count = row["count"]

            # Initialize if not exists
            if reactor_id not in reactor_stats:
                reactor_stats[reactor_id] = {"given": 0, "emojis": {}}
            if reactee_id not in reactee_stats:
                reactee_stats[reactee_id] = {"received": 0, "emojis": {}}

            # Update stats
            reactor_stats[reactor_id]["given"] += count
            reactor_stats[reactor_id]["emojis"][emoji] = reactor_stats[reactor_id]["emojis"].get(emoji, 0) + count
            
            reactee_stats[reactee_id]["received"] += count
            reactee_stats[reactee_id]["emojis"][emoji] = reactee_stats[reactee_id]["emojis"].get(emoji, 0) + count

        # Build report
        report_lines = ["📊 **Reaction Tracking Report**"]
        
        if days:
            report_lines.append(f"Time period: Last {days} days")
        if emoji:
            report_lines.append(f"Filtered by emoji: {emoji}")
        report_lines.append("")

        # Top 5 reaction givers
        report_lines.append("**🎯 Top 5 Reaction Givers:**")
        sorted_reactors = sorted(
            [(uid, data) for uid, data in reactor_stats.items()],
            key=lambda x: x[1]["given"],
            reverse=True
        )[:5]  # Always show top 5

        for i, (user_id, stats) in enumerate(sorted_reactors, 1):
            if emoji:
                # When filtering by emoji, just show the count
                report_lines.append(f"{i}. <@{user_id}>: {stats['given']} {emoji}")
            else:
                # Show detailed breakdown only when not filtering by emoji
                top_emojis = sorted(
                    stats["emojis"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                emoji_str = " ".join(f"{emoji}({count})" for emoji, count in top_emojis)
                report_lines.append(f"{i}. <@{user_id}>: {stats['given']} reactions given")
                report_lines.append(f"   Most used: {emoji_str}")
            report_lines.append("")

        # Top 5 reaction receivers
        report_lines.append("**🎯 Top 5 Reaction Receivers:**")
        sorted_reactees = sorted(
            [(uid, data) for uid, data in reactee_stats.items()],
            key=lambda x: x[1]["received"],
            reverse=True
        )[:5]  # Always show top 5

        for i, (user_id, stats) in enumerate(sorted_reactees, 1):
            if emoji:
                # When filtering by emoji, just show the count
                report_lines.append(f"{i}. <@{user_id}>: {stats['received']} {emoji}")
            else:
                # Show detailed breakdown only when not filtering by emoji
                top_emojis = sorted(
                    stats["emojis"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                emoji_str = " ".join(f"{emoji}({count})" for emoji, count in top_emojis)
                report_lines.append(f"{i}. <@{user_id}>: {stats['received']} reactions received")
                report_lines.append(f"   Most received: {emoji_str}")
            report_lines.append("")

        return "\n".join(report_lines)

    async def get_emoji_stats(self, guild_id: int, days: Optional[int] = None):
        """Get statistics about emoji usage."""
        start_time = None
        if days:
            start_time = datetime.now() - timedelta(days=days)

        stats = await self.db.get_statistics(guild_id=guild_id, start_time=start_time)
        
        emoji_stats = defaultdict(int)
        for row in stats:
            emoji_stats[row["emoji"]] += row["count"]

        return dict(sorted(emoji_stats.items(), key=lambda x: x[1], reverse=True))
        
