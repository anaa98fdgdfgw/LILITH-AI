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
schema_version: 0.3
TOOLS:
- execute_python(code, timeout)
- execute_command(command, timeout)
- read_file(filepath)
- type_text(text, interval)
- click_screen(x,y | x_rel,y_rel, button)
- move_mouse(x,y | x_rel,y_rel, duration)
- take_screenshot()

RULES:
• When calling a tool, reply ONLY with the JSON object {{ "name": "...", "arguments": {{...}} }}.
• No other text in that message.
• Use x_rel / y_rel (0-1) when derived from an image.
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
                    if name == "type_text":
                        type_text(**args)
                        results.append("⌨️ Typed.")
                    elif cmd["action"] == "click":
                    xs, ys = cmd["params"].split()[:2]

                     # ───────────  NOUVEAU  ───────────
                    import pyautogui
                    scr_w, scr_h = pyautogui.size()          # taille du bureau virtuel
                    x = float(xs)
                    y = float(ys)
                    # si les valeurs sont des ratios 0-1, on les projette en pixels
                    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                        x *= scr_w
                        y *= scr_h
                     x = int(round(x))
                     y = int(round(y))
                     # ─────────────────────────────────

                     await mcp_mouse_click(x, y)
                     return f"🖱️ **Clicked at:** ({x}, {y})"
                    elif name == "move_mouse":
                        move_mouse(**args)
                        results.append("↔️ Moved.")
                    elif name == "take_screenshot":
                        img = take_screenshot()
                        results.append(f"📸 Screenshot captured ({len(img)//1024} KB).")
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
