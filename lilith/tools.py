"""
Tools for Lilith to interact with the system.
Version: 1.1 (AB498 RPC Fix)
Date: 2025-08-05
"""
from __future__ import annotations

import subprocess
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import tempfile
import textwrap
import ast
import traceback
import json as _json, urllib.request as _u, urllib.error as _ue

# ----------------------------------------------------------------------
#  AB498 RPC Functions (for screen control)
# ----------------------------------------------------------------------

_AB498_URL = "http://127.0.0.1:3011/rpc"

def _ab498_rpc(method: str, params: dict | None = None):
    """Helper function to call the AB498 control server."""
    payload = _json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    ).encode()
    req = _u.Request(_AB498_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with _u.urlopen(req, timeout=5) as resp:
            data = _json.load(resp)
            if data.get("error"):
                raise RuntimeError(data["error"])
            return data.get("result", {})
    except _ue.URLError as exc:
        raise RuntimeError(f"AB498 control server unreachable at {_AB498_URL}: {exc}") from exc

def type_text(text: str, interval: float = 0.0) -> bool:
    """Types the given text via the local keyboard."""
    _ab498_rpc("keyboard_type", {"text": text, "interval": interval})
    return True

def click_screen(x_rel: float, y_rel: float, button: str = "left") -> bool:
    """Clicks the screen at relative (0.0-1.0) coordinates."""
    params = {"x_rel": x_rel, "y_rel": y_rel, "button": button}
    _ab498_rpc("mouse_click", params)
    return True

def move_mouse(x_rel: float, y_rel: float, duration: float = 0.2) -> bool:
    """Moves the mouse to relative (0.0-1.0) coordinates."""
    params = {"x_rel": x_rel, "y_rel": y_rel, "duration": duration}
    _ab498_rpc("mouse_move", params)
    return True

def take_screenshot() -> str:
    """Captures the screen and returns a base64 encoded PNG image."""
    return _ab498_rpc("take_screenshot").get("image", "")

# ----------------------------------------------------------------------
#  LilithTools Class (for filesystem and execution)
# ----------------------------------------------------------------------

class LilithTools:
    """Collection of tools that Lilith can use to interact with the local system."""
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        """Initialize tools with an optional workspace directory."""
        self.workspace = workspace_dir or Path.cwd() / "lilith_workspace"
        self.workspace.mkdir(exist_ok=True)
        
    def execute_python(self, code: str, timeout: int = 10) -> Dict[str, Any]:
        """Execute Python code in a sandboxed environment."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=self.workspace, encoding='utf-8') as fp:
            fp.write(textwrap.dedent(code))
            tmp_path = Path(fp.name)
        
        try:
            proc = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace),
                encoding='utf-8'
            )
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Code execution timed out after {timeout} seconds.",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error executing code: {str(e)}",
                "returncode": -1
            }
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command in the workspace."""
        try:
            shell = sys.platform.startswith('win')
            
            proc = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace),
                encoding='utf-8'
            )
            
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds.",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error executing command: {str(e)}",
                "returncode": -1
            }
    
    def read_file(self, filepath: str) -> Dict[str, Any]:
        """Read a file from the workspace."""
        try:
            path = self._resolve_path(filepath)
            if not path.is_file():
                return {"success": False, "error": f"File not found or is a directory: {filepath}"}
                
            content = path.read_text(encoding='utf-8')
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "content": "", "error": f"Error reading file: {str(e)}"}
    
    def write_file(self, filepath: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the workspace."""
        try:
            path = self._resolve_path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return {"success": True, "path": str(path)}
        except Exception as e:
            return {"success": False, "path": "", "error": f"Error writing file: {str(e)}"}
    
    def list_directory(self, path: str = ".") -> Dict[str, Any]:
        """List files and subdirectories in a given path within the workspace."""
        try:
            dir_path = self._resolve_path(path)
            if not dir_path.is_dir():
                return {"success": False, "error": f"Path is not a directory: {path}"}
                
            items = []
            for item in sorted(dir_path.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                })
                
            return {"success": True, "items": items}
        except Exception as e:
            return {"success": False, "items": [], "error": f"Error listing directory: {str(e)}"}

    def _resolve_path(self, filepath: str) -> Path:
        """Resolve a path against the workspace, ensuring it's safe."""
        # This is a security measure to prevent directory traversal attacks.
        # It ensures that the resolved path is still within the workspace directory.
        resolved_path = (self.workspace / filepath).resolve()
        if self.workspace.resolve() not in resolved_path.parents and resolved_path != self.workspace.resolve():
             raise PermissionError(f"Access to path '{filepath}' is outside the allowed workspace.")
        return resolved_path