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
from .computer_control import (
    get_computer_controller,
    ComputerController,
    ComputerControlConfig,
    capture_screen,
    extract_text_from_screen,
    click_at_text,
    get_all_windows,
    analyze_full_screen,
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

        # Optional LM-Studio connector
        try:
            self.lm_connector = get_lm_studio_connector()
        except Exception as e:
            log.warning("LM Studio connector unavailable: %s", e)
            self.lm_connector = None

        self.tools = LilithTools()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
        # Initialize computer control
        try:
            self.computer_controller = get_computer_controller()
            log.info("✅ Computer control initialized with full capabilities")
        except Exception as e:
            log.warning("⚠️ Computer control initialization failed: %s", e)
            self.computer_controller = None

        # Start MCP servers async (if available)
        if MCP_AVAILABLE:
            threading.Thread(target=self._init_mcp_async, daemon=True).start()

    # ------------------------------------------------------------------
    #  MCP server initialisation (unchanged except for logging)
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
            # Enlève la partie tool-call du texte avant de retourner
            ai_response = self._strip_command_blocks(ai_response)

            if results:
                ai_response += "\n\n" + "\n".join(results)

        return ai_response

    # ------------------------------------------------------------------
    #  Prompt builder  (identique à ta version – raccourci ici)
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        user_msg: str,
        image_frame: np.ndarray | None,
        personality: str,
        stream_context: dict | None,
    ) -> list[dict]:
        """Construit le prompt system + user (version abrégée pour lisibilité)."""
        system_prompt = f"""You are Lilith (personality: {personality})
schema_version: 0.4
ENHANCED COMPUTER CONTROL TOOLS:
- capture_full_screen(monitor=0) - Capture entire screen with OCR analysis
- analyze_screen(monitor=0, include_ocr=True) - Complete screen analysis with text extraction
- click_at_text(text, monitor=0) - Find and click on specific text
- click_screen(x,y | x_rel,y_rel, button="left") - Precise mouse control
- type_text(text, interval=0.0) - Advanced keyboard input
- press_key(key, presses=1) - Keyboard key control
- key_combination(keys_list) - Keyboard shortcuts (e.g., ["ctrl", "c"])
- drag_mouse(start_x, start_y, end_x, end_y, duration=1.0) - Drag operations
- scroll_at(x, y, clicks=3, direction="up") - Mouse scrolling
- get_all_windows() - List all open windows
- activate_window(title_pattern) - Switch to specific window
- resize_window(title_pattern, width, height) - Resize window
- move_window(title_pattern, x, y) - Move window
- get_system_info() - Comprehensive system information
- automate_task(description, steps_list) - Execute automation sequence

CLASSIC TOOLS:
- execute_python(code, timeout)
- execute_command(command, timeout)
- read_file(filepath)
- take_screenshot() - Basic screenshot

ENHANCED VISION CAPABILITIES:
- Full screen OCR with text detection and bounding boxes
- UI element detection (buttons, text fields, etc.)
- Multi-monitor support
- Window management and automation
- Advanced input control with safety limits

RULES:
• When calling a tool, reply ONLY with the JSON object {{ "name": "...", "arguments": {{...}} }}.
• No other text in that message.
• Use x_rel / y_rel (0-1) when derived from an image.
• For complex tasks, use analyze_screen() first to understand the interface.
• Always use capture_full_screen() for comprehensive screen analysis.
• Use click_at_text() to interact with UI elements by their text content.
"""
        messages = [{"role": "system", "content": system_prompt}]
        content_block = [{"type": "text", "text": user_msg}]
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
        _, buf = cv2.imencode(".jpg", frame)
        return base64.b64encode(buf).decode()

    def _llm_complete(self, messages: list, max_tokens: int, temperature: float):
        """Appelle LM Studio directement (sans streaming)."""
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
    #  Command detection (nouveau JSON + anciens regex)
    # ------------------------------------------------------------------
    def _extract_all_commands(self, text: str) -> list[dict]:
        """Renvoie une liste d’objets commande {'type':…, 'name':…, 'args':…}."""
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

        # --- LEGACY COMMANDS (extraits comme avant) ----------------------
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
                    # Enhanced computer control tools
                    if name == "capture_full_screen":
                        if self.computer_controller:
                            monitor = args.get("monitor", 0)
                            screenshot_b64 = capture_screen(monitor)
                            results.append(f"📸 Full screen captured from monitor {monitor}")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "analyze_screen":
                        if self.computer_controller:
                            analysis = analyze_full_screen(args.get("monitor", 0))
                            text_found = len(analysis.get("text_elements", []))
                            ui_found = len(analysis.get("ui_elements", []))
                            windows_found = len(analysis.get("windows", []))
                            results.append(f"🔍 Screen analysis: {text_found} text elements, {ui_found} UI elements, {windows_found} windows")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "click_at_text":
                        if self.computer_controller:
                            text = args.get("text", "")
                            monitor = args.get("monitor", 0)
                            success = click_at_text(text, monitor)
                            if success:
                                results.append(f"🎯 Clicked on text: '{text}'")
                            else:
                                results.append(f"❌ Text not found: '{text}'")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "get_all_windows":
                        if self.computer_controller:
                            windows = get_all_windows()
                            results.append(f"🖼️ Found {len(windows)} windows")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "activate_window":
                        if self.computer_controller:
                            title = args.get("title_pattern", "")
                            success = self.computer_controller.window_manager.activate_window(title)
                            if success:
                                results.append(f"✅ Activated window: '{title}'")
                            else:
                                results.append(f"❌ Window not found: '{title}'")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "resize_window":
                        if self.computer_controller:
                            title = args.get("title_pattern", "")
                            width = args.get("width", 800)
                            height = args.get("height", 600)
                            success = self.computer_controller.window_manager.resize_window(title, width, height)
                            if success:
                                results.append(f"📏 Resized window '{title}' to {width}x{height}")
                            else:
                                results.append(f"❌ Failed to resize window: '{title}'")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "move_window":
                        if self.computer_controller:
                            title = args.get("title_pattern", "")
                            x = args.get("x", 0)
                            y = args.get("y", 0)
                            success = self.computer_controller.window_manager.move_window(title, x, y)
                            if success:
                                results.append(f"📍 Moved window '{title}' to ({x}, {y})")
                            else:
                                results.append(f"❌ Failed to move window: '{title}'")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "press_key":
                        if self.computer_controller:
                            key = args.get("key", "")
                            presses = args.get("presses", 1)
                            success = self.computer_controller.input.press_key(key, presses)
                            if success:
                                results.append(f"⌨️ Pressed key: {key} ({presses} times)")
                            else:
                                results.append(f"❌ Failed to press key: {key}")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "key_combination":
                        if self.computer_controller:
                            keys = args.get("keys", [])
                            success = self.computer_controller.input.key_combination(keys)
                            if success:
                                results.append(f"⌨️ Key combination: {'+'.join(keys)}")
                            else:
                                results.append(f"❌ Failed key combination: {'+'.join(keys)}")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "drag_mouse":
                        if self.computer_controller:
                            start_x = args.get("start_x", 0)
                            start_y = args.get("start_y", 0)
                            end_x = args.get("end_x", 0)
                            end_y = args.get("end_y", 0)
                            duration = args.get("duration", 1.0)
                            success = self.computer_controller.input.drag(start_x, start_y, end_x, end_y, duration)
                            if success:
                                results.append(f"🖱️ Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
                            else:
                                results.append("❌ Drag operation failed")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "scroll_at":
                        if self.computer_controller:
                            x = args.get("x", 0)
                            y = args.get("y", 0)
                            clicks = args.get("clicks", 3)
                            direction = args.get("direction", "up")
                            success = self.computer_controller.input.scroll(x, y, clicks, direction)
                            if success:
                                results.append(f"🖱️ Scrolled {direction} at ({x}, {y})")
                            else:
                                results.append("❌ Scroll operation failed")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "get_system_info":
                        if self.computer_controller:
                            info = self.computer_controller.get_system_info()
                            monitors = len(info.get("monitors", []))
                            cpu = info.get("cpu_percent", 0)
                            memory = info.get("memory_percent", 0)
                            results.append(f"💻 System: {monitors} monitors, CPU: {cpu:.1f}%, RAM: {memory:.1f}%")
                        else:
                            results.append("❌ Computer control not available")
                    
                    elif name == "automate_task":
                        if self.computer_controller:
                            description = args.get("description", "")
                            steps = args.get("steps", [])
                            result = self.computer_controller.automate_task(description, steps)
                            if result.get("success"):
                                completed = len(result.get("results", []))
                                results.append(f"🤖 Automation '{description}': {completed} steps completed")
                            else:
                                error = result.get("error", "Unknown error")
                                results.append(f"❌ Automation failed: {error}")
                        else:
                            results.append("❌ Computer control not available")
                    
                    # Legacy tools
                    elif name == "type_text":
                        if self.computer_controller:
                            text = args.get("text", "")
                            interval = args.get("interval", 0.0)
                            success = self.computer_controller.input.type_text(text, interval)
                            if success:
                                results.append(f"⌨️ Typed: {len(text)} characters")
                            else:
                                results.append("❌ Type text failed")
                        else:
                            type_text(**args)
                            results.append("⌨️ Typed (legacy mode).")
                    
                    elif name == "click_screen":
                        # Handle both new and legacy click
                        if self.computer_controller:
                            x = args.get("x")
                            y = args.get("y")
                            x_rel = args.get("x_rel")
                            y_rel = args.get("y_rel")
                            button = args.get("button", "left")
                            
                            if x_rel is not None and y_rel is not None:
                                success = self.computer_controller.input.click_relative(x_rel, y_rel, button)
                            elif x is not None and y is not None:
                                success = self.computer_controller.input.click(x, y, button)
                            else:
                                success = False
                            
                            if success:
                                results.append(f"🖱️ Clicked at specified location")
                            else:
                                results.append("❌ Click failed")
                        else:
                            click_screen(**args)
                            results.append("🖱️ Clicked (legacy mode).")
                    
                    elif name == "move_mouse":
                        if self.computer_controller:
                            # Convert move_mouse to pyautogui.moveTo
                            import pyautogui
                            x = args.get("x")
                            y = args.get("y") 
                            x_rel = args.get("x_rel")
                            y_rel = args.get("y_rel")
                            duration = args.get("duration", 0.2)
                            
                            if x_rel is not None and y_rel is not None:
                                screen_width, screen_height = pyautogui.size()
                                x = int(x_rel * screen_width)
                                y = int(y_rel * screen_height)
                            
                            if x is not None and y is not None:
                                pyautogui.moveTo(x, y, duration=duration)
                                results.append(f"↔️ Moved mouse to ({x}, {y})")
                            else:
                                results.append("❌ Move mouse failed")
                        else:
                            move_mouse(**args)
                            results.append("↔️ Moved (legacy mode).")
                    
                    elif name == "take_screenshot":
                        if self.computer_controller:
                            screenshot_b64 = capture_screen(0)
                            results.append(f"📸 Screenshot captured ({len(screenshot_b64)//1024} KB)")
                        else:
                            img = take_screenshot()
                            results.append(f"📸 Screenshot captured (legacy mode).")
                    
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
