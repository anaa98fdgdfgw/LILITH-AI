"""Tools for Lilith to interact with the system."""
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
import base64
import io

# Enhanced vision and control imports
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = False  # Disable failsafe for automation
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pynput
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    import cv2
    import numpy as np
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class LilithTools:
    """Collection of tools that Lilith can use to interact with the system."""
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        """Initialize tools with an optional workspace directory."""
        self.workspace = workspace_dir or Path.cwd() / "lilith_workspace"
        self.workspace.mkdir(exist_ok=True)
        
        # Initialize control interfaces
        if PYNPUT_AVAILABLE:
            self.mouse_controller = mouse.Controller()
            self.keyboard_controller = keyboard.Controller()
        else:
            self.mouse_controller = None
            self.keyboard_controller = None
    
    def get_vision_capabilities(self) -> Dict[str, Any]:
        """Get information about available vision capabilities."""
        capabilities = {
            "mss_available": MSS_AVAILABLE,
            "pyautogui_available": PYAUTOGUI_AVAILABLE,
            "cv2_available": CV2_AVAILABLE,
            "multi_monitor_support": False,
            "monitors": [],
            "recommended_method": None
        }
        
        if MSS_AVAILABLE:
            try:
                with mss.mss() as sct:
                    monitors = sct.monitors
                    capabilities["monitors"] = [
                        {
                            "index": i,
                            "left": mon["left"],
                            "top": mon["top"],
                            "width": mon["width"],
                            "height": mon["height"]
                        }
                        for i, mon in enumerate(monitors)
                    ]
                    capabilities["multi_monitor_support"] = len(monitors) > 2  # 0=all, 1=primary, 2+=multi
                    capabilities["recommended_method"] = "mss"
            except Exception:
                capabilities["mss_available"] = False
        
        if capabilities["recommended_method"] is None and PYAUTOGUI_AVAILABLE:
            capabilities["recommended_method"] = "pyautogui"
        
        return capabilities
    
    def enhanced_screenshot(self, monitor: int = 0, format: str = "base64") -> Dict[str, Any]:
        """
        Take enhanced screenshot with multi-monitor support.
        
        Args:
            monitor: Monitor index (0=all monitors, 1=primary, 2+=secondary)
            format: Return format ("base64", "numpy", "pil", "file")
        """
        try:
            image_data = None
            method_used = None
            
            # Try MSS first (best for multi-monitor)
            if MSS_AVAILABLE:
                try:
                    with mss.mss() as sct:
                        monitors = sct.monitors
                        if monitor < len(monitors):
                            target_monitor = monitors[monitor]
                            screenshot = sct.grab(target_monitor)
                            image_data = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                            method_used = "mss"
                        else:
                            return {
                                "success": False,
                                "error": f"Monitor {monitor} not found. Available: 0-{len(monitors)-1}",
                                "method": "mss"
                            }
                except Exception as e:
                    # Fall through to pyautogui
                    pass
            
            # Fallback to PyAutoGUI
            if image_data is None and PYAUTOGUI_AVAILABLE:
                try:
                    screenshot = pyautogui.screenshot()
                    image_data = screenshot
                    method_used = "pyautogui"
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Screenshot failed: {str(e)}",
                        "method": "pyautogui"
                    }
            
            if image_data is None:
                return {
                    "success": False,
                    "error": "No screenshot method available",
                    "method": "none"
                }
            
            # Convert to requested format
            result = {
                "success": True,
                "method": method_used,
                "width": image_data.width,
                "height": image_data.height,
                "monitor": monitor
            }
            
            if format == "base64":
                buffer = io.BytesIO()
                image_data.save(buffer, format="PNG")
                result["image"] = base64.b64encode(buffer.getvalue()).decode()
                result["format"] = "data:image/png;base64"
                
            elif format == "numpy" and CV2_AVAILABLE:
                result["image"] = cv2.cvtColor(np.array(image_data), cv2.COLOR_RGB2BGR)
                result["format"] = "numpy_array"
                
            elif format == "pil":
                result["image"] = image_data
                result["format"] = "pil_image"
                
            elif format == "file":
                filename = f"screenshot_{monitor}_{hash(str(image_data.tobytes())[:100])}.png"
                filepath = self.workspace / filename
                image_data.save(filepath)
                result["image"] = str(filepath)
                result["format"] = "file_path"
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Enhanced screenshot failed: {str(e)}",
                "method": "error"
            }
    
    def enhanced_mouse_control(self, action: str, x: Optional[float] = None, y: Optional[float] = None, 
                              x_rel: Optional[float] = None, y_rel: Optional[float] = None,
                              button: str = "left", duration: float = 0.2) -> Dict[str, Any]:
        """
        Enhanced mouse control with multiple backend support.
        
        Args:
            action: "move", "click", "drag", "scroll", "position"
            x, y: Absolute coordinates
            x_rel, y_rel: Relative coordinates (0-1)
            button: "left", "right", "middle"
            duration: Duration for movements
        """
        try:
            # Convert relative to absolute coordinates if needed
            if x_rel is not None and y_rel is not None:
                if PYAUTOGUI_AVAILABLE:
                    screen_w, screen_h = pyautogui.size()
                    x = int(x_rel * screen_w)
                    y = int(y_rel * screen_h)
                elif MSS_AVAILABLE:
                    with mss.mss() as sct:
                        monitor = sct.monitors[1]  # Primary monitor
                        x = int(x_rel * monitor["width"]) + monitor["left"]
                        y = int(y_rel * monitor["height"]) + monitor["top"]
                else:
                    return {"success": False, "error": "No coordinate system available"}
            
            result = {"success": False, "method": None, "action": action}
            
            # Try pynput first (more reliable)
            if PYNPUT_AVAILABLE and self.mouse_controller:
                try:
                    if action == "move":
                        self.mouse_controller.position = (x, y)
                        result = {"success": True, "method": "pynput", "action": "move", "x": x, "y": y}
                        
                    elif action == "click":
                        if x is not None and y is not None:
                            self.mouse_controller.position = (x, y)
                        
                        button_map = {
                            "left": mouse.Button.left,
                            "right": mouse.Button.right,
                            "middle": mouse.Button.middle
                        }
                        self.mouse_controller.click(button_map.get(button, mouse.Button.left))
                        result = {"success": True, "method": "pynput", "action": "click", "button": button}
                        
                    elif action == "position":
                        pos = self.mouse_controller.position
                        result = {"success": True, "method": "pynput", "action": "position", "x": pos[0], "y": pos[1]}
                        
                    elif action == "scroll":
                        scroll_y = y if y is not None else 0
                        self.mouse_controller.scroll(0, scroll_y)
                        result = {"success": True, "method": "pynput", "action": "scroll", "scroll_y": scroll_y}
                        
                except Exception as e:
                    # Fall through to pyautogui
                    pass
            
            # Fallback to PyAutoGUI
            if not result["success"] and PYAUTOGUI_AVAILABLE:
                try:
                    if action == "move":
                        pyautogui.moveTo(x, y, duration=duration)
                        result = {"success": True, "method": "pyautogui", "action": "move", "x": x, "y": y}
                        
                    elif action == "click":
                        pyautogui.click(x=x, y=y, button=button)
                        result = {"success": True, "method": "pyautogui", "action": "click", "button": button}
                        
                    elif action == "position":
                        pos = pyautogui.position()
                        result = {"success": True, "method": "pyautogui", "action": "position", "x": pos[0], "y": pos[1]}
                        
                    elif action == "scroll":
                        scroll_amount = int(y) if y is not None else 1
                        pyautogui.scroll(scroll_amount, x=x, y=y)
                        result = {"success": True, "method": "pyautogui", "action": "scroll", "scroll": scroll_amount}
                        
                except Exception as e:
                    result = {"success": False, "error": f"PyAutoGUI error: {str(e)}", "method": "pyautogui"}
            
            if not result["success"] and "error" not in result:
                result["error"] = "No working mouse control method available"
                
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Enhanced mouse control failed: {str(e)}",
                "method": "error"
            }
    
    def enhanced_keyboard_control(self, action: str, text: Optional[str] = None, 
                                 key: Optional[str] = None, interval: float = 0.0) -> Dict[str, Any]:
        """
        Enhanced keyboard control with multiple backend support.
        
        Args:
            action: "type", "press", "hold", "release"
            text: Text to type
            key: Key to press (e.g., "enter", "ctrl+c")
            interval: Interval between characters when typing
        """
        try:
            result = {"success": False, "method": None, "action": action}
            
            # Try pynput first
            if PYNPUT_AVAILABLE and self.keyboard_controller:
                try:
                    if action == "type" and text:
                        if interval > 0:
                            for char in text:
                                self.keyboard_controller.type(char)
                                if interval > 0:
                                    import time
                                    time.sleep(interval)
                        else:
                            self.keyboard_controller.type(text)
                        result = {"success": True, "method": "pynput", "action": "type", "text": text}
                        
                    elif action == "press" and key:
                        # Handle key combinations
                        if "+" in key:
                            keys = key.split("+")
                            modifiers = []
                            final_key = keys[-1]
                            
                            # Map modifier keys
                            key_map = {
                                "ctrl": keyboard.Key.ctrl,
                                "alt": keyboard.Key.alt,
                                "shift": keyboard.Key.shift,
                                "cmd": keyboard.Key.cmd,
                                "enter": keyboard.Key.enter,
                                "space": keyboard.Key.space,
                                "tab": keyboard.Key.tab,
                                "esc": keyboard.Key.esc,
                                "escape": keyboard.Key.esc
                            }
                            
                            for modifier in keys[:-1]:
                                if modifier.lower() in key_map:
                                    modifiers.append(key_map[modifier.lower()])
                            
                            # Press combination
                            with self.keyboard_controller.pressed(*modifiers):
                                if final_key.lower() in key_map:
                                    self.keyboard_controller.press(key_map[final_key.lower()])
                                    self.keyboard_controller.release(key_map[final_key.lower()])
                                else:
                                    self.keyboard_controller.type(final_key)
                        else:
                            # Single key
                            key_map = {
                                "enter": keyboard.Key.enter,
                                "space": keyboard.Key.space,
                                "tab": keyboard.Key.tab,
                                "esc": keyboard.Key.esc,
                                "escape": keyboard.Key.esc
                            }
                            
                            if key.lower() in key_map:
                                self.keyboard_controller.press(key_map[key.lower()])
                                self.keyboard_controller.release(key_map[key.lower()])
                            else:
                                self.keyboard_controller.type(key)
                                
                        result = {"success": True, "method": "pynput", "action": "press", "key": key}
                        
                except Exception as e:
                    # Fall through to pyautogui
                    pass
            
            # Fallback to PyAutoGUI
            if not result["success"] and PYAUTOGUI_AVAILABLE:
                try:
                    if action == "type" and text:
                        pyautogui.write(text, interval=interval)
                        result = {"success": True, "method": "pyautogui", "action": "type", "text": text}
                        
                    elif action == "press" and key:
                        if "+" in key:
                            # Handle key combinations
                            keys = key.split("+")
                            pyautogui.hotkey(*keys)
                        else:
                            pyautogui.press(key)
                        result = {"success": True, "method": "pyautogui", "action": "press", "key": key}
                        
                except Exception as e:
                    result = {"success": False, "error": f"PyAutoGUI error: {str(e)}", "method": "pyautogui"}
            
            if not result["success"] and "error" not in result:
                result["error"] = "No working keyboard control method available"
                
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Enhanced keyboard control failed: {str(e)}",
                "method": "error"
            }
        
    def execute_python(self, code: str, timeout: int = 10) -> Dict[str, str]:
        """Execute Python code in a sandboxed environment."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(textwrap.dedent(code))
            tmp_path = Path(fp.name)
        
        try:
            proc = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)
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
                "stderr": f"Code execution timed out after {timeout} seconds",
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
        """Execute a shell command."""
        try:
            # Use shell=True on Windows, shell=False on Unix
            shell = sys.platform.startswith('win')
            
            proc = subprocess.run(
                command if not shell else command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)
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
                "stderr": f"Command timed out after {timeout} seconds",
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
        """Read a file from the workspace or absolute path."""
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = self.workspace / path
                
            if not path.exists():
                return {
                    "success": False,
                    "content": "",
                    "error": f"File not found: {filepath}"
                }
                
            content = path.read_text(encoding='utf-8')
            return {
                "success": True,
                "content": content,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": "",
                "error": f"Error reading file: {str(e)}"
            }
    
    def write_file(self, filepath: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the workspace."""
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = self.workspace / path
                
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            path.write_text(content, encoding='utf-8')
            return {
                "success": True,
                "path": str(path),
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "path": "",
                "error": f"Error writing file: {str(e)}"
            }
    
    def list_files(self, directory: str = ".") -> Dict[str, Any]:
        """List files in a directory."""
        try:
            path = Path(directory)
            if not path.is_absolute():
                path = self.workspace / path
                
            if not path.exists():
                return {
                    "success": False,
                    "files": [],
                    "error": f"Directory not found: {directory}"
                }
                
            files = []
            for item in path.iterdir():
                files.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
                
            return {
                "success": True,
                "files": files,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "files": [],
                "error": f"Error listing files: {str(e)}"
            }
    
    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Analyze code structure and provide insights."""
        if language.lower() != "python":
            return {
                "success": False,
                "analysis": {},
                "error": "Currently only Python analysis is supported"
            }
            
        try:
            tree = ast.parse(code)
            
            analysis = {
                "functions": [],
                "classes": [],
                "imports": [],
                "variables": [],
                "line_count": len(code.splitlines()),
                "has_main": False
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis["functions"].append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "lineno": node.lineno
                    })
                    if node.name == "main":
                        analysis["has_main"] = True
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    analysis["imports"].append(f"{node.module}.{node.names[0].name}")
                elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                    analysis["variables"].append(node.targets[0].id)
                    
            return {
                "success": True,
                "analysis": analysis,
                "error": None
            }
        except SyntaxError as e:
            return {
                "success": False,
                "analysis": {},
                "error": f"Syntax error in code: {e.msg} at line {e.lineno}"
            }
        except Exception as e:
            return {
                "success": False,
                "analysis": {},
                "error": f"Error analyzing code: {str(e)}"
            }
    
    def create_project(self, name: str, project_type: str = "python") -> Dict[str, Any]:
        """Create a new project structure."""
        try:
            project_path = self.workspace / name
            if project_path.exists():
                return {
                    "success": False,
                    "path": "",
                    "error": f"Project '{name}' already exists"
                }
                
            project_path.mkdir(parents=True)
            
            if project_type == "python":
                # Create Python project structure
                (project_path / "src").mkdir()
                (project_path / "tests").mkdir()
                (project_path / "docs").mkdir()
                
                # Create initial files
                (project_path / "README.md").write_text(f"# {name}\n\nA Python project created by Lilith.")
                (project_path / "requirements.txt").write_text("")
                (project_path / ".gitignore").write_text("__pycache__/\n*.pyc\n.env\nvenv/\n")
                (project_path / "src" / "__init__.py").write_text("")
                (project_path / "src" / "main.py").write_text(
                    'def main():\n    print("Hello from Lilith!")\n\nif __name__ == "__main__":\n    main()\n'
                )
                
            elif project_type == "web":
                # Create web project structure
                (project_path / "css").mkdir()
                (project_path / "js").mkdir()
                (project_path / "images").mkdir()
                
                # Create initial files
                (project_path / "index.html").write_text(
                    '<!DOCTYPE html>\n<html>\n<head>\n    <title>' + name + 
                    '</title>\n    <link rel="stylesheet" href="css/style.css">\n</head>\n<body>\n    ' +
                    '<h1>Welcome to ' + name + '</h1>\n    <p>Created by Lilith</p>\n    ' +
                    '<script src="js/script.js"></script>\n</body>\n</html>'
                )
                (project_path / "css" / "style.css").write_text(
                    'body {\n    font-family: Arial, sans-serif;\n    margin: 0;\n    padding: 20px;\n}'
                )
                (project_path / "js" / "script.js").write_text(
                    'console.log("Hello from Lilith!");'
                )
                
            return {
                "success": True,
                "path": str(project_path),
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "path": "",
                "error": f"Error creating project: {str(e)}"
            }
    
    def get_workspace_info(self) -> Dict[str, Any]:
        """Get information about the current workspace."""
        try:
            projects = []
            total_size = 0
            
            for item in self.workspace.iterdir():
                if item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    projects.append({
                        "name": item.name,
                        "size": size,
                        "files": len(list(item.rglob('*')))
                    })
                    total_size += size
                    
            return {
                "workspace_path": str(self.workspace),
                "projects": projects,
                "total_size": total_size,
                "project_count": len(projects)
            }
        except Exception as e:
            return {
                "workspace_path": str(self.workspace),
                "projects": [],
                "total_size": 0,
                "project_count": 0,
                "error": str(e)
            }
import json as _json, urllib.request as _u, urllib.error as _ue

_AB498_URL = "http://127.0.0.1:3011/rpc"

def _ab498_rpc(method: str, params: dict | None = None):
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
        raise RuntimeError(f"AB498 control server unreachable: {exc}") from exc

def type_text(text: str, interval: float = 0.0) -> bool:
    """Enhanced type_text function with fallback support."""
    try:
        # Try enhanced keyboard control first
        tools = LilithTools()
        result = tools.enhanced_keyboard_control("type", text=text, interval=interval)
        if result["success"]:
            return True
    except Exception:
        pass
    
    # Fallback to AB498 RPC
    try:
        _ab498_rpc("type_text", {"text": text, "interval": interval})
        return True
    except Exception:
        pass
    
    # Final fallback to direct pyautogui
    try:
        import pyautogui
        pyautogui.write(text, interval=interval)
        return True
    except Exception:
        return False

def click_screen(*, x: int | None = None, y: int | None = None,
                 x_rel: float | None = None, y_rel: float | None = None,
                 button: str = "left") -> bool:
    """Enhanced click_screen function with fallback support."""
    try:
        # Try enhanced mouse control first
        tools = LilithTools()
        result = tools.enhanced_mouse_control("click", x=x, y=y, x_rel=x_rel, y_rel=y_rel, button=button)
        if result["success"]:
            return True
    except Exception:
        pass
    
    # Fallback to AB498 RPC
    try:
        _ab498_rpc("click_screen", {"x": x, "y": y, "x_rel": x_rel, "y_rel": y_rel, "button": button})
        return True
    except Exception:
        pass
    
    # Final fallback to direct pyautogui
    try:
        import pyautogui
        if x_rel is not None and y_rel is not None:
            screen_w, screen_h = pyautogui.size()
            x = int(x_rel * screen_w)
            y = int(y_rel * screen_h)
        pyautogui.click(x=x, y=y, button=button)
        return True
    except Exception:
        return False

def move_mouse(*, x: int | None = None, y: int | None = None,
               x_rel: float | None = None, y_rel: float | None = None,
               duration: float = 0.2) -> bool:
    """Enhanced move_mouse function with fallback support."""
    try:
        # Try enhanced mouse control first
        tools = LilithTools()
        result = tools.enhanced_mouse_control("move", x=x, y=y, x_rel=x_rel, y_rel=y_rel, duration=duration)
        if result["success"]:
            return True
    except Exception:
        pass
    
    # Fallback to AB498 RPC
    try:
        _ab498_rpc("move_mouse", {"x": x, "y": y, "x_rel": x_rel, "y_rel": y_rel, "duration": duration})
        return True
    except Exception:
        pass
    
    # Final fallback to direct pyautogui
    try:
        import pyautogui
        if x_rel is not None and y_rel is not None:
            screen_w, screen_h = pyautogui.size()
            x = int(x_rel * screen_w)
            y = int(y_rel * screen_h)
        pyautogui.moveTo(x, y, duration=duration)
        return True
    except Exception:
        return False

def take_screenshot() -> str:
    """Enhanced take_screenshot function with multi-monitor support."""
    try:
        # Try enhanced screenshot first
        tools = LilithTools()
        result = tools.enhanced_screenshot(monitor=0, format="base64")
        if result["success"]:
            return result["image"]
    except Exception:
        pass
    
    # Fallback to AB498 RPC
    try:
        result = _ab498_rpc("take_screenshot")
        if "image" in result:
            return result["image"]
    except Exception:
        pass
    
    # Final fallback to direct pyautogui
    try:
        import pyautogui
        import base64
        import io
        screenshot = pyautogui.screenshot()
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        return ""