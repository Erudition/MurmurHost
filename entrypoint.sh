#!/bin/bash
set -e

DB_PATH="/var/lib/murmur/murmur.sqlite"
SEED_PATH="/etc/murmur/murmur.sqlite.seed"

# 1. Clean up if Docker accidentally created a directory
if [ -d "$DB_PATH" ]; then
    echo "WARNING: $DB_PATH is a directory (Docker mount artifact). Removing..."
    rm -rf "$DB_PATH"
fi

# 2. Seed the database if missing or empty
if [ ! -f "$DB_PATH" ] || [ ! -s "$DB_PATH" ]; then
    echo "INFO: Database missing or empty. Seeding from Git version..."
    cp "$SEED_PATH" "$DB_PATH"
fi

# 3. Ensure permissions are correct
chown murmur:murmur "$DB_PATH"
chown murmur:murmur /var/lib/murmur

# Execute Murmur
echo "INFO: Starting Murmur..."
exec mumble-server -fg -ini /etc/murmur.ini
