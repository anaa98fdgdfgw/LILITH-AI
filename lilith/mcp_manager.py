"""MCP (Model Context Protocol) Manager for **LM Studio**.

This module provides a ready‑to‑use manager for running and orchestrating
multiple MCP servers – including the *AB498 Computer Control* server – so
LM Studio (or any other agent runtime) can interact with the local machine
(files, browser, memory, etc.) through simple JSON‑RPC calls.

Highlights
==========
* Automatic discovery of server scripts in the local *mcp_servers/* folder.
* Declarative configuration via an optional ``mcp_config.py`` (same API as
  Lilith) – but with sane defaults when absent.
* Built‑in helper coroutines (``mcp_filesystem_read``, ``mcp_keyboard_type``, …)
  exposing the most common actions to the LM.
* First‑class support for **AB498 Computer Control** (`ab498_control_server.py`).
  If the script is missing, the manager skips it gracefully and logs a warning.
* Portable: works on *Windows*, *macOS*, and *Linux* as long as ``python``
  and the 🐍 dependencies are installed.

Usage Example
-------------
```python
import asyncio
from lmstudio_mcp_manager import mcp_manager, mcp_keyboard_type

async def main():
    # Type “Hello world!” via AB498 control.
    await mcp_keyboard_type("Hello world!\n")

    # Query the status of every server.
    print(mcp_manager.get_all_status())

asyncio.run(main())
```
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import aiohttp
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s")


@dataclass
class MCPServer:
    """Represents an MCP server (script + runtime metadata)."""

    name: str
    command: List[str]
    args: List[str] | None = None
    env: Dict[str, str] | None = None
    description: str = ""
    enabled: bool = True
    process: Optional[subprocess.Popen] = None
    port: Optional[int] = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


class MCPManager:
    """Base class that discovers and controls MCP server subprocesses."""

    DEFAULT_PORTS: dict[str, int] = {
        "filesystem": 3001,
        "github": 3002,
        "memory": 3005,
        "search": 3006,
        "time": 3009,
        "fetch": 3010,
        "ab498_control": 3011,  # AB498 Computer Control JSON‑RPC
        "alpaca": 3012,
    }

    def __init__(self) -> None:
        self.servers: Dict[str, MCPServer] = {}
        self._configure_servers()

    # ---------------------------------------------------------------------
    # Configuration helpers
    # ---------------------------------------------------------------------
    def _configure_servers(self) -> None:
        """Populate ``self.servers`` either from ``mcp_config`` or defaults."""

        mcp_dir = Path(__file__).with_suffix("").parent / "mcp_servers"

        # Try to read optional project‑specific config
        try:
            import mcp_config  # type: ignore

            cfg = mcp_config.get_mcp_config()
            ports = cfg.get("ports", {})
            enabled_map = cfg.get("enabled", {})
            fs_allowed = cfg.get("filesystem", {}).get("allowed_dirs", [])
            memory_db = cfg.get("memory", {}).get("db_path", None)
        except Exception as e:  # pragma: no cover – config is optional
            logger.debug("No custom mcp_config.py found (%s). Using defaults.", e)
            ports = {}
            enabled_map = {}
            fs_allowed = [str(Path.home()), str(Path.cwd())]
            memory_db = str(Path.home() / ".lmstudio" / "memory.db")

        # Final port table with fallbacks
        port_table: dict[str, int] = {
            k: ports.get(k, v) for k, v in self.DEFAULT_PORTS.items()
        }

        for srv_name, port in port_table.items():
            if not enabled_map.get(srv_name, True):
                continue  # Server explicitly disabled

            script_path = mcp_dir / f"{srv_name}_server.py"

            cmd: list[str] = [sys.executable, str(script_path)]
            args: list[str] = []
            env: dict[str, str] | None = None

            # Per‑server customisation
            if srv_name == "filesystem":
                args = ["--allowed-directories", *fs_allowed]
            elif srv_name == "memory":
                if memory_db:
                    args = ["--db-path", memory_db]
            elif srv_name == "github":
                env = {"GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", "")}
            elif srv_name == "search":
                env = {
                    "BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", ""),
                    "SEARX_URL": os.environ.get("SEARX_URL", "https://searx.me"),
                }
            elif srv_name == "alpaca":
                env = {
                    "ALPACA_API_KEY": os.environ.get("ALPACA_API_KEY", ""),
                    "ALPACA_SECRET_KEY": os.environ.get("ALPACA_SECRET_KEY", ""),
                    "ALPACA_BASE_URL": os.environ.get(
                        "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
                    ),
                }

            self.servers[srv_name] = MCPServer(
                name=srv_name,
                command=cmd,
                args=args or None,
                env=env,
                port=port,
                description=script_path.name,
            )

    # ------------------------------------------------------------------
    # Lifecycle management (start/stop/restart)
    # ------------------------------------------------------------------
    async def start_server(self, name: str) -> bool:
        if name not in self.servers:
            logger.error("Unknown server: %s", name)
            return False

        srv = self.servers[name]
        if not srv.enabled:
            logger.info("Server %s is disabled", name)
            return False
        if srv.is_running():
            return True

        # Build env and command
        env = os.environ.copy()
        if srv.env:
            env.update(srv.env)
        cmd = [*srv.command, *(srv.args or []), "--port", str(srv.port)]

        # Spawn subprocess
        try:
            srv.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            logger.warning("Server script missing: %s", " " .join(cmd))
            return False
        except Exception as exc:
            logger.error("Failed to start %s: %s", name, exc)
            return False

        await asyncio.sleep(1.5)  # Give it a chance to bind the port
        if srv.is_running():
            logger.info("Started %s on port %s", name, srv.port)
            return True
        logger.error("%s exited immediately – check logs", name)
        return False

    async def stop_server(self, name: str) -> bool:
        srv = self.servers.get(name)
        if not srv or not srv.is_running():
            return False
        srv.process.terminate()
        try:
            await asyncio.get_running_loop().run_in_executor(None, srv.process.wait, 5)
        except subprocess.TimeoutExpired:
            srv.process.kill()
        logger.info("Stopped %s", name)
        return True

    async def restart_server(self, name: str) -> bool:
        await self.stop_server(name)
        await asyncio.sleep(0.5)
        return await self.start_server(name)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------
    def get_server_status(self, name: str) -> dict[str, Any]:
        srv = self.servers.get(name)
        if not srv:
            return {"error": "unknown server"}
        return {
            "name": srv.name,
            "running": srv.is_running(),
            "enabled": srv.enabled,
            "port": srv.port,
            "pid": srv.process.pid if srv.is_running() else None,
        }

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        return {n: self.get_server_status(n) for n in self.servers}

    # ------------------------------------------------------------------
    # JSON‑RPC proxy helper
    # ------------------------------------------------------------------
    async def call_server(self, name: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in self.servers:
            return {"error": "unknown server"}

        srv = self.servers[name]
        if not await self.start_server(name):
            return {"error": f"{name} not available"}

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }
        url = f"http://127.0.0.1:{srv.port}/rpc"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(url, json=payload, timeout=20) as resp:
                    data = await resp.json()
                    if "error" in data:
                        return {"error": data["error"]}
                    return data.get("result", {})
        except Exception as exc:
            return {"error": str(exc)}


# ----------------------------------------------------------------------
# Singleton instance
# ----------------------------------------------------------------------

mcp_manager = MCPManager()

# ----------------------------------------------------------------------
# Convenience helper coroutines – ordinary agent code can import these
# ----------------------------------------------------------------------

async def mcp_filesystem_read(path: str):
    return await mcp_manager.call_server("filesystem", "read_file", {"path": path})


async def mcp_filesystem_write(path: str, content: str):
    return await mcp_manager.call_server("filesystem", "write_file", {"path": path, "content": content})


async def mcp_keyboard_type(text: str, interval: float = 0.0):
    """Type text using **AB498 Computer Control** server."""
    return await mcp_manager.call_server("ab498_control", "keyboard_type", {"text": text, "interval": interval})


async def mcp_mouse_move(x: int, y: int, duration: float = 0.2):
    return await mcp_manager.call_server("ab498_control", "mouse_move", {"x": x, "y": y, "duration": duration})


async def mcp_mouse_click(x: int | None = None, y: int | None = None, button: str = "left"):
    params: dict[str, Any] = {"button": button}
    if x is not None:
        params["x"] = x
    if y is not None:
        params["y"] = y
    return await mcp_manager.call_server("ab498_control", "mouse_click", params)


async def mcp_search_web(query: str):
    return await mcp_manager.call_server("search", "search", {"query": query})


async def mcp_memory_store(key: str, value: Any):
    return await mcp_manager.call_server("memory", "store", {"key": key, "value": value})


async def mcp_memory_retrieve(key: str):
    return await mcp_manager.call_server("memory", "retrieve", {"key": key})


# Add any additional helpers for Alpaca, GitHub, etc. following the same pattern.

__all__ = [
    "mcp_manager",
    "mcp_filesystem_read",
    "mcp_filesystem_write",
    "mcp_keyboard_type",
    "mcp_mouse_move",
    "mcp_mouse_click",
    "mcp_search_web",
    "mcp_memory_store",
    "mcp_memory_retrieve",
]
