#!/bin/bash
set -e

# Ensure the database file exists and is owned by the murmur user
# This handles cases where Docker mounts the file as root
if [ -f /var/lib/murmur/murmur.sqlite ]; then
    chown murmur:murmur /var/lib/murmur/murmur.sqlite
fi

# Ensure the directory is writable
chown murmur:murmur /var/lib/murmur

# Execute Murmur
exec mumble-server -fg -ini /etc/murmur.ini
