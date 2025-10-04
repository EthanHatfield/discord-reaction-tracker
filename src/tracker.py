from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Any
import asyncio
import discord
from database import Database
import config

class ReactionTracker:
    def __init__(self):
        self.db = Database()
        self.scanning = False
        self.scan_progress = defaultdict(int)
        self.scan_task = None
        
    async def track_reaction(self, reactor_id: int, reactee_id: int, message_id: int, 
                           channel_id: int, emoji: str):
        """Track a new reaction."""
        await self.db.add_reaction(
            reactor_id=reactor_id,
            reactee_id=reactee_id,
            message_id=message_id,
            channel_id=channel_id,
            emoji=emoji
        )

    async def scan_channel_history(self, channel: discord.TextChannel, progress_callback=None):
        """Scan a channel's message history for reactions."""
        last_message_id = await self.db.get_scan_progress(channel.id)
        
        try:
            async for message in channel.history(limit=None, after=last_message_id):
                if not self.scanning:
                    break
                    
                for reaction in message.reactions:
                    async for user in reaction.users():
                        if user.bot:
                            continue
                            
                        await self.db.add_reaction(
                            reactor_id=user.id,
                            reactee_id=message.author.id,
                            message_id=message.id,
                            channel_id=channel.id,
                            emoji=str(reaction.emoji),
                            timestamp=message.created_at
                        )
                
                await self.db.update_scan_progress(channel.id, message.id)
                self.scan_progress[channel.id] = message.id
                
                if progress_callback:
                    await progress_callback(channel, message)
                    
                # Rate limit handling
                await asyncio.sleep(0.5)
                
        except discord.errors.Forbidden:
            print(f"No access to channel {channel.name}")
        except Exception as e:
            print(f"Error scanning channel {channel.name}: {e}")

    async def start_scanning(self, guild: discord.Guild, progress_callback=None):
        """Start scanning the server's message history."""
        if self.scanning:
            return False
            
        self.scanning = True
        self.scan_task = asyncio.create_task(self._scan_guild(guild, progress_callback))
        return True

    async def stop_scanning(self):
        """Stop the scanning process."""
        self.scanning = False
        if self.scan_task:
            await self.scan_task
            self.scan_task = None

    async def _scan_guild(self, guild: discord.Guild, progress_callback=None):
        """Scan all accessible channels in the guild."""
        for channel in guild.text_channels:
            if not self.scanning:
                break
            await self.scan_channel_history(channel, progress_callback)

    def get_scan_status(self):
        """Get the current scanning status."""
        return {
            "scanning": self.scanning,
            "progress": dict(self.scan_progress)
        }

    async def get_report(self, days: Optional[int] = None, emoji: Optional[str] = None):
        """Generate a detailed report of reaction statistics."""
        start_time = None
        if days:
            start_time = datetime.now() - timedelta(days=days)

        stats = await self.db.get_statistics(start_time=start_time, emoji=emoji)
        if not stats:
            return "No reactions found for the specified criteria!"

        # Process statistics
        reactor_stats = defaultdict(lambda: {"given": 0, "emojis": defaultdict(int)})
        reactee_stats = defaultdict(lambda: {"received": 0, "emojis": defaultdict(int)})

        for row in stats:
            reactor_stats[row["reactor_id"]]["given"] += row["count"]
            reactor_stats[row["reactor_id"]]["emojis"][row["emoji"]] += row["count"]
            
            reactee_stats[row["reactee_id"]]["received"] += row["count"]
            reactee_stats[row["reactee_id"]]["emojis"][row["emoji"]] += row["count"]

        # Build report
        report = ["📊 **Reaction Tracking Report**"]
        
        if days:
            report.append(f"Time period: Last {days} days")
        if emoji:
            report.append(f"Filtered by emoji: {emoji}")
        report.append("")

        # Top reaction givers
        report.append("**Top Reaction Givers:**")
        sorted_reactors = sorted(
            reactor_stats.items(),
            key=lambda x: x[1]["given"],
            reverse=True
        )[:5]

        for user_id, stats in sorted_reactors:
            top_emojis = sorted(
                stats["emojis"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            emoji_str = " ".join(f"{emoji}({count})" for emoji, count in top_emojis)
            report.append(f"<@{user_id}>: {stats['given']} reactions given")
            report.append(f"Most used: {emoji_str}")
            report.append("")

        # Top reaction receivers
        report.append("**Top Reaction Receivers:**")
        sorted_reactees = sorted(
            reactee_stats.items(),
            key=lambda x: x[1]["received"],
            reverse=True
        )[:5]

        for user_id, stats in sorted_reactees:
            top_emojis = sorted(
                stats["emojis"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            emoji_str = " ".join(f"{emoji}({count})" for emoji, count in top_emojis)
            report.append(f"<@{user_id}>: {stats['received']} reactions received")
            report.append(f"Most received: {emoji_str}")
            report.append("")

        return "\n".join(report)

    async def get_emoji_stats(self, days: Optional[int] = None):
        """Get statistics about emoji usage."""
        start_time = None
        if days:
            start_time = datetime.now() - timedelta(days=days)

        stats = await self.db.get_statistics(start_time=start_time)
        
        emoji_stats = defaultdict(int)
        for row in stats:
            emoji_stats[row["emoji"]] += row["count"]

        return dict(sorted(emoji_stats.items(), key=lambda x: x[1], reverse=True))
        
    def track_reaction(self, reactor_id: int, reactee_id: int, message_id: int, emoji_str: str):
        """
        Track a reaction with full context.
        
        Args:
            reactor_id: ID of the user who reacted
            reactee_id: ID of the user who received the reaction
            message_id: ID of the message that was reacted to
            emoji_str: The emoji that was used
        """
        if not self.tracking:
            return False
            
        self.reactions.append({
            'timestamp': datetime.now(),
            'reactor_id': reactor_id,
            'reactee_id': reactee_id,
            'message_id': message_id,
            'emoji': emoji_str
        })
        return True
        
    def _filter_reactions(self, 
                         timeframe: Optional[timedelta] = None, 
                         emoji: Optional[str] = None) -> List[Dict]:
        """Filter reactions based on timeframe and emoji."""
        now = datetime.now()
        filtered = self.reactions
        
        if timeframe:
            cutoff = now - timeframe
            filtered = [r for r in filtered if r['timestamp'] >= cutoff]
            
        if emoji:
            filtered = [r for r in filtered if r['emoji'] == emoji]
            
        return filtered
        
    def _get_user_stats(self, reactions: List[Dict]) -> Tuple[Dict, Dict]:
        """Get statistics for both reactors and reactees."""
        reactor_stats = defaultdict(lambda: {'given': 0, 'emojis': defaultdict(int)})
        reactee_stats = defaultdict(lambda: {'received': 0, 'emojis': defaultdict(int)})
        
        for reaction in reactions:
            reactor = reactor_stats[reaction['reactor_id']]
            reactee = reactee_stats[reaction['reactee_id']]
            
            reactor['given'] += 1
            reactor['emojis'][reaction['emoji']] += 1
            
            reactee['received'] += 1
            reactee['emojis'][reaction['emoji']] += 1
            
        return reactor_stats, reactee_stats
        
    def get_report(self, timeframe_days: Optional[int] = None, emoji: Optional[str] = None):
        """
        Generate a detailed report of reaction statistics.
        
        Args:
            timeframe_days: Optional number of days to look back
            emoji: Optional emoji to filter by
        """
        if not self.reactions:
            return "No reactions tracked yet!"
            
        timeframe = timedelta(days=timeframe_days) if timeframe_days else None
        filtered_reactions = self._filter_reactions(timeframe, emoji)
        
        if not filtered_reactions:
            return "No reactions found for the specified criteria!"
            
        reactor_stats, reactee_stats = self._get_user_stats(filtered_reactions)
        
        # Build report
        report = ["📊 **Reaction Tracking Report**"]
        
        # Add filters info
        if timeframe:
            report.append(f"Time period: Last {timeframe_days} days")
        if emoji:
            report.append(f"Filtered by emoji: {emoji}")
        report.append("")
        
        # Top reaction givers
        report.append("**Top Reaction Givers:**")
        sorted_reactors = sorted(reactor_stats.items(), key=lambda x: x[1]['given'], reverse=True)[:5]
        for user_id, stats in sorted_reactors:
            top_emojis = sorted(stats['emojis'].items(), key=lambda x: x[1], reverse=True)[:3]
            emoji_str = " ".join(f"{emoji}({count})" for emoji, count in top_emojis)
            report.append(f"<@{user_id}>: {stats['given']} reactions given")
            report.append(f"Most used: {emoji_str}")
            report.append("")
            
        # Top reaction receivers
        report.append("**Top Reaction Receivers:**")
        sorted_reactees = sorted(reactee_stats.items(), key=lambda x: x[1]['received'], reverse=True)[:5]
        for user_id, stats in sorted_reactees:
            top_emojis = sorted(stats['emojis'].items(), key=lambda x: x[1], reverse=True)[:3]
            emoji_str = " ".join(f"{emoji}({count})" for emoji, count in top_emojis)
            report.append(f"<@{user_id}>: {stats['received']} reactions received")
            report.append(f"Most received: {emoji_str}")
            report.append("")
            
        return "\n".join(report)
        
    def get_emoji_stats(self, timeframe_days: Optional[int] = None):
        """Get statistics about emoji usage."""
        timeframe = timedelta(days=timeframe_days) if timeframe_days else None
        filtered_reactions = self._filter_reactions(timeframe)
        
        emoji_stats = defaultdict(int)
        for reaction in filtered_reactions:
            emoji_stats[reaction['emoji']] += 1
            
        return dict(sorted(emoji_stats.items(), key=lambda x: x[1], reverse=True))