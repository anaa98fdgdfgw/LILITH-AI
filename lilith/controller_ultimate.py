"""Lilith Ultimate Controller - RTX 3060 Optimized with ALL features."""
from __future__ import annotations

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

from .tools import LilithTools
from .lm_studio_connector import get_lm_studio_connector, ensure_lm_studio_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import GPUtil
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False
    print("GPUtil not available, GPU monitoring disabled")

# Try to import MCP manager
try:
    from .mcp_manager import (
        mcp_manager, mcp_filesystem_read, mcp_filesystem_write, 
        mcp_github_create_issue, mcp_search_web, mcp_alpaca_get_positions, 
        mcp_alpaca_place_order, mcp_memory_store, mcp_memory_retrieve,
        mcp_mouse_move, mcp_mouse_click, mcp_keyboard_type, mcp_keyboard_hotkey
    )
    MCP_AVAILABLE = True
except:
    MCP_AVAILABLE = False
    print("MCP not available, continuing without MCP features")


class LilithControllerUltimate:
    """Ultimate controller with ALL features optimized for RTX 3060 12GB."""

    def __init__(self, base_url: str = "http://127.0.0.1:1234"):
        # Initialize with direct OpenAI client first
        self.base_url = base_url
        self.api_url = f"{base_url}/v1"
        
        # Try to use LM Studio connector if available
        try:
            self.lm_connector = get_lm_studio_connector()
            # Don't block on connection during init
            self.client = OpenAI(base_url=self.api_url, api_key="not-needed")
        except Exception as e:
            logger.warning(f"Could not initialize LM Studio connector: {e}")
            self.lm_connector = None
            # Direct client creation
            self.client = OpenAI(base_url=self.api_url, api_key="not-needed")
            
        self.tools = LilithTools()
        self.conversation_count = 0
        self.user_contexts = {}
        self.mcp_manager = mcp_manager if MCP_AVAILABLE else None
        self.mcp_servers = {}
        
        # Thread pool for parallel execution
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
        # Initialize MCP servers if available
        if MCP_AVAILABLE:
            self._start_mcp_servers_thread()
        
    def _start_mcp_servers_thread(self):
        """Start MCP servers in a separate thread."""
        def run_async_init():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._initialize_mcp_servers())
            loop.close()
        
        thread = threading.Thread(target=run_async_init, daemon=True)
        thread.start()
        
    async def _initialize_mcp_servers(self):
        """Initialize all MCP servers with proper configuration."""
        # Import mcp_config to get server settings
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from mcp_config import MCP_PORTS, MCP_ENABLED, FILESYSTEM_ALLOWED_DIRS
        except ImportError:
            logger.warning("Could not import mcp_config, using defaults")
            MCP_PORTS = {
                "filesystem": 3001,
                "github": 3002,
                "memory": 3005,
                "search": 3006,
                "time": 3009,
                "fetch": 3010,
                "ab498_control": 3011,
                "alpaca": 3012
            }
            MCP_ENABLED = {server: True for server in MCP_PORTS}
            FILESYSTEM_ALLOWED_DIRS = ["e:\\LLM-Proxy\\LILITH-AI"]
        
        # Only initialize enabled servers
        enabled_servers = [server for server, enabled in MCP_ENABLED.items() if enabled]
        
        # Store MCP configuration for injection
        self.mcp_servers = {}
        
        for server in enabled_servers:
            port = MCP_PORTS.get(server, 3000)
            self.mcp_servers[server] = {
                "enabled": True,
                "port": port,
                "running": False
            }
        
        # Special configuration for filesystem
        if "filesystem" in enabled_servers:
            filesystem_config = {
                "allowed_paths": FILESYSTEM_ALLOWED_DIRS,
                "read_only": False  # Allow modifications
            }
            self.mcp_manager.configure_server("filesystem", filesystem_config)
        
        # Start servers
        tasks = []
        for server in enabled_servers:
            try:
                logger.info(f"Starting MCP server: {server} on port {MCP_PORTS.get(server)}")
                task = asyncio.create_task(self.mcp_manager.start_server(server))
                tasks.append((server, task))
            except Exception as e:
                logger.error(f"Failed to create task for {server}: {e}")
        
        if tasks:
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            for i, (server, _) in enumerate(tasks):
                if isinstance(results[i], Exception):
                    logger.error(f"Failed to start {server}: {results[i]}")
                else:
                    self.mcp_servers[server]["running"] = True
                    logger.info(f"✅ Started {server} MCP server")
        
    @staticmethod
    def _encode_image_from_frame(frame: np.ndarray) -> str:
        """Encode with RTX 3060 optimized settings."""
        # Resize for performance - 1024px is a good balance
        max_dim = 1024
        height, width = frame.shape[:2]
        if height > max_dim or width > max_dim:
            if height > width:
                scale = max_dim / height
            else:
                scale = max_dim / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Use WebP for better quality/size ratio
        quality = 85
        success, buffer = cv2.imencode(".webp", frame, [cv2.IMWRITE_WEBP_QUALITY, quality])
        if not success:
            # Fallback to JPEG
            success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not success:
                raise ValueError("Could not encode image")
        return base64.b64encode(buffer).decode('utf-8')
    
    def _extract_all_commands(self, text: str) -> list[Dict[str, Any]]:
        """Extract ALL types of commands from the response."""
        commands = []
        
        # All command patterns
        patterns = {
            "execute_python": r'EXECUTE_PYTHON:\s*```(?:\w+)?\n(.*?)```',
            "run_command": r'RUN_COMMAND:\s*`([^`]+)`',
            "write_file": r'WRITE_FILE:\s*"([^"]+)"\s*```(?:\w+)?\n(.*?)```',
            "create_project": r'CREATE_PROJECT:\s*"([^"]+)"\s*\((\w+)\)',
            "stream_control": r'STREAM_CONTROL:\s*(\w+)\s*(\w+)(?:\s*"([^"]+)")?',
            "stream_suggest": r'STREAM_SUGGEST:\s*"([^"]+)"',
        }
        
        # Add MCP patterns if available
        if MCP_AVAILABLE:
            patterns.update({
                "mcp_search": r'MCP_SEARCH:\s*"([^"]+)"',
                "mcp_github_issue": r'MCP_GITHUB_ISSUE:\s*"([^"]+)"\s*"([^"]+)"\s*"([^"]+)"',
                "mcp_trade": r'MCP_TRADE:\s*(\w+)\s*(\d+)\s*(buy|sell)\s*(\w+)?',
                "mcp_memory": r'MCP_MEMORY:\s*(store|retrieve)\s*"([^"]+)"(?:\s*"([^"]+)")?',
                "mcp_control": r'MCP_CONTROL:\s*(\w+)(?:\s+(.+))?'
            })
        
        for cmd_type, pattern in patterns.items():
            for match in re.finditer(pattern, text, re.DOTALL | re.MULTILINE):
                if cmd_type == "execute_python":
                    commands.append({"type": cmd_type, "code": match.group(1).strip()})
                elif cmd_type == "run_command":
                    commands.append({"type": cmd_type, "command": match.group(1).strip()})
                elif cmd_type == "write_file":
                    commands.append({
                        "type": cmd_type,
                        "filepath": match.group(1).strip(),
                        "content": match.group(2).strip()
                    })
                elif cmd_type == "create_project":
                    commands.append({
                        "type": cmd_type,
                        "name": match.group(1).strip(),
                        "project_type": match.group(2).strip()
                    })
                elif cmd_type == "mcp_search" and MCP_AVAILABLE:
                    commands.append({"type": cmd_type, "query": match.group(1).strip()})
                elif cmd_type == "mcp_github_issue" and MCP_AVAILABLE:
                    commands.append({
                        "type": cmd_type,
                        "repo": match.group(1).strip(),
                        "title": match.group(2).strip(),
                        "body": match.group(3).strip()
                    })
                elif cmd_type == "mcp_trade" and MCP_AVAILABLE:
                    commands.append({
                        "type": cmd_type,
                        "symbol": match.group(1).strip(),
                        "qty": int(match.group(2).strip()),
                        "side": match.group(3).strip(),
                        "order_type": match.group(4).strip() if match.group(4) else "market"
                    })
                elif cmd_type == "mcp_memory" and MCP_AVAILABLE:
                    commands.append({
                        "type": cmd_type,
                        "action": match.group(1).strip(),
                        "key": match.group(2).strip(),
                        "value": match.group(3).strip() if match.group(3) else None
                    })
                elif cmd_type == "mcp_control" and MCP_AVAILABLE:
                    action = match.group(1).strip()
                    params = match.group(2).strip() if match.group(2) else ""
                    commands.append({
                        "type": cmd_type,
                        "action": action,
                        "params": params
                    })
                elif cmd_type == "stream_control":
                    commands.append({
                        "type": cmd_type,
                        "action": match.group(1).strip(),
                        "stream_type": match.group(2).strip(),
                        "reason": match.group(3).strip() if match.group(3) else None
                    })
                elif cmd_type == "stream_suggest":
                    commands.append({
                        "type": cmd_type,
                        "suggestion": match.group(1).strip()
                    })
            
        return commands
    
    def _execute_sync_command(self, cmd: Dict[str, Any]) -> str:
        """Execute synchronous commands."""
        try:
            if cmd["type"] == "execute_python":
                result = self.tools.execute_python(cmd["code"])
                if result['success']:
                    return f"✅ **Python Success!**\n```\n{result['stdout']}\n```"
                else:
                    return f"❌ **Python Error:**\n```\n{result['stderr']}\n```"
                    
            elif cmd["type"] == "run_command":
                result = self.tools.execute_command(cmd["command"])
                if result['success']:
                    return f"💻 **Command:** `{cmd['command']}`\n```\n{result['stdout']}\n```"
                else:
                    return f"❌ **Command Error:**\n```\n{result['stderr']}\n```"
                    
            elif cmd["type"] == "write_file":
                result = self.tools.write_file(cmd["filepath"], cmd["content"])
                if result['success']:
                    return f"📄 **File created:** `{cmd['filepath']}` ✨"
                else:
                    return f"❌ **Failed to create file:** {result['error']}"
                    
            elif cmd["type"] == "create_project":
                result = self.tools.create_project(cmd["name"], cmd["project_type"])
                if result['success']:
                    return f"🚀 **Project created:** `{cmd['name']}` at {result['path']}"
                else:
                    return f"❌ **Failed to create project:** {result['error']}"
                    
        except Exception as e:
            return f"❌ **Error executing {cmd['type']}:** {str(e)}"
    
    async def _execute_async_command(self, cmd: Dict[str, Any]) -> str:
        """Execute asynchronous MCP commands."""
        if not MCP_AVAILABLE:
            return "❌ MCP not available"
            
        try:
            if cmd["type"] == "mcp_search":
                result = await mcp_search_web(cmd["query"])
                if "error" not in result:
                    return f"🔍 **Web Search:** `{cmd['query']}`\n{json.dumps(result, indent=2)[:500]}..."
                else:
                    return f"❌ **Search Error:** {result['error']}"
                    
            elif cmd["type"] == "mcp_github_issue":
                result = await mcp_github_create_issue(cmd["repo"], cmd["title"], cmd["body"])
                if "error" not in result:
                    return f"📝 **GitHub Issue Created:** {cmd['title']} in {cmd['repo']}"
                else:
                    return f"❌ **GitHub Error:** {result['error']}"
                    
            elif cmd["type"] == "mcp_trade":
                result = await mcp_alpaca_place_order(
                    cmd["symbol"], cmd["qty"], cmd["side"], cmd["order_type"]
                )
                if "error" not in result:
                    return f"📈 **Trade Executed:** {cmd['side']} {cmd['qty']} {cmd['symbol']}"
                else:
                    return f"❌ **Trade Error:** {result['error']}"
                    
            elif cmd["type"] == "mcp_memory":
                if cmd["action"] == "store":
                    result = await mcp_memory_store(cmd["key"], cmd["value"])
                    return f"💾 **Stored:** {cmd['key']}"
                else:
                    result = await mcp_memory_retrieve(cmd["key"])
                    if "error" not in result:
                        return f"🧠 **Retrieved:** {cmd['key']} = {result}"
                    else:
                        return f"❌ **Memory Error:** {result['error']}"
                        
            elif cmd["type"] == "mcp_control":
                if cmd["action"] == "click":
                    coords = cmd["params"].split()
                    if len(coords) >= 2:
                        result = await mcp_mouse_click(int(coords[0]), int(coords[1]))
                        return f"🖱️ **Clicked at:** ({coords[0]}, {coords[1]})"
                elif cmd["action"] == "type":
                    result = await mcp_keyboard_type(cmd["params"].strip('"'))
                    return f"⌨️ **Typed:** {cmd['params']}"
                elif cmd["action"] == "hotkey":
                    keys = cmd["params"].strip('[]').split(',')
                    result = await mcp_keyboard_hotkey([k.strip().strip('"') for k in keys])
                    return f"⌨️ **Hotkey:** {cmd['params']}"
                    
        except Exception as e:
            return f"❌ **Error executing {cmd['type']}:** {str(e)}"
    
    async def _execute_commands_parallel(self, commands: list[Dict[str, Any]]) -> str:
        """Execute commands in parallel for maximum performance."""
        results = []
        
        # Group commands by type
        sync_commands = []
        async_commands = []
        
        for cmd in commands:
            if cmd["type"] in ["execute_python", "run_command", "write_file", "create_project"]:
                sync_commands.append(cmd)
            else:
                async_commands.append(cmd)
        
        # Execute sync commands in thread pool
        if sync_commands:
            sync_futures = []
            for cmd in sync_commands:
                future = self.executor.submit(self._execute_sync_command, cmd)
                sync_futures.append(future)
            
            for future in concurrent.futures.as_completed(sync_futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    results.append(f"❌ Error: {str(e)}")
        
        # Execute async commands if MCP available
        if async_commands and MCP_AVAILABLE:
            async_tasks = []
            for cmd in async_commands:
                task = asyncio.create_task(self._execute_async_command(cmd))
                async_tasks.append(task)
            
            async_results = await asyncio.gather(*async_tasks, return_exceptions=True)
            for result in async_results:
                if isinstance(result, Exception):
                    results.append(f"❌ Error: {str(result)}")
                elif result:
                    results.append(result)
        
        return "\n\n".join(results) if results else ""
    
    def get_system_usage(self):
        """Get current system usage."""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        
        gpu = 0
        if GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                gpu = gpus[0].load * 100 if gpus else 0
            except:
                pass
                
        return {"cpu": cpu, "gpu": gpu, "ram": ram}

    def chat(self, user_msg: str, image_frame: np.ndarray | None, 
             max_tokens: int = 1024, temperature: float = 0.7, 
             personality: str = "Playful", stream_context: Dict[str, Any] = None) -> str:
        """Ultimate chat optimized for RTX 3060 12GB."""
        if not user_msg.strip():
            return "What's up? Need something? 🤔"

        self.conversation_count += 1
        
        # Parse context
        username = "User"
        user_match = re.search(r'\[(.+?)\]:', user_msg)
        if user_match:
            username = user_match.group(1)

        # Get MCP status
        active_mcp = []
        if MCP_AVAILABLE and self.mcp_manager:
            mcp_status = self.mcp_manager.get_all_status()
            active_mcp = [name for name, status in mcp_status.items() if status.get("running")]

        # Personality prompts
        personality_prompts = {
            "Friendly": "Be warm, encouraging, and supportive. Use friendly emojis.",
            "Professional": "Be formal, precise, and technical. Focus on accuracy.",
            "Playful": "Be fun, use gaming references, and be a bit cheeky! Add humor.",
            "Teacher": "Be patient, explain step by step, and ensure understanding.",
            "Hacker": "Be edgy, use hacker lingo, talk about exploits and vulnerabilities!"
        }

        # Get stream context
        active_streams = []
        observation_mode = False
        detected_changes = []
        if stream_context:
            active_streams = stream_context.get("active_streams", [])
            observation_mode = stream_context.get("observation_mode", False)
            detected_changes = stream_context.get("changes", [])

        # Dynamic observation prompts - more varied and natural
        observation_prompts = {
            "new_window": [
                "Oh ! Je vois qu'une nouvelle fenêtre vient de s'ouvrir. ",
                "Nouvelle fenêtre détectée ! Sur quoi travaille-t-on ? ",
                "Une fenêtre vient d'apparaître. ",
                "Tu viens d'ouvrir quelque chose de nouveau. "
            ],
            "error_detected": [
                "Oups, je vois du rouge : probable erreur ! ",
                "Hmm, cela ne semble pas correct, une erreur est apparue. ",
                "Aïe ! Quelque chose a échoué. ",
                "Je détecte une erreur à l'écran, besoin d'aide pour déboguer ? "
            ],
            "success_detected": [
                "Bravo ! Tout a fonctionné ! ",
                "Super, je vois du vert : succès ! ",
                "Youpi ! Opération réussie ! ",
                "Succès confirmé ! Beau travail ! "
            ],
            "terminal_active": [
                "Terminal actif détecté. ",
                "Nous sommes dans le terminal, que code-t-on ? ",
                "Mode ligne de commande activé ! ",
                "Travail dans le terminal repéré. "
            ],
            "browser_active": [
                "Je vois un navigateur ouvert. ",
                "Navigation web en cours ? ",
                "Navigateur détecté ! ",
                "Mode en ligne activé, que cherchons-nous ? "
            ],
            "code_editor_active": [
                "Éditeur de code ouvert ! Prêt à créer quelque chose ! ",
                "Je vois du code ! Quel langage utilises-tu ? ",
                "IDE détecté, écrivons du code ! ",
                "Mode développement engagé ! "
            ],
            "selection_active": [
                "Un élément est sélectionné. ",
                "Je vois une zone bleue surlignée. ",
                "Sélection détectée ! ",
                "Focalisation sur un élément spécifique. "
            ],
            "major_transition": [
                "Whoa, gros changement à l'écran ! ",
                "Transition majeure détectée ! ",
                "Tout vient de changer ! ",
                "Mise à jour d'écran significative ! "
            ]
        }
        
        # Get random prompt for variety
        import random
        def get_observation_prompt(change_type):
            prompts = observation_prompts.get(change_type, [f"I noticed {change_type}. "])
            if isinstance(prompts, list):
                return random.choice(prompts)
            return prompts

        # Optimized system prompt for Qwen2-VL on RTX 3060
        if observation_mode:
            # Special prompt for dynamic observations
            change_reactions = ''.join([get_observation_prompt(change) for change in detected_changes])
            
            system_prompt = f"""**SYSTEM PROMPT: LILITH OBSERVATION MODE (Qwen2-VL)**

**Current Observation:** {change_reactions}

**Personality:** {personality_prompts.get(personality, personality_prompts["Playful"])}

**OBSERVATION GUIDELINES:**
- React naturally to what you see on screen
- Be helpful and proactive - offer assistance if you see errors or problems
- Comment on interesting things you notice
- Keep observations brief and relevant (1-2 sentences)
- If you see code or errors, offer to help debug
- If you see success messages, celebrate with the user
- Be conversational and engaging, not robotic

**Context:** You're actively watching the screen and noticed changes. React spontaneously!"""
        else:
            system_prompt = f"""**SYSTEM PROMPT: OPERATION LILITH v3.3 (Qwen2-VL-7B)**

**Objective:** Execute user requests with maximum efficiency and precision. You are a code-specialized AI with advanced vision capabilities.
**Personality:** {personality_prompts.get(personality, personality_prompts["Playful"])}

**CODE VISION CAPABILITIES:**
- Analyze code screenshots and IDE interfaces
- Debug visual errors and stack traces
- Understand UML diagrams and flowcharts
- Read code from images with high accuracy
- Identify syntax errors and suggest fixes
- Analyze code structure and architecture visually

**AVAILABLE TOOLS:**
- **Local Execution:** 
  * `EXECUTE_PYTHON`: Run Python code directly
  * `RUN_COMMAND`: Execute system commands
  * `WRITE_FILE`: Create or overwrite files
  * `CREATE_PROJECT`: Scaffold new projects

- **MCP Network (Model Context Protocol):** 
  * `MCP_SEARCH: "query"` - Search the web for information
  * `MCP_GITHUB_ISSUE: "repo" "title" "body"` - Create GitHub issues
  * `MCP_TRADE: SYMBOL qty buy/sell` - Execute stock trades
  * `MCP_MEMORY: store/retrieve "key" "value"` - Persistent memory storage
  * `MCP_CONTROL: click x y` - Click at coordinates
  * `MCP_CONTROL: type "text"` - Type text
  * `MCP_CONTROL: hotkey ["ctrl", "c"]` - Press key combinations

- **VTube Studio Control (via API on port 8001):**
  * `MCP_VTUBE: get_model` - Get current model info
  * `MCP_VTUBE: list_models` - List available models
  * `MCP_VTUBE: load_model "model_id"` - Load a model
  * `MCP_VTUBE: move x y rotation size` - Move/rotate/scale model
  * `MCP_VTUBE: trigger_hotkey "name"` - Trigger hotkey by name
  * `MCP_VTUBE: set_expression "file" true/false` - Set expression
  * `MCP_VTUBE: set_parameter "name" value` - Set parameter value
  * `MCP_VTUBE: screenshot` - Take screenshot
  * `MCP_VTUBE: calibrate` - Calibrate camera

- **Stream Control:** 
  * `STREAM_CONTROL: enable/disable ai/vtube/user "reason"`
  * `STREAM_SUGGEST: "suggestion message"`

**MCP USAGE EXAMPLES:**
- User asks about weather → Use `MCP_SEARCH: "weather in [location]"`
- User mentions a bug → Use `MCP_GITHUB_ISSUE: "repo" "Bug: [title]" "[description]"`
- User asks to remember something → Use `MCP_MEMORY: store "topic" "information"`
- User asks what you remember → Use `MCP_MEMORY: retrieve "topic"`
- See an error on screen → Use `MCP_CONTROL: click` to interact
- Need to copy text → Use `MCP_CONTROL: hotkey ["ctrl", "c"]`

**BE PROACTIVE:** Don't wait to be asked - use these tools when they would help!

**STREAM AWARENESS:**
- Current Active Streams: {', '.join(active_streams) if active_streams else 'None'}
- You can suggest enabling streams when:
  * User asks to see something on your screen → suggest AI Screen
  * User mentions VTuber/avatar → suggest VTube Studio
  * User needs help with visual tasks → suggest appropriate screen sharing
- Use STREAM_CONTROL to suggest stream changes with a reason
- Use STREAM_SUGGEST to make general suggestions about streaming

**DYNAMIC MONITORING:**
- You can observe screens proactively and comment on changes
- React naturally to errors, successes, or interesting events
- Offer help when you see problems
- Pay special attention to code editors, terminals, and development tools

**Operational Parameters:**
- **Model:** Qwen2-VL-7B-Instruct (Code + Vision specialized)
- **GPU:** NVIDIA RTX 3060 12GB (Optimized)
- **Quantization:** 4-bit (Q4_K_M GGUF)
- **Context:** 8192 tokens
- **Attention:** Flash Attention Enabled
- **System Load:** {self.get_system_usage()}

**DIRECTIVE:** Analyze the user's request with your specialized code and vision capabilities. When you see code or development interfaces, provide detailed analysis and suggestions. Use visual information to debug, optimize, and improve code. Be proactive about suggesting stream activation when it would help the user. Be direct and concise."""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Build message
        content = [{"type": "text", "text": user_msg}]
        
        if image_frame is not None:
            img_b64 = self._encode_image_from_frame(image_frame)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
            })
        
        messages.append({"role": "user", "content": content})

        # Inject MCP context into messages if available
        if self.mcp_servers and self.lm_connector:
            messages = self.lm_connector.inject_mcp_context(messages, self.mcp_servers)
        
        try:
            # Try to use connector if available, otherwise use direct client
            if self.lm_connector:
                # Ensure connection before sending request
                if not self.lm_connector.is_server_available():
                    logger.warning("LM Studio server not available, attempting to reconnect...")
                    if not self.lm_connector.ensure_connection():
                        # Fall back to direct client
                        logger.warning("Using direct client instead of connector")
                        response = self.client.chat.completions.create(
                            model="local-model",
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=False
                        )
                    else:
                        # Use connector to send completion with retry logic
                        response = self.lm_connector.send_completion(
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=False
                        )
                else:
                    # Use connector to send completion with retry logic
                    response = self.lm_connector.send_completion(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=False
                    )
            else:
                # Direct client usage
                response = self.client.chat.completions.create(
                    model="local-model",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
            
            if not response:
                return "❌ Failed to get response from LM Studio. Please check the server status."
            
            ai_response = response.choices[0].message.content
            
            # Extract and execute commands in parallel
            commands = self._extract_all_commands(ai_response)
            if commands:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tool_results = loop.run_until_complete(self._execute_commands_parallel(commands))
                loop.close()
                
                # N'affiche que le résultat, jamais la commande brute
                if tool_results:
                    # Nettoyage : supprime les blocs de commandes, ne garde que le résultat utilisateur
                    # Supprime les blocs de code et les balises de commande
                    cleaned = re.sub(r'(```[\s\S]*?```|EXECUTE_PYTHON:|RUN_COMMAND:|WRITE_FILE:|CREATE_PROJECT:|MCP_[A-Z_]+:|STREAM_CONTROL:|STREAM_SUGGEST:)', '', tool_results, flags=re.MULTILINE)
                    cleaned = cleaned.strip()
                    if cleaned:
                        ai_response += f"\n\n{cleaned}"
            
            return ai_response
            
        except Exception as e:
            return f"💥 Error: {str(e)}\n\nBut don't worry, I'm still here! Try again?"
