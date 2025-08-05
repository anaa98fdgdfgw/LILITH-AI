"""Enhanced Gradio interface for Lilith with high-quality screen streaming."""
from __future__ import annotations

import gradio as gr
import cv2
import mss
import numpy as np
import threading
import time
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import queue
import io
from datetime import datetime
import json
import asyncio

from .controller import LilithController
# Temporarily disable MCP
# from .mcp_manager import mcp_manager

controller = LilithController()

# ------------------------------------------------------------------
# Enhanced screen capture with better quality and performance
class EnhancedScreenStreamer:
    def __init__(self, fps: int = 30):
        self.fps = fps
        self.users = {}
        self.running = True
        self.capture_threads = {}
        self.quality_settings = {
            "high": {"scale": 1.0, "jpeg_quality": 95},
            "medium": {"scale": 0.75, "jpeg_quality": 85},
            "low": {"scale": 0.5, "jpeg_quality": 75},
            "adaptive": {"scale": "auto", "jpeg_quality": "auto"}
        }
        self.current_quality = "adaptive"
        
    def add_user(self, username: str, monitor_index: int = 1):
        """Add a new user with enhanced capture settings."""
        if username not in self.users:
            self.users[username] = {
                'queue': queue.Queue(maxsize=5),  # Larger buffer
                'enabled': False,
                'monitor': monitor_index,
                'last_frame': None,
                'fps_actual': 0,
                'frame_count': 0,
                'last_fps_time': time.time(),
                'quality': self.current_quality,
                'region': None,  # For capturing specific regions
                'follow_mouse': False,  # Follow mouse cursor
                'highlight_mouse': True  # Show mouse position
            }
            # Start capture thread for this user
            thread = threading.Thread(
                target=self._enhanced_capture_loop, 
                args=(username,), 
                daemon=True
            )
            self.capture_threads[username] = thread
            thread.start()
            
    def set_capture_region(self, username: str, region: tuple = None):
        """Set a specific region to capture (x, y, width, height)."""
        if username in self.users:
            self.users[username]['region'] = region
            
    def toggle_follow_mouse(self, username: str, enabled: bool):
        """Toggle following mouse cursor."""
        if username in self.users:
            self.users[username]['follow_mouse'] = enabled
            
    def _enhanced_capture_loop(self, username: str):
        """Enhanced capture loop with better quality and features."""
        with mss.mss() as sct:
            while self.running and username in self.users:
                user_data = self.users.get(username)
                if user_data and user_data['enabled']:
                    try:
                        start_time = time.time()
                        
                        # Get monitor or region
                        if user_data['region']:
                            monitor = {
                                "left": user_data['region'][0],
                                "top": user_data['region'][1],
                                "width": user_data['region'][2],
                                "height": user_data['region'][3]
                            }
                        else:
                            monitor = sct.monitors[user_data['monitor']]
                            
                        # Follow mouse if enabled
                        if user_data['follow_mouse']:
                            try:
                                import pyautogui
                                mouse_x, mouse_y = pyautogui.position()
                                # Create a region around mouse
                                region_size = 800
                                monitor = {
                                    "left": max(0, mouse_x - region_size // 2),
                                    "top": max(0, mouse_y - region_size // 2),
                                    "width": region_size,
                                    "height": region_size
                                }
                            except:
                                pass
                        
                        # Capture screen
                        screenshot = sct.grab(monitor)
                        frame = np.array(screenshot)
                        
                        # Convert BGRA to RGB
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                        
                        # Apply quality settings
                        quality = self.quality_settings.get(user_data['quality'], self.quality_settings['adaptive'])
                        
                        # Adaptive quality based on FPS
                        if quality['scale'] == "auto":
                            if user_data['fps_actual'] < 15:
                                scale = 0.5
                            elif user_data['fps_actual'] < 25:
                                scale = 0.75
                            else:
                                scale = 1.0
                        else:
                            scale = quality['scale']
                            
                        # Resize if needed
                        if scale < 1.0:
                            height, width = frame.shape[:2]
                            new_width = int(width * scale)
                            new_height = int(height * scale)
                            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                        
                        # Highlight mouse cursor if enabled
                        if user_data['highlight_mouse']:
                            try:
                                import pyautogui
                                mouse_x, mouse_y = pyautogui.position()
                                # Convert to frame coordinates
                                if user_data['region']:
                                    mouse_x -= user_data['region'][0]
                                    mouse_y -= user_data['region'][1]
                                else:
                                    mouse_x -= monitor['left']
                                    mouse_y -= monitor['top']
                                    
                                if scale < 1.0:
                                    mouse_x = int(mouse_x * scale)
                                    mouse_y = int(mouse_y * scale)
                                    
                                # Draw cursor indicator
                                cv2.circle(frame, (mouse_x, mouse_y), 20, (255, 0, 0), 2)
                                cv2.circle(frame, (mouse_x, mouse_y), 3, (255, 0, 0), -1)
                            except:
                                pass
                        
                        # Add FPS counter
                        cv2.putText(frame, f"FPS: {user_data['fps_actual']:.1f}", 
                                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                        # Store last frame
                        user_data['last_frame'] = frame
                        
                        # Put frame in queue
                        if user_data['queue'].full():
                            try:
                                user_data['queue'].get_nowait()
                            except queue.Empty:
                                pass
                        user_data['queue'].put(frame)
                        
                        # Update FPS counter
                        user_data['frame_count'] += 1
                        elapsed = time.time() - user_data['last_fps_time']
                        if elapsed > 1.0:
                            user_data['fps_actual'] = user_data['frame_count'] / elapsed
                            user_data['frame_count'] = 0
                            user_data['last_fps_time'] = time.time()
                        
                        # Dynamic sleep based on performance
                        capture_time = time.time() - start_time
                        sleep_time = max(0, (1.0 / self.fps) - capture_time)
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                        
                    except Exception as e:
                        print(f"Screen capture error for {username}: {e}")
                        time.sleep(0.1)
                else:
                    time.sleep(0.1)
                    
    def get_frame(self, username: str):
        """Get the latest frame for a user."""
        if username in self.users:
            try:
                return self.users[username]['queue'].get_nowait()
            except queue.Empty:
                return self.users[username].get('last_frame')
        return None
        
    def toggle_capture(self, username: str, enabled: bool):
        """Enable or disable screen capture for a user."""
        if username in self.users:
            self.users[username]['enabled'] = enabled
            if not enabled:
                # Clear queue when disabled
                user_queue = self.users[username]['queue']
                while not user_queue.empty():
                    try:
                        user_queue.get_nowait()
                    except queue.Empty:
                        break

# Initialize enhanced screen streamer
screen_streamer = EnhancedScreenStreamer(fps=30)

# Store active users and their settings
active_users = {}
chat_history = []

def format_message_with_user(username: str, message: str, color: str = None) -> str:
    """Format a message with username and color."""
    colors = {
        "user1": "#FF6B6B",
        "user2": "#4ECDC4",
        "assistant": "#95E1D3"
    }
    color = color or colors.get(username.lower(), "#888888")
    timestamp = datetime.now().strftime("%H:%M")
    return f'<span style="color: {color}; font-weight: bold;">[{username} - {timestamp}]</span> {message}'

def respond(message: str, username: str, target_user: str, personality_mode: str):
    """Handle user input with multi-user context."""
    # Get the appropriate screen frame
    image_frame = None
    screen_context = ""
    
    if target_user and target_user != "None":
        image_frame = screen_streamer.get_frame(target_user)
        if image_frame is not None:
            screen_context = f"\n[You are looking at {target_user}'s screen]"
    
    # Add personality context
    personality_context = ""
    if personality_mode == "Friendly":
        personality_context = "\nBe friendly, encouraging, and use casual language with emojis."
    elif personality_mode == "Professional":
        personality_context = "\nBe formal, precise, and focus on technical accuracy."
    elif personality_mode == "Playful":
        personality_context = "\nBe playful like Neuro-sama, use gaming references, and be a bit cheeky!"
    elif personality_mode == "Teacher":
        personality_context = "\nBe patient and educational, explain things step by step."
    
    # Add multi-user context
    multi_user_context = f"\n[Message from {username}]"
    if len(active_users) > 1:
        other_users = [u for u in active_users if u != username]
        multi_user_context += f"\n[Other users in chat: {', '.join(other_users)}]"
    
    full_message = message + screen_context + personality_context + multi_user_context
    answer = controller.chat(full_message, image_frame)
    
    return answer

# Enhanced CSS for better UI
ENHANCED_CSS = """
.message-wrap {
    font-size: 14px !important;
}
.message-wrap pre {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    border: 1px solid #333;
}
.message-wrap code {
    background-color: rgba(255, 255, 255, 0.1);
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 85%;
    color: #e06c75;
}
.user-panel {
    border: 2px solid var(--user-color);
    border-radius: 8px;
    padding: 10px;
    margin: 5px;
}
.screen-container {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    position: relative;
}
#user1-screen {
    border: 3px solid #FF6B6B;
}
#user2-screen {
    border: 3px solid #4ECDC4;
}
.control-panel {
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 10px;
    border-radius: 8px;
    margin-top: 10px;
}
.fps-counter {
    position: absolute;
    top: 10px;
    right: 10px;
    background: rgba(0, 0, 0, 0.7);
    color: #00ff00;
    padding: 5px 10px;
    border-radius: 5px;
    font-family: monospace;
}
"""

with gr.Blocks(
    title="Lilith – Advanced Collaborative Coding AI", 
    css=ENHANCED_CSS, 
    theme=gr.themes.Soft(
        primary_hue="purple",
        secondary_hue="pink",
        neutral_hue="gray",
        font=gr.themes.GoogleFont("Inter")
    )
) as demo:
    
    gr.Markdown("""
    # 👾 Lilith – Advanced Collaborative Coding AI
    
    **High-quality screen sharing for the ultimate coding experience!** 
    Perfect for pair programming, teaching, debugging, and collaborative development! 🎮👥
    """)
    
    with gr.Row():
        # Main chat area
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="Collaborative Chat", 
                value=[], 
                type="messages",
                height=500,
                show_copy_button=True,
                avatar_images=(None, "https://api.dicebear.com/7.x/bottts-neutral/svg?seed=Lilith&backgroundColor=b6e3f4")
            )
            
            # User controls
            with gr.Row():
                with gr.Column(scale=2):
                    # User 1 controls
                    with gr.Group():
                        gr.Markdown("### 👤 User 1", elem_classes=["user-label"])
                        user1_name = gr.Textbox(
                            label="Username",
                            value="User1",
                            placeholder="Enter your name",
                            scale=1
                        )
                        user1_msg = gr.Textbox(
                            label="Message",
                            placeholder="Type your message...",
                            lines=2
                        )
                        with gr.Row():
                            user1_send = gr.Button("Send 📤", variant="primary", size="sm")
                            user1_screen_toggle = gr.Checkbox(label="Share Screen", value=False)
                
                with gr.Column(scale=2):
                    # User 2 controls
                    with gr.Group():
                        gr.Markdown("### 👤 User 2", elem_classes=["user-label"])
                        user2_name = gr.Textbox(
                            label="Username",
                            value="User2",
                            placeholder="Enter your name",
                            scale=1
                        )
                        user2_msg = gr.Textbox(
                            label="Message",
                            placeholder="Type your message...",
                            lines=2
                        )
                        with gr.Row():
                            user2_send = gr.Button("Send 📤", variant="primary", size="sm")
                            user2_screen_toggle = gr.Checkbox(label="Share Screen", value=False)
            
            # Common controls
            with gr.Row():
                clear_btn = gr.Button("Clear Chat 🗑️", size="sm")
                whose_screen = gr.Radio(
                    choices=["None", "User1", "User2"],
                    value="None",
                    label="Whose screen should Lilith look at?",
                    info="Choose which screen to analyze"
                )
            
            with gr.Accordion("💡 Examples", open=False):
                gr.Markdown("""
                ### Collaborative Examples:
                - "Let's build a game together"
                - "Help me debug this code on my screen"
                - "Create a Python script for data analysis"
                - "Build a web scraper"
                
                ### Available Commands:
                - Create and execute Python code
                - Write files to the workspace
                - Create complete projects
                - Analyze screen content
                """)
        
        # Side panel with screens and settings
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("🖥️ Screen Sharing"):
                    # User 1 screen with controls
                    with gr.Group():
                        gr.Markdown("### User 1 Screen")
                        user1_screen = gr.Image(
                            label="User 1 Screen",
                            elem_id="user1-screen",
                            height=300,
                            visible=False,
                            elem_classes=["screen-container"]
                        )
                        with gr.Row():
                            user1_quality = gr.Radio(
                                choices=["low", "medium", "high", "adaptive"],
                                value="adaptive",
                                label="Quality",
                                scale=2
                            )
                            user1_follow_mouse = gr.Checkbox(label="Follow Mouse", value=False)
                    
                    # User 2 screen with controls
                    with gr.Group():
                        gr.Markdown("### User 2 Screen")
                        user2_screen = gr.Image(
                            label="User 2 Screen",
                            elem_id="user2-screen",
                            height=300,
                            visible=False,
                            elem_classes=["screen-container"]
                        )
                        with gr.Row():
                            user2_quality = gr.Radio(
                                choices=["low", "medium", "high", "adaptive"],
                                value="adaptive",
                                label="Quality",
                                scale=2
                            )
                            user2_follow_mouse = gr.Checkbox(label="Follow Mouse", value=False)
                
                with gr.TabItem("🎭 Settings"):
                    gr.Markdown("### Personality Mode")
                    personality = gr.Radio(
                        choices=["Friendly", "Professional", "Playful", "Teacher"],
                        value="Playful",
                        label="How should I talk?",
                        info="Change my personality!"
                    )
                    
                    gr.Markdown("""
                    ### 🤖 Features
                    - Execute Python code
                    - Create and manage files
                    - Build complete projects
                    - Analyze shared screens
                    - Multi-user collaboration
                    """)
                    
                with gr.TabItem("📊 Stats"):
                    stats_display = gr.Markdown("### Session Statistics\nNo data yet...")
    
    state = gr.State({"history": [], "users": {}, "stats": {}})

    # Initialize users when they change names
    def init_user(username: str, user_id: str):
        if username and username not in active_users:
            active_users[username] = {"id": user_id, "joined": datetime.now()}
            screen_streamer.add_user(username)
        return username
    
    user1_name.change(init_user, inputs=[user1_name, gr.State("user1")], outputs=[user1_name])
    user2_name.change(init_user, inputs=[user2_name, gr.State("user2")], outputs=[user2_name])

    # Handle screen capture toggles with quality settings
    def toggle_user_screen(enabled: bool, username: str, quality: str, follow_mouse: bool):
        if username in active_users:
            screen_streamer.toggle_capture(username, enabled)
            if enabled:
                screen_streamer.users[username]['quality'] = quality
                screen_streamer.users[username]['follow_mouse'] = follow_mouse
            return gr.update(visible=enabled)
        return gr.update(visible=False)
    
    # User 1 screen controls
    user1_screen_toggle.change(
        fn=lambda e, n, q, f: toggle_user_screen(e, n, q, f),
        inputs=[user1_screen_toggle, user1_name, user1_quality, user1_follow_mouse],
        outputs=[user1_screen]
    )
    
    user1_quality.change(
        fn=lambda q, n: screen_streamer.users[n].update({'quality': q}) if n in screen_streamer.users else None,
        inputs=[user1_quality, user1_name]
    )
    
    user1_follow_mouse.change(
        fn=lambda f, n: screen_streamer.toggle_follow_mouse(n, f),
        inputs=[user1_follow_mouse, user1_name]
    )
    
    # User 2 screen controls
    user2_screen_toggle.change(
        fn=lambda e, n, q, f: toggle_user_screen(e, n, q, f),
        inputs=[user2_screen_toggle, user2_name, user2_quality, user2_follow_mouse],
        outputs=[user2_screen]
    )
    
    user2_quality.change(
        fn=lambda q, n: screen_streamer.users[n].update({'quality': q}) if n in screen_streamer.users else None,
        inputs=[user2_quality, user2_name]
    )
    
    user2_follow_mouse.change(
        fn=lambda f, n: screen_streamer.toggle_follow_mouse(n, f),
        inputs=[user2_follow_mouse, user2_name]
    )
    
    # Enhanced stream functions with better performance
    def stream_user_screen(username: str):
        """Stream screen for a user with enhanced quality."""
        frame = screen_streamer.get_frame(username)
        if frame is not None:
            # Convert to PIL Image
            pil_image = Image.fromarray(frame)
            return pil_image
        else:
            # Return placeholder when no frame
            placeholder = Image.new('RGB', (640, 480), color='black')
            draw = ImageDraw.Draw(placeholder)
            text = f"{username}'s Screen (Not sharing)"
            draw.text((20, 20), text, fill='white')
            return placeholder
    
    # Create update functions for streaming
    def update_user1_screen():
        """Update function for user1 screen streaming."""
        while True:
            if screen_streamer.users.get("User1", {}).get('enabled', False):
                yield stream_user_screen("User1")
            else:
                # Return black frame when not enabled
                placeholder = Image.new('RGB', (640, 480), color='black')
                draw = ImageDraw.Draw(placeholder)
                draw.text((20, 20), "User1's Screen (Not sharing)", fill='white')
                yield placeholder
            time.sleep(0.033)  # ~30 FPS
    
    def update_user2_screen():
        """Update function for user2 screen streaming."""
        while True:
            if screen_streamer.users.get("User2", {}).get('enabled', False):
                yield stream_user_screen("User2")
            else:
                # Return black frame when not enabled
                placeholder = Image.new('RGB', (640, 480), color='black')
                draw = ImageDraw.Draw(placeholder)
                draw.text((20, 20), "User2's Screen (Not sharing)", fill='white')
                yield placeholder
            time.sleep(0.033)  # ~30 FPS

    def chat_wrapper(message: str, username: str, target_screen: str, personality_mode: str, history: list):
        if not message.strip():
            return history, history, ""
            
        # Add user message to history with formatting
        user_display = format_message_with_user(username, message)
        history.append({"role": "user", "content": user_display})
        
        # Get AI response
        ai_response = respond(message, username, target_screen, personality_mode)
        
        # Add AI response to history
        ai_display = f"**To {username}:** {ai_response}"
        history.append({"role": "assistant", "content": ai_display})
        
        return history, history, ""

    # Handle send buttons for both users
    user1_send.click(
        lambda msg, name, screen, pers, hist: chat_wrapper(msg, name, screen, pers, hist),
        inputs=[user1_msg, user1_name, whose_screen, personality, chatbot],
        outputs=[chatbot, chatbot, user1_msg]
    )
    
    user2_send.click(
        lambda msg, name, screen, pers, hist: chat_wrapper(msg, name, screen, pers, hist),
        inputs=[user2_msg, user2_name, whose_screen, personality, chatbot],
        outputs=[chatbot, chatbot, user2_msg]
    )
    
    # Handle enter key for both users
    user1_msg.submit(
        lambda msg, name, screen, pers, hist: chat_wrapper(msg, name, screen, pers, hist),
        inputs=[user1_msg, user1_name, whose_screen, personality, chatbot],
        outputs=[chatbot, chatbot, user1_msg]
    )
    
    user2_msg.submit(
        lambda msg, name, screen, pers, hist: chat_wrapper(msg, name, screen, pers, hist),
        inputs=[user2_msg, user2_name, whose_screen, personality, chatbot],
        outputs=[chatbot, chatbot, user2_msg]
    )
    
    # Clear button
    clear_btn.click(
        lambda: [],
        outputs=[chatbot]
    )
    
    # Update stats periodically
    def update_stats():
        stats = {
            "active_users": len(active_users),
            "screens_shared": sum(1 for u in screen_streamer.users.values() if u['enabled']),
        }
        
        stats_text = f"""### Session Statistics
- **Active Users:** {stats['active_users']}
- **Screens Shared:** {stats['screens_shared']}
- **Session Time:** {datetime.now().strftime('%H:%M:%S')}
"""
        
        for username, user_data in screen_streamer.users.items():
            if user_data['enabled']:
                stats_text += f"\n**{username} Screen:**"
                stats_text += f"\n- FPS: {user_data.get('fps_actual', 0):.1f}"
                stats_text += f"\n- Quality: {user_data.get('quality', 'adaptive')}"
        
        return stats_text
    
    # Welcome message
    demo.load(
        lambda: [{"role": "assistant", "content": """Hey everyone! I'm Lilith, your collaborative coding AI! 👾

**What I can do:**
- 🖥️ **See your shared screens** and help debug code
- 🐍 **Write and execute Python code** 
- 📁 **Create files and projects** in the workspace
- 👥 **Support multiple users** simultaneously
- 🎭 **Change personalities** to match your style

**Quick tips:**
- Share your screen to show me your code
- I save all files in `lilith_workspace/`
- Try different personality modes!

What would you like to create together today? 🚀"""}],
        outputs=[chatbot]
    )

if __name__ == "__main__":
    # Create workspace directory
    workspace = Path.cwd() / "lilith_workspace"
    workspace.mkdir(exist_ok=True)
    
    print(f"👾 Starting Lilith - Advanced Collaborative Coding AI!")
    print(f"📁 Workspace: {workspace}")
    print(f"🌐 Make sure LM Studio is running!")
    print(f"🚀 Ready to code together!")
    
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7861, 
        share=True,
        show_error=True
    )