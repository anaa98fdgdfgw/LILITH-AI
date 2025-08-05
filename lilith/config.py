"""Configuration settings for Lilith."""
from pathlib import Path

# LM Studio settings
LM_STUDIO_URL = "http://localhost:1234/v1"
MODEL_NAME = "local-model"  # This is the default name LM Studio uses

# Screen capture settings
SCREEN_FPS = 15  # Frames per second for screen capture
SCREEN_MAX_WIDTH = 1280  # Maximum width for screen capture (resized if larger)
SCREEN_QUALITY = 85  # JPEG quality (1-100)

# UI settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 7861
ENABLE_SHARE = True  # Create a public share link
THEME_PRIMARY = "purple"
THEME_SECONDARY = "pink"

# Workspace settings
WORKSPACE_DIR = Path.cwd() / "lilith_workspace"

# Tool settings
PYTHON_TIMEOUT = 10  # Seconds before Python execution times out
COMMAND_TIMEOUT = 30  # Seconds before system commands time out
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size

# Personality settings
DEFAULT_PERSONALITY = "Playful"
REACTION_FREQUENCY = 3  # Show a reaction every N messages

# Safety settings
ALLOWED_COMMANDS = [
    "ls", "dir", "pwd", "cd", "echo", "cat", "type", "find", 
    "grep", "pip", "python", "node", "npm", "git", "curl", "wget"
]

# Avatar settings
AVATAR_URL = "https://api.dicebear.com/7.x/bottts-neutral/svg?seed=Lilith&backgroundColor=b6e3f4"

# Welcome messages (randomly selected)
WELCOME_MESSAGES = [
    "Hey! I'm Lilith, your AI coding companion! 👾\n\nI can help you code, debug, and build awesome projects! Enable screen sharing if you want me to see what you're working on. What would you like to create today? 🚀",
    "Yo! Lilith here! 🎮\n\nReady to code something amazing? I can see your screen, write code, and help you build whatever you can imagine! Let's make something cool! 💻✨",
    "Hi there! I'm Lilith! 👋\n\nThink of me as your coding buddy who never sleeps! I can help debug, create projects, and make coding fun! What's on your mind today? 🤔",
    "Welcome! I'm Lilith, your friendly neighborhood code companion! 🕷️\n\nFrom games to websites to automation scripts, I'm here to help you build it all! What adventure shall we embark on? 🗺️"
]

# Example prompts organized by category
EXAMPLE_CATEGORIES = {
    "Games": [
        "Create a snake game with pygame",
        "Make a text-based RPG adventure",
        "Build a simple platformer game"
    ],
    "Web Development": [
        "Create a portfolio website with animations",
        "Build a real-time chat application",
        "Make a todo app with local storage"
    ],
    "Automation": [
        "Create a file organizer script",
        "Build a web scraper for news",
        "Make a Discord bot"
    ],
    "AI & Data": [
        "Create a sentiment analysis script",
        "Build a simple chatbot",
        "Make a data visualization dashboard"
    ]
}