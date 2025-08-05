"""Lilith Ultimate Controller – v0.4
Entièrement compatible RTX-3060 + AB498 Control JSON tools.
"""
from __future__ import annotations

# ----------------------------------------------------------------------
#  Imports & initialisation
# ----------------------------------------------------------------------
from pathlib import Path
import base64
from openai import OpenAI
import numpy as np
import cv2
import json
import re
from typing import Dict, Any, Optional, List
import random
from datetime import datetime
import asyncio
import os
import threading
import concurrent.futures
import psutil
import logging

from .tools import (
    LilithTools,
    type_text,
    click_screen,
    move_mouse,
    take_screenshot,
)
from .lm_studio_connector import get_lm_studio_connector

# Try MCP manager (optional)
try:
    from .mcp_manager import mcp_manager
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    mcp_manager = None  # type: ignore

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("controller")

# ----------------------------------------------------------------------
#  Controller class
# ----------------------------------------------------------------------
class LilithControllerUltimate:
    """Ultimate controller with ALL features (MCP, vision, streaming, AB498…)."""

    def __init__(self, base_url: str = "http://127.0.0.1:1234"):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/v1"
        self.client = OpenAI(base_url=self.api_url, api_key="not-needed")
        
        # Stream management
        self.current_view = "AI"  # Current view (AI, or username)
        self.active_streams = []  # List of active streams
        self.auto_view_selection = True  # Enable automatic view selection
        self.last_view_change = datetime.now()  # Timestamp of last view change
        self.view_change_cooldown = 5  # Seconds cooldown between view changes

        # Optional LM-Studio connector
        try:
            self.lm_connector = get_lm_studio_connector()
        except Exception as e:
            log.warning("LM Studio connector unavailable: %s", e)
            self.lm_connector = None

        self.tools = LilithTools()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        # Start MCP servers async (if available)
        if MCP_AVAILABLE:
            threading.Thread(target=self._init_mcp_async, daemon=True).start()

    # ------------------------------------------------------------------
    #  MCP server initialisation
    # ------------------------------------------------------------------
    def _init_mcp_async(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if loop.run_until_complete(mcp_manager.start_server("ab498_control")):
            log.info("✅ AB498 Control server detected & started")
        else:
            log.warning("⚠️  AB498 Control server unavailable")
        loop.close()

    # ------------------------------------------------------------------
    #  Auto view selection - New functionality
    # ------------------------------------------------------------------
    def select_best_view(self, available_streams: List[str]) -> str:
        """
        Automatically select the best view to observe based on 
        available streams and activity.
        """
        if not self.auto_view_selection or not available_streams:
            return self.current_view
        
        # Respect cooldown to avoid changing too often
        now = datetime.now()
        if (now - self.last_view_change).total_seconds() < self.view_change_cooldown:
            return self.current_view
            
        # Priority 1: If a user recently activated screen sharing, watch them
        user_screens = [stream for stream in available_streams 
                       if stream != "AI" and not stream.startswith("VTube")]
        
        if user_screens and self.current_view == "AI":
            # Switch to user stream
            self.current_view = user_screens[0]
            self.last_view_change = now
            log.info(f"🔄 View automatically changed to: {self.current_view}")
            return self.current_view
            
        # If currently on user stream but it's no longer active, return to AI
        if self.current_view not in available_streams and "AI" in available_streams:
            self.current_view = "AI"
            self.last_view_change = now
            log.info("🔄 View reset to AI (previous stream inactive)")
            return self.current_view
            
        # Otherwise keep current view if still available
        if self.current_view in available_streams:
            return self.current_view
            
        # Default, use first available stream
        if available_streams:
            self.current_view = available_streams[0]
            self.last_view_change = now
            log.info(f"🔄 View automatically set to: {self.current_view}")
            return self.current_view
            
        return "AI"  # Default view

    # ------------------------------------------------------------------
    #  Chat entry point
    # ------------------------------------------------------------------
    def chat(
        self,
        user_msg: str,
        image_frame: np.ndarray | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        personality: str = "Playful",
        stream_context: dict | None = None,
    ) -> str:
        """Send a chat message to the language model and post-process tool-calls."""
        # Update active streams and select best view
        if stream_context and "active_streams" in stream_context:
            self.active_streams = stream_context["active_streams"]
            
            # Automatic view selection if enabled
            if self.auto_view_selection:
                selected_view = self.select_best_view(self.active_streams)
                if selected_view != self.current_view:
                    log.info(f"🔄 Changing view from {self.current_view} to {selected_view}")
                    self.current_view = selected_view
                    
            # Add current view info to context
            if stream_context:
                stream_context["current_view"] = self.current_view
                
        # Build prompt and send to model
        messages = self._build_prompt(user_msg, image_frame, personality, stream_context)

        # --- completions ---
        response = self._llm_complete(messages, max_tokens, temperature)
        if not response:
            return "❌ Unable to get response from LM Studio."

        ai_response = response.choices[0].message.content

        # --- detect / execute tools (sync) ---
        commands = self._extract_all_commands(ai_response)
        if commands:
            results = self._execute_sync_commands(commands)
            # Remove tool-call part from text before returning
            ai_response = self._strip_command_blocks(ai_response)

            if results:
                ai_response += "\n\n" + "\n".join(results)

        return ai_response

    # ------------------------------------------------------------------
    #  Prompt builder (modified to include current view)
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        user_msg: str,
        image_frame: np.ndarray | None,
        personality: str,
        stream_context: dict | None = None,
    ) -> list[dict]:
        """Build system + user prompt with current context."""
        system_prompt = f"""You are Lilith (personality: {personality})
schema_version: 0.4
TOOLS:
- execute_python(code, timeout)
- execute_command(command, timeout)
- read_file(filepath)
- type_text(text, interval)
- click_screen(x,y | x_rel,y_rel, button)
- move_mouse(x,y | x_rel,y_rel, duration)
- take_screenshot()
- change_view(view) - Change which stream to watch

VISION:
- You have full vision capabilities
- You are currently watching: {self.current_view}
- Available streams: {', '.join(self.active_streams) if self.active_streams else 'None'}

RULES:
• When calling a tool, reply ONLY with the JSON object {{ "name": "...", "arguments": {{...}} }}.
• No other text in that message.
• Use x_rel / y_rel (0-1) when derived from an image.
"""
        messages = [{"role": "system", "content": system_prompt}]

        # Build user message
        content_block = [{"type": "text", "text": user_msg}]

        # Add image if available
        if image_frame is not None:
            img_b64 = self._encode_image(image_frame)
            content_block.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            )

        messages.append({"role": "user", "content": content_block})
        return messages

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    def _encode_image(self, frame: np.ndarray) -> str:
        """Encode image without ANY resizing to guarantee complete vision."""
        try:
            # Check if image is valid
            if frame is None or frame.size == 0:
                log.warning("❌ Invalid image received")
                return ""
            
            # Use image as-is, without ANY transformation
            # Simply convert BGR to RGB if necessary
            if len(frame.shape) == 3 and frame.shape[2] == 3 and frame.dtype == np.uint8:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            
            # Log original dimensions (crucial for diagnosis)
            h, w = frame_rgb.shape[:2]
            log.info(f"🔍 Original image dimensions: {w}x{h} pixels")
            
            # NO resizing whatsoever, regardless of size
            
            # Encode to JPEG with maximum quality
            success, buffer = cv2.imencode('.jpg', frame_rgb, [cv2.IMWRITE_JPEG_QUALITY, 100])
            if not success:
                log.warning("❌ Image encoding failed")
                return ""
            
            # Log size for diagnosis
            file_size_kb = len(buffer) / 1024
            log.info(f"📦 Encoded image size: {file_size_kb:.2f} KB")
            
            # Force standard base64 format (without optional padding)
            b64_str = base64.b64encode(buffer).decode('utf-8')
            
            return b64_str
            
        except Exception as e:
            log.error(f"❌ Image encoding error: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _llm_complete(self, messages: list, max_tokens: int, temperature: float):
        """Call LM Studio directly (no streaming)."""
        try:
            return self.client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
        except Exception as e:
            log.error("LLM completion failed: %s", e)
            return None

    # ------------------------------------------------------------------
    #  Command detection (new JSON + legacy regex)
    # ------------------------------------------------------------------
    def _extract_all_commands(self, text: str) -> list[dict]:
        """Return list of command objects {'type':…, 'name':…, 'args':…}."""
        commands: list[dict] = []

        # --- NEW JSON TOOL-CALL DETECTION --------------------------------
        json_pattern = r'\{\s*"name"\s*:\s*".+?"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}'
        for m in re.finditer(json_pattern, text, re.DOTALL):
            try:
                obj = json.loads(m.group(0))
                if "name" in obj and "arguments" in obj:
                    commands.append({"type": "json_tool", "name": obj["name"], "args": obj["arguments"]})
            except json.JSONDecodeError:
                pass  # ignore malformed

        # --- LEGACY COMMANDS (extracted as before) ----------------------
        legacy = {
            "execute_python": r"EXECUTE_PYTHON:\s*```(.*?)```",
            "run_command": r"RUN_COMMAND:\s*```(.*?)```",
        }
        for typ, pat in legacy.items():
            for m in re.finditer(pat, text, re.DOTALL | re.IGNORECASE):
                commands.append({"type": typ, "code": m.group(1).strip()})

        return commands

    # ------------------------------------------------------------------
    #  Synchronised execution
    # ------------------------------------------------------------------
    def _execute_sync_commands(self, cmds: list[dict]) -> list[str]:
        results: list[str] = []

        for cmd in cmds:
            if cmd["type"] == "json_tool":
                name, args = cmd["name"], cmd["args"]
                try:
                    if name == "type_text":
                        type_text(**args)
                        results.append("⌨️ Typed.")
                    elif name == "click_screen":
                        # Extract coordinates (absolute or relative)
                        x = args.get("x")
                        y = args.get("y")
                        x_rel = args.get("x_rel")
                        y_rel = args.get("y_rel")
                        button = args.get("button", "left")
                        
                        # If relative coordinates, convert to absolute
                        if x_rel is not None and y_rel is not None:
                            import pyautogui
                            screen_w, screen_h = pyautogui.size()
                            x = int(float(x_rel) * screen_w)
                            y = int(float(y_rel) * screen_h)
                        
                        # Execute click
                        click_screen(x=x, y=y, button=button)
                        results.append(f"🖱️ Clicked at: ({x}, {y}) with {button} button.")
                    elif name == "move_mouse":
                        # Extract coordinates (absolute or relative)
                        x = args.get("x")
                        y = args.get("y")
                        x_rel = args.get("x_rel")
                        y_rel = args.get("y_rel")
                        duration = args.get("duration", 0.2)
                        
                        # If relative coordinates, convert to absolute
                        if x_rel is not None and y_rel is not None:
                            import pyautogui
                            screen_w, screen_h = pyautogui.size()
                            x = int(float(x_rel) * screen_w)
                            y = int(float(y_rel) * screen_h)
                        
                        # Move mouse
                        move_mouse(x=x, y=y, duration=duration)
                        results.append(f"↔️ Moved mouse to: ({x}, {y}).")
                    elif name == "take_screenshot":
                        img = take_screenshot()
                        results.append(f"📸 Screenshot captured ({len(img)//1024} KB).")
                    elif name == "execute_python":
                        r = self.tools.execute_python(args["code"], args.get("timeout", 10))
                        results.append(f"🐍 Python → {r['stdout'] or r['stderr']}")
                    elif name == "execute_command":
                        r = self.tools.execute_command(args["command"], args.get("timeout", 30))
                        results.append(f"🖥️ CMD → {r['stdout'] or r['stderr']}")
                    elif name == "read_file":
                        r = self.tools.read_file(args["filepath"])
                        if r["success"]:
                            results.append(f"📄 File content ({args['filepath']}): {r['content'][:100]}...")
                        else:
                            results.append(f"❌ File read error: {r['error']}")
                    elif name == "change_view":
                        # New functionality: change AI's view
                        new_view = args.get("view")
                        if new_view and new_view in self.active_streams:
                            self.current_view = new_view
                            self.last_view_change = datetime.now()
                            results.append(f"👁️ Changed view to: {new_view}")
                        else:
                            results.append(f"❌ Cannot change to view '{new_view}' (not available)")
                    else:
                        results.append(f"⚠️ Unknown tool '{name}'.")
                except Exception as e:
                    results.append(f"❌ Error running {name}: {e}")

            elif cmd["type"] == "execute_python":
                r = self.tools.execute_python(cmd["code"])
                results.append(f"🐍 Python → {r['stdout'] or r['stderr']}")
            elif cmd["type"] == "run_command":
                r = self.tools.execute_command(cmd["code"])
                results.append(f"🖥️ CMD → {r['stdout'] or r['stderr']}")

        return results

    # ------------------------------------------------------------------
    #  Strip command blocks from AI answer (avoid echoing raw JSON)
    # ------------------------------------------------------------------
    @staticmethod
    def _strip_command_blocks(text: str) -> str:
        text = re.sub(r'\{\s*"name"\s*:.*?\}\s*', "", text, flags=re.DOTALL)
        text = re.sub(r"EXECUTE_PYTHON:\s*```.*?```", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"RUN_COMMAND:\s*```.*?```", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()

    # ------------------------------------------------------------------
    #  Configuration du streaming
    # ------------------------------------------------------------------
    def set_view(self, view: str) -> bool:
        """
        Définit manuellement quelle vue l'IA doit regarder.
        
        Args:
            view: "AI" pour l'écran de l'IA ou le nom d'un utilisateur
                 dont le partage est actif
        
        Returns:
            bool: True si le changement a réussi
        """
        if view in self.active_streams or view == "AI":
            self.current_view = view
            self.last_view_change = datetime.now()
            log.info(f"👁️ Vue manuellement changée vers: {view}")
            return True
        log.warning(f"❌ Vue demandée non disponible: {view}")
        return False
    
    def toggle_auto_view_selection(self, enabled: bool) -> None:
        """Active ou désactive la sélection automatique de la vue."""
        self.auto_view_selection = enabled
        log.info(f"🔄 Sélection auto de vue: {'activée' if enabled else 'désactivée'}")

    def get_current_view(self) -> str:
        """Retourne la vue actuellement utilisée par l'IA."""
        return self.current_view


# ----------------------------------------------------------------------
#  Simple self-test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    ctl = LilithControllerUltimate()
    print("🚀 Controller ready. Type 'exit' to quit.")
    while True:
        msg = input("You: ")
        if msg.lower() == "exit":
            break
        print("AI:", ctl.chat(msg))