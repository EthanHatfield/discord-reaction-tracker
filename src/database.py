import sqlite3
import aiosqlite
from datetime import datetime
import os

class Database:
    def __init__(self, db_path="reactions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    reactor_id INTEGER NOT NULL,
                    reactee_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    is_removed BOOLEAN DEFAULT FALSE
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_progress (
                    channel_id INTEGER PRIMARY KEY,
                    last_message_id INTEGER,
                    last_scan_time DATETIME
                )
            """)
            
            # Create indexes for better query performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON reactions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reactor ON reactions(reactor_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reactee ON reactions(reactee_id)")

    async def add_reaction(self, reactor_id: int, reactee_id: int, message_id: int, 
                          channel_id: int, emoji: str, timestamp: datetime = None):
        """Add a new reaction to the database."""
        if timestamp is None:
            timestamp = datetime.now()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO reactions 
                (timestamp, reactor_id, reactee_id, message_id, channel_id, emoji)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, reactor_id, reactee_id, message_id, channel_id, emoji))
            await db.commit()

    async def get_reactions(self, start_time: datetime = None, end_time: datetime = None, 
                          emoji: str = None):
        """Get reactions within a time range and/or for a specific emoji."""
        query = "SELECT * FROM reactions WHERE is_removed = FALSE"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        if emoji:
            query += " AND emoji = ?"
            params.append(emoji)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            async with db.execute(query, params) as cursor:
                return await cursor.fetchall()

    async def update_scan_progress(self, channel_id: int, last_message_id: int):
        """Update the scanning progress for a channel."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO scan_progress (channel_id, last_message_id, last_scan_time)
                VALUES (?, ?, ?)
            """, (channel_id, last_message_id, datetime.now()))
            await db.commit()

    async def get_scan_progress(self, channel_id: int):
        """Get the last scanned message ID for a channel."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT last_message_id FROM scan_progress WHERE channel_id = ?",
                (channel_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def get_statistics(self, start_time: datetime = None, end_time: datetime = None,
                           emoji: str = None):
        """Get comprehensive reaction statistics."""
        query = """
            SELECT 
                reactor_id,
                reactee_id,
                emoji,
                COUNT(*) as count
            FROM reactions
            WHERE is_removed = FALSE
        """
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        if emoji:
            query += " AND emoji = ?"
            params.append(emoji)

        query += " GROUP BY reactor_id, reactee_id, emoji"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            async with db.execute(query, params) as cursor:
                return await cursor.fetchall()