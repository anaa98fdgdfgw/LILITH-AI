"""Launch Lilith Ultimate - RTX 3060 Optimized with ALL features."""
import sys
import os
from pathlib import Path
import subprocess

print("""
⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡
    LILITH ULTIMATE - RTX 3060 EDITION
    All Features Enabled!
⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡⚡
""")

# Set up environment
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
os.chdir(current_dir)

# Load MCP configuration
try:
    import mcp_config
    print("✅ MCP configuration loaded")
    mcp_config.check_api_keys()
except Exception as e:
    print(f"⚠️ Could not load MCP configuration: {e}")

# Install any missing dependencies
print("🔧 Checking dependencies...")
required = [
    "opencv-python",
    "openai", 
    "numpy",
    "Pillow",
    "mss",
    "psutil",
    "aiohttp",
    "flask",
    "flask-socketio",
    "flask-cors",
    "pyttsx3",
    "pywin32",
    "pypiwin32",
    "langdetect",
    "python-socketio[client]",
    "eventlet"
]

try:
    import cv2
    import openai
    import numpy
    import PIL
    import mss
    import psutil
    import flask
    import flask_socketio
    import pyttsx3
    import langdetect
    print("✅ Core dependencies OK!")
except ImportError:
    print("📦 Installing missing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + required)

# Optional dependencies
optional = ["gputil", "pyautogui", "keyboard", "mouse", "alpaca-trade-api", "pygetwindow"]
for pkg in optional:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

# Install streaming dependencies
streaming_deps = ["flask", "flask-socketio", "flask-cors", "pyttsx3", "pywin32", "pypiwin32", "langdetect"]
print("📦 Installing streaming dependencies...")
for pkg in streaming_deps:
    try:
        print(f"   Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
    except Exception as e:
        print(f"   ⚠️ Failed to install {pkg}: {e}")

# Fix pywin32 postinstall
print("🔧 Configuring pywin32...")
try:
    # Try to run pywin32_postinstall
    subprocess.check_call([sys.executable, "-m", "pywin32_postinstall", "-install"])
    print("   ✅ pywin32 configured successfully")
except:
    # Alternative method
    try:
        import win32com.client
        print("   ✅ pywin32 is working")
    except:
        print("   ⚠️ pywin32 configuration failed, TTS might not work")

# Start MCP servers
import time
enabled_servers = [server for server, enabled in mcp_config.MCP_ENABLED.items() if enabled]
mcp_processes = []
for server in enabled_servers:
    port = mcp_config.MCP_PORTS[server]
    server_file = f"mcp_servers/{server}_server.py"
    extra_args = []
    if server == "filesystem":
        extra_args = ["--allowed-directories"] + mcp_config.FILESYSTEM_ALLOWED_DIRS
    elif server == "memory":
        extra_args = ["--db-path", mcp_config.MEMORY_DB_PATH]
    cmd = [sys.executable, server_file, "--port", str(port)] + extra_args
    proc = subprocess.Popen(cmd)
    mcp_processes.append(proc)
    print(f"✅ Started {server} MCP server on port {port}")
time.sleep(5)  # Wait for servers to initialize
print("✅ All MCP servers started")

# --- LM Studio Automation (Simplified) ---

LM_STUDIO_PATH = "C:\\Program Files\\LM Studio\\LM Studio.exe"

if os.path.exists(LM_STUDIO_PATH):
    print(f"\n🚀 Launching LM Studio...")
    try:
        subprocess.Popen([LM_STUDIO_PATH])
        print("   ✅ LM Studio process started.")
        print("\n   --- ACTION REQUIRED ---")
        print("   Please load your model in LM Studio and start the server.")
        print("   -----------------------")
        print("\n   Waiting 10 seconds before starting Lilith...")
        time.sleep(10)
    except Exception as e:
        print(f"   ❌ Failed to launch LM Studio: {e}")
else:
    print("\n⚠️ LM Studio not found. Please start it manually before running this script.")
    print(f"   Expected path: {LM_STUDIO_PATH}")

print("\n🚀 Starting LILITH ULTIMATE STREAMING...")
print("⚡ RTX 3060 12GB Optimized")
print("����️ All tools enabled")
print("🖥️ Multi-monitor support active")
print("🎬 Advanced streaming interface\n")

try:
    from lilith.streaming_server import run_streaming_server
    import webbrowser
    import threading
    import time
    
    print("📍 Streaming server starting at: http://localhost:7861")
    print("🌐 Features:")
    print("   - ✅ Real client-side screen sharing")
    print("   - ✅ Multi-user streaming support")
    print("   - ✅ VTube Studio integration")
    print("   - ✅ Text-to-Speech (TTS) for AI responses")
    print("   - ✅ Low latency WebSocket streaming")
    print("\n💡 LM Studio Settings for RTX 3060:")
    print("   - GPU Layers: Maximum (all layers)")
    print("   - Context Length: 2048")
    print("   - Flash Attention: ON")
    print("   - Model: Up to 13B Q4_K_M")
    print("\n💡 Press Ctrl+C to stop\n")
    
    # The browser will no longer open automatically.
    # Please open http://localhost:7861 manually when the server is ready.
    
    # Run the streaming server
    run_streaming_server(host="0.0.0.0", port=7861)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    input("\nPress Enter to exit...")
