"""MCP Server Configuration for LILITH AI.

This file helps you configure API keys and settings for MCP servers.
Copy this file to mcp_config_local.py and fill in your API keys.
"""

import os
from pathlib import Path

# ===== API KEYS CONFIGURATION =====
# Set your API keys here or as environment variables

# GitHub API Token
# Get yours at: https://github.com/settings/tokens
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Brave Search API Key
# Get yours at: https://api.search.brave.com/
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

# Alpaca Trading API Keys (Paper Trading)
# Get yours at: https://alpaca.markets/
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# ===== SERVER CONFIGURATION =====

# MCP Server Ports
MCP_PORTS = {
    "filesystem": 3001,
    "github": 3002,
    "memory": 3005,
    "search": 3006,
    "time": 3009,
    "fetch": 3010,
    "ab498_control": 3011,
    "alpaca": 3012,
    "vtube_studio": 3013
}

# Enabled Servers (set to False to disable)
MCP_ENABLED = {
    "filesystem": True,      # File operations
    "github": True,          # GitHub integration (requires GITHUB_TOKEN)
    "memory": True,          # Persistent memory & knowledge graph
    "search": True,          # Web search (works without API key using DuckDuckGo)
    "time": True,            # Time & date operations
    "fetch": True,           # HTTP requests
    "ab498_control": True,  # Mouse, keyboard, screen control
    "alpaca": True,          # Stock trading (requires ALPACA keys)
    "vtube_studio": True     # VTube Studio control (requires VTube Studio running with API on port 8001)
}

# ===== FILESYSTEM SERVER SETTINGS =====

# Allowed directories for filesystem operations
FILESYSTEM_ALLOWED_DIRS = [
    str(Path.home()),                    # User home directory
    str(Path.cwd()),                     # Current working directory
    str(Path.home() / "Desktop"),        # Desktop
    str(Path.home() / "Documents"),      # Documents
    str(Path.home() / "Downloads"),      # Downloads
    "e:\\LLM-Proxy\\LILITH-AI\\lilith_workspace"  # LILITH workspace
]

# ===== MEMORY SERVER SETTINGS =====

# Database location for persistent memory
MEMORY_DB_PATH = str(Path.home() / ".lilith" / "memory.db")

# ===== REMOTE CONTROL SETTINGS =====

# Safety settings for remote control
REMOTE_CONTROL_SAFE_MODE = True  # If True, requires confirmation for destructive actions
REMOTE_CONTROL_ALLOWED_APPS = [   # Apps that can be controlled
    "notepad", "calculator", "chrome", "firefox", "vscode", "terminal"
]

# ===== SEARCH SERVER SETTINGS =====

# Searx instance URL (optional, for advanced search)
SEARX_URL = os.environ.get("SEARX_URL", "https://searx.me")

# ===== HELPER FUNCTIONS =====

def set_environment_variables():
    """Set environment variables from this config."""
    if GITHUB_TOKEN:
        os.environ["GITHUB_TOKEN"] = GITHUB_TOKEN
    if BRAVE_API_KEY:
        os.environ["BRAVE_API_KEY"] = BRAVE_API_KEY
    if ALPACA_API_KEY:
        os.environ["ALPACA_API_KEY"] = ALPACA_API_KEY
    if ALPACA_SECRET_KEY:
        os.environ["ALPACA_SECRET_KEY"] = ALPACA_SECRET_KEY
    if ALPACA_BASE_URL:
        os.environ["ALPACA_BASE_URL"] = ALPACA_BASE_URL
    if SEARX_URL:
        os.environ["SEARX_URL"] = SEARX_URL

def check_api_keys():
    """Check which API keys are configured."""
    status = {
        "GitHub": bool(GITHUB_TOKEN),
        "Brave Search": bool(BRAVE_API_KEY),
        "Alpaca Trading": bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)
    }
    
    print("=== MCP API Keys Status ===")
    for service, configured in status.items():
        status_text = "✅ Configured" if configured else "❌ Not configured"
        print(f"{service}: {status_text}")
    print()
    
    # Show which features are available
    print("=== Available Features ===")
    if status["GitHub"]:
        print("✅ GitHub: Create issues, manage repos, search code")
    else:
        print("❌ GitHub: Limited functionality without API key")
        
    if status["Brave Search"]:
        print("✅ Search: Full web search with Brave API")
    else:
        print("⚠️ Search: Using DuckDuckGo fallback (limited)")
        
    if status["Alpaca Trading"]:
        print("✅ Trading: Full paper trading capabilities")
    else:
        print("❌ Trading: Not available without API keys")
    
    print("\n✅ Always available: Filesystem, Memory, Time, Fetch, Remote Control")
    
    return status

def get_mcp_config():
    """Get MCP configuration as a dictionary."""
    return {
        "ports": MCP_PORTS,
        "enabled": MCP_ENABLED,
        "filesystem": {
            "allowed_dirs": FILESYSTEM_ALLOWED_DIRS
        },
        "memory": {
            "db_path": MEMORY_DB_PATH
        },
        "remote_control": {
            "safe_mode": REMOTE_CONTROL_SAFE_MODE,
            "allowed_apps": REMOTE_CONTROL_ALLOWED_APPS
        },
        "api_keys": {
            "github": bool(GITHUB_TOKEN),
            "brave": bool(BRAVE_API_KEY),
            "alpaca": bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)
        }
    }

# Auto-load local config if it exists
try:
    from mcp_config_local import *
    print("✅ Loaded local MCP configuration from mcp_config_local.py")
except ImportError:
    pass

# Set environment variables on import
set_environment_variables()

if __name__ == "__main__":
    # Show configuration status when run directly
    check_api_keys()
    print("\nTo configure API keys:")
    print("1. Copy this file to mcp_config_local.py")
    print("2. Fill in your API keys in the new file")
    print("3. Restart LILITH to apply changes")