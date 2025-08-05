"""Ultimate Lilith UI with ALL features, monitor selection, and cloud redirect."""
from __future__ import annotations

import gradio as gr
import cv2
import mss
import numpy as np
import threading
import time
from PIL import Image
from pathlib import Path
from datetime import datetime
import tempfile
import os
import psutil
import queue
import asyncio
import json
import random
import webbrowser
import subprocess
import socket
import sys

# Try imports
try:
    import GPUtil
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False

from .controller_ultimate import LilithControllerUltimate

try:
    from .mcp_manager import mcp_manager
    MCP_AVAILABLE = True
except:
    MCP_AVAILABLE = False
    mcp_manager = None

# Create temp dir
temp_dir = Path(tempfile.gettempdir()) / "gradio"
temp_dir.mkdir(exist_ok=True)

# Initialize
controller = LilithControllerUltimate()
CLOUD_URL = "https://lilith.sl-anais-kiyori.cloud/ui"

# System monitor
class SystemMonitor:
    def __init__(self, max_usage=90):
        self.max_usage = max_usage
        
    def get_usage(self):
        cpu = psutil.cpu_percent(interval=0.1)
        gpu = 0
        if GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                gpu = gpus[0].load * 100 if gpus else 0
            except:
                pass
        ram = psutil.virtual_memory().percent
        return {"cpu": cpu, "gpu": gpu, "ram": ram, "safe": cpu < self.max_usage and ram < self.max_usage}

system_monitor = SystemMonitor(max_usage=90)

