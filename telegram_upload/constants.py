"""
Constants used throughout the telegram-upload application.

This module centralizes magic numbers and strings to improve
code maintainability and readability.
"""

# File splitting constants
SPLIT_FILE_PART_NUMBER_PADDING = 2  # Number of digits for part numbering (e.g., .01, .02, .99)

# Duration formatting constants
DURATION_SEPARATOR = ", "  # Separator between duration components
DURATION_LAST_SEPARATOR = " and "  # Separator before the last duration component

# Caption formatting constants
MAX_CAPTION_LENGTH_FREE = 1024  # Maximum caption length for free users
MAX_CAPTION_LENGTH_PREMIUM = 2048  # Maximum caption length for premium users

# File size constants (already defined in telegram_manager_client.py but can be moved here)
# BOT_USER_MAX_FILE_SIZE = 52428800  # 50MB
# USER_MAX_FILE_SIZE = 2097152000  # 2GB
# PREMIUM_USER_MAX_FILE_SIZE = 4194304000  # 4GB