# Screen capture
class UltimateScreenCapture:
    def __init__(self):
        self.users = {}
        self.ai_stream = {'frame': None, 'enabled': False, 'thread': None, 'monitor': 2}  # AI uses monitor 2
        self.current_view = "AI"  # Which stream AI is watching
        self.capture_threads = {}
        self.max_fps = 30
        self.lock = threading.Lock()
        
    def get_available_monitors(self):
        with mss.mss() as sct:
            monitors = []
            for i, monitor in enumerate(sct.monitors):
                if i == 0:
                    continue
                monitors.append({"name": f"Monitor {i}: {monitor['width']}x{monitor['height']}", "index": i})
            return monitors
        
    def add_user(self, username):
        if username not in self.users:
            self.users[username] = {
                'queue': queue.Queue(maxsize=10),
                'enabled': False,
                'current_frame': None,
                'fps': 30,
                'quality': 'high',
                'monitor': 1,
                'thread': None,
                'follow_mouse': False,
                'highlight_mouse': True
            }
    
    def change_monitor(self, username, monitor_index):
        if username in self.users:
            self.users[username]['monitor'] = monitor_index
            return True
        return False
    
    def start_capture(self, username):
        if username not in self.users:
            self.add_user(username)
        user_data = self.users[username]
        user_data['enabled'] = True
        if user_data['thread'] is None or not user_data['thread'].is_alive():
            user_data['thread'] = threading.Thread(target=self._capture_loop, args=(username,), daemon=True)
            user_data['thread'].start()
    
    def stop_capture(self, username):
        if username in self.users:
            self.users[username]['enabled'] = False
    
    def _capture_loop(self, username):
        user_data = self.users[username]
        with mss.mss() as sct:
            while user_data['enabled']:
                try:
                    usage = system_monitor.get_usage()
                    if not usage['safe']:
                        time.sleep(0.1)
                        continue
                    
                    monitor = sct.monitors[user_data['monitor']]
                    
                    if user_data['follow_mouse']:
                        try:
                            import pyautogui
                            mouse_x, mouse_y = pyautogui.position()
                            region_size = 800
                            monitor = {
                                "left": max(0, mouse_x - region_size // 2),
                                "top": max(0, mouse_y - region_size // 2),
                                "width": region_size,
                                "height": region_size
                            }
                        except:
                            pass
                    
                    screenshot = sct.grab(monitor)
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                    
                    if user_data['quality'] == 'low':
                        scale = 0.5
                    elif user_data['quality'] == 'medium':
                        scale = 0.75
                    else:
                        scale = 1.0
                    
                    if scale < 1.0:
                        height, width = frame.shape[:2]
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    
                    cv2.putText(frame, f"Monitor {user_data['monitor']} | CPU: {usage['cpu']:.1f}% GPU: {usage['gpu']:.1f}%", 
                              (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    if user_data['highlight_mouse']:
                        try:
                            import pyautogui
                            mouse_x, mouse_y = pyautogui.position()
                            if user_data['follow_mouse']:
                                mouse_x = region_size // 2
                                mouse_y = region_size // 2
                            else:
                                mouse_x -= monitor['left']
                                mouse_y -= monitor['top']
                            if scale < 1.0:
                                mouse_x = int(mouse_x * scale)
                                mouse_y = int(mouse_y * scale)
                            cv2.circle(frame, (mouse_x, mouse_y), 20, (255, 0, 0), 2)
                            cv2.circle(frame, (mouse_x, mouse_y), 3, (255, 0, 0), -1)
                        except:
                            pass
                    
                    user_data['current_frame'] = frame
                    
                    if not user_data['queue'].full():
                        user_data['queue'].put(frame)
                    
                    if usage['cpu'] > 70:
                        sleep_time = 1.0 / 15
                    else:
                        sleep_time = 1.0 / user_data['fps']
                    
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    print(f"Capture error for {username}: {e}")
                    time.sleep(0.5)
    
    def get_frame(self, username):
        if username in self.users:
            try:
                return self.users[username]['queue'].get_nowait()
            except queue.Empty:
                return self.users[username].get('current_frame')
        return None
    
    def start_ai_stream(self):
        """Start AI's own screen capture."""
        with self.lock:
            if not self.ai_stream['enabled']:
                self.ai_stream['enabled'] = True
                self.ai_stream['thread'] = threading.Thread(
                    target=self._capture_ai_screen, 
                    daemon=True
                )
                self.ai_stream['thread'].start()
    
    def stop_ai_stream(self):
        """Stop AI's screen capture."""
        with self.lock:
            self.ai_stream['enabled'] = False
    
    def _capture_ai_screen(self):
        """Capture AI's screen."""
        with mss.mss() as sct:
            # Check if monitor 2 exists, otherwise use monitor 1
            monitor_index = self.ai_stream['monitor']
            if monitor_index >= len(sct.monitors):
                monitor_index = 1
                print(f"Monitor 2 not found, using Monitor 1 instead")
            
            while self.ai_stream['enabled']:
                try:
                    monitor = sct.monitors[monitor_index]
                    screenshot = sct.grab(monitor)
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                    
                    # Resize for performance
                    height, width = frame.shape[:2]
                    if width > 1280:
                        scale = 1280 / width
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Add label with monitor info
                    cv2.putText(frame, f"AI Screen - Monitor 2 (3440x1440)", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    
                    with self.lock:
                        self.ai_stream['frame'] = frame
                    
                    time.sleep(0.1)  # 10 FPS
                    
                except Exception as e:
                    print(f"AI screen capture error: {e}")
                    time.sleep(1)
    
    def get_current_view_frame(self):
        """Get the frame that AI is currently watching."""
        with self.lock:
            if self.current_view == "AI":
                return self.ai_stream.get('frame')
            elif self.current_view == "None":
                return None
            elif self.current_view in self.users:
                return self.users[self.current_view].get('current_frame')
            return None
    
    def set_current_view(self, view: str):
        """Set which stream the AI is watching."""
        with self.lock:
            self.current_view = view
    
    def get_active_streams(self):
        """Get list of active streams."""
        with self.lock:
            active = []
            if self.ai_stream['enabled']:
                active.append("AI")
            for username, data in self.users.items():
                if data['enabled']:
                    active.append(username)
            return active

# Initialize
screen_capture = UltimateScreenCapture()
active_users = {}
ui_instances = {}
shared_chat_history = []  # Shared chat history for all users
streaming_server_process = None  # Track streaming server process

def generate_unique_pseudo():
    adjectives = ["Swift", "Clever", "Bold", "Wise", "Fierce", "Noble", "Mystic", "Cyber", "Quantum", "Neural"]
    nouns = ["Coder", "Hacker", "Builder", "Creator", "Architect", "Engineer", "Artist", "Wizard", "Ninja", "Phoenix"]
    pseudo = f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(100, 999)}"
    while pseudo in active_users:
        pseudo = f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(100, 999)}"
    return pseudo

# CSS and JavaScript for WebRTC screen sharing
ULTIMATE_CSS = """
.message-wrap { font-size: 14px !important; }
.message-wrap pre { background-color: #1e1e1e; color: #d4d4d4; border-radius: 8px; padding: 16px; overflow-x: auto; border: 1px solid #333; }
.system-stats { background: rgba(0, 0, 0, 0.8); color: #00ff00; padding: 10px; border-radius: 8px; font-family: monospace; }
.monitor-select { background: #f0f0f0; padding: 10px; border-radius: 8px; margin: 10px 0; }
.cloud-redirect { background: linear-gradient(45deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center; margin: 10px 0; }
"""

# JavaScript for client-side screen capture
SCREEN_CAPTURE_JS = """
<script>
let localStream = null;
let captureInterval = null;

async function startScreenShare() {
    try {
        // Request screen capture with audio
        localStream = await navigator.mediaDevices.getDisplayMedia({
            video: {
                cursor: "always",
                displaySurface: "monitor"
            },
            audio: false
        });
        
        // Create video element to capture frames
        const video = document.createElement('video');
        video.srcObject = localStream;
        video.play();
        
        // Wait for video to be ready
        video.onloadedmetadata = () => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            // Capture frames periodically
            captureInterval = setInterval(() => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                
                // Convert to base64 and send to server
                canvas.toBlob((blob) => {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        // Send frame to Gradio
                        const frameData = reader.result;
                        const event = new CustomEvent('screenframe', { detail: frameData });
                        window.dispatchEvent(event);
                    };
                    reader.readAsDataURL(blob);
                }, 'image/jpeg', 0.8);
            }, 100); // 10 FPS
        };
        
        // Handle stream end
        localStream.getVideoTracks()[0].onended = () => {
            stopScreenShare();
        };
        
        return true;
    } catch (err) {
        console.error('Error starting screen share:', err);
        return false;
    }
}

function stopScreenShare() {
    if (captureInterval) {
        clearInterval(captureInterval);
        captureInterval = null;
    }
    
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
}

// Listen for Gradio events
window.addEventListener('load', () => {
    // Override the screen share checkbox behavior
    const checkInterval = setInterval(() => {
        const shareCheckbox = document.querySelector('input[type="checkbox"][aria-label*="Share My Screen"]');
        if (shareCheckbox) {
            clearInterval(checkInterval);
            
            shareCheckbox.addEventListener('change', async (e) => {
                if (e.target.checked) {
                    const started = await startScreenShare();
                    if (!started) {
                        e.target.checked = false;
                    }
                } else {
                    stopScreenShare();
                }
            });
        }
    }, 100);
});
</script>
"""

# Create interface
with gr.Blocks(title="Lilith Ultimate - RTX 3060 Optimized", css=ULTIMATE_CSS, theme=gr.themes.Soft(primary_hue="purple", secondary_hue="pink")) as demo:
    
    ui_id = str(time.time())
    default_pseudo = generate_unique_pseudo()
    ui_instances[ui_id] = {"pseudo": default_pseudo, "created": datetime.now()}
    
    gr.Markdown("# 👾 Lilith Ultimate - Maximum Power Mode\n### ⚡ Optimized for RTX 3060 12GB | All features enabled!")
    
    with gr.Row():
        with gr.Column():
            gr.HTML(f'<div class="cloud-redirect">🌐 <b>Also available on cloud:</b> {CLOUD_URL}</div>')
            cloud_btn = gr.Button("Open Cloud Version 🚀", variant="primary")
    
    with gr.Row():
        system_stats = gr.Markdown("### System Resources\nInitializing...", elem_classes=["system-stats"])
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="Chat with Lilith Ultimate", value=[], height=600, show_copy_button=True, type="messages")
            
            with gr.Row():
                with gr.Column(scale=4):
                    with gr.Row():
                        username = gr.Textbox(label="Your Unique Pseudo", value=default_pseudo, placeholder="Enter your username", info=f"UI Instance: {ui_id[:8]}...", scale=3)
                        validate_pseudo_btn = gr.Button("Validate ✓", size="sm", scale=1)
                    msg = gr.Textbox(label="Message", placeholder="Ask me anything! All tools ready...", lines=3)
                    
                with gr.Column(scale=1):
                    send_btn = gr.Button("Send 📤", variant="primary", size="lg")
                    clear_btn = gr.Button("Clear 🗑️")
            
            with gr.Row():
                other_users = gr.Markdown("**Active users:** Loading...")
            
            with gr.Accordion("🛠️ Advanced Tools & Enhanced Computer Control", open=False):
                gr.Markdown("### Enhanced Computer Control:\n- **capture_full_screen:** Full screen capture with OCR\n- **analyze_screen:** Complete screen analysis with text extraction\n- **click_at_text:** Find and click on specific text\n- **get_all_windows:** List all open windows\n- **activate_window:** Switch to specific window\n- **automate_task:** Execute automation sequences\n\n### Classic Commands:\n- **EXECUTE_PYTHON:** Run Python code\n- **RUN_COMMAND:** Execute system commands\n- **WRITE_FILE:** Create/edit files\n- **CREATE_PROJECT:** Scaffold projects\n\n### MCP Commands (if available):\n- **MCP_SEARCH:** Web search\n- **MCP_GITHUB_ISSUE:** Create GitHub issues\n- **MCP_TRADE:** Stock/crypto trading\n- **MCP_MEMORY:** Persistent storage\n- **MCP_CONTROL:** Local automation")
                
                # Computer control status
                with gr.Group():
                    gr.Markdown("### 🖥️ Computer Control Status")
                    computer_control_status = gr.Textbox(
                        label="Enhanced Control Status",
                        value="Checking computer control capabilities...",
                        interactive=False
                    )
                    refresh_control_status = gr.Button("Refresh Status", size="sm")
                
                if MCP_AVAILABLE:
                    mcp_status = gr.JSON(label="MCP Server Status", value={})
                    refresh_mcp = gr.Button("Refresh MCP Status", size="sm")
        
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("🖥️ Screen Sharing"):
                    # AI View Control
                    with gr.Group():
                        gr.Markdown("### 🤖 AI Screen Control")
                        with gr.Row():
                            ai_view_dropdown = gr.Dropdown(
                                label="AI is watching",
                                choices=["None", "AI"],
                                value="AI",
                                interactive=True
                            )
                            override_btn = gr.Button("Override View 🎮", variant="secondary")
                        
                        ai_view_status = gr.Textbox(
                            label="Status",
                            value="AI is watching: AI",
                            interactive=False
                        )
                        
                        ai_share_screen = gr.Checkbox(label="AI Share Screen", value=False)
                    
                    # What AI Sees
                    ai_current_view = gr.Image(
                        label="What AI Sees Right Now",
                        height=250
                    )
                    
                    gr.Markdown("### 👤 Screen Sharing Options")
                    
                    # Streaming server button
                    with gr.Group():
                        gr.Markdown("### 🚀 Advanced Streaming Interface")
                        gr.Markdown("""
                        **Features:**
                        - ✅ Real client-side screen sharing
                        - ✅ Multi-user streaming support
                        - ✅ VTube Studio integration
                        - ✅ Text-to-Speech (TTS) for AI responses
                        - ✅ Low latency WebSocket streaming
                        """)
                        
                        streaming_status = gr.Textbox(label="Streaming Server Status", value="Not running", interactive=False)
                        
                        with gr.Row():
                            start_streaming_btn = gr.Button("🎬 Start Streaming Server", variant="primary")
                            open_streaming_btn = gr.Button("📺 Open Streaming Interface", variant="secondary")
                    
                    gr.Markdown("---")
                    
                    # Legacy screen sharing (local only)
                    gr.Markdown("### 📟 Legacy Screen Sharing (Local Only)")
                    share_screen = gr.Checkbox(label="Share My Screen (Local)", value=False)
                    screen_status = gr.Textbox(label="Status", value="Not sharing", interactive=False)
                    
                    # Hidden components for WebRTC data transfer
                    screen_frame_input = gr.Image(visible=False)  # Receives frames from client
                    screen_preview = gr.Image(label="Your Screen Preview", visible=False, height=250)
                    
                with gr.TabItem("⚙️ Settings"):
                    personality = gr.Radio(choices=["Friendly", "Professional", "Playful", "Teacher", "Hacker"], value="Playful", label="Personality Mode")
                    max_tokens = gr.Slider(minimum=256, maximum=2048, value=1024, step=256, label="Max Response Length")
                    temperature = gr.Slider(minimum=0.1, maximum=1.0, value=0.7, step=0.1, label="Creativity Level")
                    
                with gr.TabItem("📁 Workspace"):
                    workspace_info = gr.Markdown("Loading workspace info...")
                    refresh_workspace = gr.Button("Refresh", size="sm")
                    
                with gr.TabItem("💡 Examples"):
                    gr.Examples(
                        examples=[
                            "Create a Discord bot with slash commands",
                            "Build a real-time stock tracker using Alpaca",
                            "Make a machine learning model for image classification",
                            "Create a web scraper with data visualization",
                            "Build a multiplayer game with websockets",
                            "Help me debug this code on my screen",
                            "Create a full-stack web app with authentication"
                        ],
                        inputs=msg
                    )
    
    def open_cloud():
        webbrowser.open(CLOUD_URL)
        return gr.update(value=f"✅ Opened {CLOUD_URL} in browser!")
    
    cloud_btn.click(open_cloud, outputs=[screen_status])
    
    def init_user(username_val):
        if username_val and username_val not in active_users:
            active_users[username_val] = {"joined": datetime.now(), "ui_instance": ui_id, "screen_shares": 0}
            screen_capture.add_user(username_val)
        return username_val
    
    def check_if_local(request: gr.Request):
        """Check if user is accessing locally."""
        if request:
            client_host = request.client.host
            # Check if accessing from localhost, 127.0.0.1, or local network
            is_local = client_host in ["127.0.0.1", "localhost", "0.0.0.0"] or client_host.startswith("192.168.") or client_host.startswith("10.")
            return gr.update(visible=is_local)
        return gr.update(visible=False)
    
    # Use button click instead of change event to avoid creating users on every keystroke
    validate_pseudo_btn.click(init_user, inputs=[username], outputs=[username])
    
    def update_active_users():
        user_list = []
        for user, data in active_users.items():
            ui_instance = data.get("ui_instance", "unknown")[:8]
            user_list.append(f"{user} (UI: {ui_instance}...)")
        if user_list:
            return f"**Active users ({len(user_list)}):** {', '.join(user_list[:5])}" + (" ..." if len(user_list) > 5 else "")
        return "**Active users:** None"
    
    def change_monitor(username_val, monitor_choice):
        if monitor_choice and username_val:
            monitors = screen_capture.get_available_monitors()
            for m in monitors:
                if m["name"] == monitor_choice:
                    screen_capture.change_monitor(username_val, m["index"])
                    return f"✅ Switched to {monitor_choice}"
        return "❌ Invalid selection"
    
    # Monitor controls removed for remote users
    
    def toggle_screen(enabled, username_val, request: gr.Request):
        # Only allow screen sharing for local users
        if request:
            client_host = request.client.host
            is_local = client_host in ["127.0.0.1", "localhost", "0.0.0.0"] or client_host.startswith("192.168.") or client_host.startswith("10.")
            
            if not is_local:
                return gr.update(value="❌ Screen sharing only available for local users"), gr.update(visible=False), gr.update(value=False)
        
        if enabled and username_val:
            screen_capture.add_user(username_val)
            screen_capture.start_capture(username_val)
            if username_val in active_users:
                active_users[username_val]["screen_shares"] += 1
            return gr.update(value="✅ Sharing screen"), gr.update(visible=True), gr.update(value=True)
        else:
            if username_val:
                screen_capture.stop_capture(username_val)
            return gr.update(value="Not sharing"), gr.update(visible=False), gr.update(value=False)
    
    share_screen.change(toggle_screen, inputs=[share_screen, username], outputs=[screen_status, screen_preview, share_screen])
    
    # Quality and follow mouse controls removed for simplicity
    
    def update_preview(username_val):
        if username_val in screen_capture.users and screen_capture.users[username_val]['enabled']:
            frame = screen_capture.get_frame(username_val)
            if frame is not None:
                return Image.fromarray(frame)
        return None
    
    screen_timer = gr.Timer(0.1)
    screen_timer.tick(lambda u: update_preview(u), inputs=[username], outputs=[screen_preview])
    
    users_timer = gr.Timer(5.0)
    users_timer.tick(update_active_users, outputs=[other_users])
    
    def update_system_stats():
        usage = system_monitor.get_usage()
        return f"### System Resources\n- **CPU:** {usage['cpu']:.1f}% / 90%\n- **GPU:** {usage['gpu']:.1f}% / 90%\n- **RAM:** {usage['ram']:.1f}% / 90%\n- **Status:** {'🟢 Optimal' if usage['safe'] else '🔴 High Load'}\n- **Cloud:** [Available at {CLOUD_URL}]({CLOUD_URL})"
    
    stats_timer = gr.Timer(2.0)
    stats_timer.tick(update_system_stats, outputs=[system_stats])
    
    # AI screen control functions
    def toggle_ai_screen(enabled):
        """Toggle AI screen sharing."""
        if enabled:
            screen_capture.start_ai_stream()
        else:
            screen_capture.stop_ai_stream()
        return enabled
    
    def update_ai_view_choice(choice):
        """Update AI's view choice."""
        screen_capture.set_current_view(choice)
        return f"AI is now watching: {choice}"
    
    def get_view_choices():
        """Get available view choices for AI."""
        choices = ["None", "AI"]
        choices.extend(active_users.keys())
        return choices
    
    def override_view():
        """Override to cycle through active views."""
        active = screen_capture.get_active_streams()
        if active:
            current = screen_capture.current_view
            try:
                idx = active.index(current)
                next_idx = (idx + 1) % len(active)
                next_view = active[next_idx]
            except:
                next_view = active[0] if active else "None"
            
            screen_capture.set_current_view(next_view)
            return f"AI is now watching: {next_view}", next_view
        return "No active streams", "None"
    
    def update_ai_current_view():
        """Update what the AI is currently viewing."""
        frame = screen_capture.get_current_view_frame()
        if frame is not None:
            return Image.fromarray(frame)
        else:
            # Return placeholder
            placeholder = Image.new('RGB', (640, 480), color='black')
            from PIL import ImageDraw
            draw = ImageDraw.Draw(placeholder)
            draw.text((20, 20), f"AI is watching: {screen_capture.current_view}", fill='white')
            return placeholder
    
    def chat(message, history, username_val, share_screen_val, personality_val, max_tokens_val, temp_val):
        global shared_chat_history
        
        if not message.strip():
            return shared_chat_history.copy(), ""
        
        # Get the frame AI is currently watching (not necessarily the user's screen)
        image_frame = screen_capture.get_current_view_frame()
        
        other_users_list = [u for u in active_users.keys() if u != username_val]
        context = f"[Message from {username_val}]"
        if other_users_list:
            context += f"\n[Other users in chat: {', '.join(other_users_list[:3])}]"
        
        # Add context about what AI is viewing
        current_view = screen_capture.current_view
        if current_view != "None" and image_frame is not None:
            context += f"\n[You are currently viewing: {current_view}'s screen]"
        
        response = controller.chat(message + context, image_frame, max_tokens=max_tokens_val, temperature=temp_val, personality=personality_val)
        
        # Update shared chat history
        shared_chat_history.append({"role": "user", "content": f"**{username_val}:** {message}"})
        shared_chat_history.append({"role": "assistant", "content": response})
        
        return shared_chat_history.copy(), ""
    
    def sync_chat():
        """Sync chat for all users."""
        return shared_chat_history.copy()
    
    # Wire up AI screen controls
    ai_share_screen.change(toggle_ai_screen, inputs=[ai_share_screen], outputs=[ai_share_screen])
    
    ai_view_dropdown.change(
        update_ai_view_choice,
        inputs=[ai_view_dropdown],
        outputs=[ai_view_status]
    )
    
    override_btn.click(
        override_view,
        outputs=[ai_view_status, ai_view_dropdown]
    )
    
    # Timer to update AI's current view
    ai_view_timer = gr.Timer(0.5)
    ai_view_timer.tick(update_ai_current_view, outputs=[ai_current_view])
    
    # Timer to update dropdown choices when users join/leave
    def update_dropdown_choices():
        return gr.update(choices=get_view_choices())
    
    dropdown_timer = gr.Timer(5.0)
    dropdown_timer.tick(update_dropdown_choices, outputs=[ai_view_dropdown])
    
    # Streaming server functions
    def start_streaming_server():
        """Start the streaming server."""
        global streaming_server_process
        
        try:
            # Check if port is available
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 7861))
            sock.close()
            
            if result == 0:
                return gr.update(value="✅ Streaming server already running on port 7861")
            
            # Start the server
            cmd = [sys.executable, "-m", "lilith.streaming_server"]
            streaming_server_process = subprocess.Popen(cmd, cwd=Path(__file__).parent.parent)
            
            # Wait a bit for server to start
            time.sleep(2)
            
            return gr.update(value="✅ Streaming server started on http://localhost:7861")
            
        except Exception as e:
            return gr.update(value=f"❌ Error starting server: {str(e)}")
    
    def open_streaming_interface():
        """Open the streaming interface in browser."""
        webbrowser.open("http://localhost:7861")
        return gr.update(value="✅ Opened streaming interface in browser")
    
    # Wire up streaming buttons
    start_streaming_btn.click(start_streaming_server, outputs=[streaming_status])
    open_streaming_btn.click(open_streaming_interface, outputs=[streaming_status])
    
    send_btn.click(chat, inputs=[msg, chatbot, username, share_screen, personality, max_tokens, temperature], outputs=[chatbot, msg])
    
    msg.submit(chat, inputs=[msg, chatbot, username, share_screen, personality, max_tokens, temperature], outputs=[chatbot, msg])
    
    # Clear button clears shared history
    def clear_shared_chat():
        global shared_chat_history
        shared_chat_history = []
        return []
    
    clear_btn.click(clear_shared_chat, outputs=[chatbot])
    
    # Timer to sync chat across all users
    chat_sync_timer = gr.Timer(1.0)
    chat_sync_timer.tick(sync_chat, outputs=[chatbot])
    
    if MCP_AVAILABLE:
        def get_mcp_status():
            return mcp_manager.get_all_status()
        refresh_mcp.click(get_mcp_status, outputs=[mcp_status])
    
    def get_computer_control_status():
        """Get computer control status and capabilities."""
        try:
            # Try to import and get status from computer control
            from .computer_control import get_computer_controller
            controller = get_computer_controller()
            system_info = controller.get_system_info()
            
            capabilities = system_info.get('capabilities', {})
            permissions = system_info.get('permissions', {})
            monitors = len(system_info.get('monitors', []))
            
            status_text = "✅ Enhanced Computer Control Active\n\n"
            status_text += f"🖥️ Monitors: {monitors}\n"
            status_text += f"📸 Screen Size: {system_info.get('screen_size', {}).get('width')}x{system_info.get('screen_size', {}).get('height')}\n"
            status_text += f"🖱️ Mouse Position: ({system_info.get('mouse_position', {}).get('x')}, {system_info.get('mouse_position', {}).get('y')})\n"
            status_text += f"💾 CPU: {system_info.get('cpu_percent', 0):.1f}%\n"
            status_text += f"🧠 Memory: {system_info.get('memory_percent', 0):.1f}%\n\n"
            
            status_text += "🔧 Capabilities:\n"
            status_text += f"  • OCR (Tesseract): {'✅' if capabilities.get('tesseract_ocr') else '❌'}\n"
            status_text += f"  • OCR (EasyOCR): {'✅' if capabilities.get('easyocr') else '❌'}\n"
            status_text += f"  • Advanced Input: {'✅' if capabilities.get('advanced_input') else '❌'}\n"
            status_text += f"  • Windows API: {'✅' if capabilities.get('windows_api') else '❌'}\n\n"
            
            status_text += "🔐 Permissions:\n"
            for perm, enabled in permissions.items():
                status_text += f"  • {perm.replace('_', ' ').title()}: {'✅' if enabled else '❌'}\n"
            
            return status_text
            
        except Exception as e:
            return f"⚠️ Enhanced Computer Control Not Available\n\nError: {str(e)}\n\nFalling back to basic control mode."
    
    refresh_control_status.click(get_computer_control_status, outputs=[computer_control_status])
    
    def get_workspace_info():
        try:
            workspace = Path.cwd() / "lilith_workspace"
            files = list(workspace.rglob("*"))
            projects = [d for d in workspace.iterdir() if d.is_dir()]
            return f"### Workspace Info\n- **Location:** `{workspace}`\n- **Projects:** {len(projects)}\n- **Total Files:** {len(files)}\n- **Size:** {sum(f.stat().st_size for f in files if f.is_file()) / 1024 / 1024:.2f} MB\n- **Cloud Sync:** [Enable at {CLOUD_URL}]({CLOUD_URL})\n\n**Recent Projects:**\n{chr(10).join(f'- {p.name}' for p in projects[:5])}"
        except:
            return "### Workspace Info\nError loading workspace"
    
    refresh_workspace.click(get_workspace_info, outputs=[workspace_info])
    
    demo.load(lambda: [{"role": "assistant", "content": f"🚀 **LILITH ULTIMATE - RTX 3060 OPTIMIZED!**\n\nWelcome **{default_pseudo}**! You have a unique pseudo for this session.\n\nI'm running at maximum power with ALL features:\n- ⚡ Optimized for your RTX 3060 12GB\n- 🖥️ Multi-monitor support - select any screen!\n- 🛠️ All tools ready (Python, Commands, Files, Projects)\n- 🧠 Enhanced memory and context\n- 🔥 Maximum performance mode\n- 👥 Multi-user support with unique pseudos\n- 🎭 5 personality modes\n- 🌐 Also available on cloud: {CLOUD_URL}\n\n**Quick tips:**\n- Click 'Validate ✓' after entering your pseudo\n- Select your monitor if you have multiple screens\n- Share your screen to show me code\n- Try different personality modes\n- All commands available!\n\nWhat incredible thing shall we build today? 💪"}], outputs=[chatbot])
    
    # Monitor selection removed for cloud users
    
    if MCP_AVAILABLE:
        demo.load(get_mcp_status, outputs=[mcp_status])
    demo.load(get_workspace_info, outputs=[workspace_info])
    demo.load(update_active_users, outputs=[other_users])
    demo.load(get_computer_control_status, outputs=[computer_control_status])

# Export demo
__all__ = ['demo']

if __name__ == "__main__":
    workspace = Path.cwd() / "lilith_workspace"
    workspace.mkdir(exist_ok=True)
    
    print(f"👾 LILITH ULTIMATE - RTX 3060 EDITION")
    print(f"⚡ Maximum Performance Mode!")
    print(f"🖥️ Multi-monitor support enabled")
    print(f"📁 Workspace: {workspace}")
    print(f"🔥 Using up to 90% system resources")
    print(f"🌐 Cloud version: {CLOUD_URL}")
    
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7861, 
        share=False, 
        show_error=True, 
        max_threads=40,
        root_path="",  # Remove root_path for now
        allowed_paths=["."]  # Allow serving files
    )
