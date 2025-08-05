"""MCP Remote Control Server for mouse, keyboard, and screen operations."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from typing import Dict, Any, List, Optional, Tuple
import base64
import time
import io

# Try to import required libraries
try:
    import pyautogui
    import keyboard
    import mouse
    import mss
    from PIL import Image
    import numpy as np
    CONTROL_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some remote control features unavailable: {e}")
    CONTROL_AVAILABLE = False


class RemoteControlServer(BaseMCPServer):
    """Remote control server for mouse, keyboard, and screen operations."""
    
    def __init__(self, port: int = 3011):
        super().__init__("remote_control", port)
        
        # Configure pyautogui safety features
        if CONTROL_AVAILABLE:
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            pyautogui.PAUSE = 0.1  # Pause between actions
        
        # Register methods
        self.register_method("mouse_move", self.mouse_move)
        self.register_method("mouse_click", self.mouse_click)
        self.register_method("mouse_drag", self.mouse_drag)
        self.register_method("mouse_scroll", self.mouse_scroll)
        self.register_method("mouse_position", self.mouse_position)
        
        self.register_method("keyboard_type", self.keyboard_type)
        self.register_method("keyboard_hotkey", self.keyboard_hotkey)
        self.register_method("keyboard_press", self.keyboard_press)
        self.register_method("keyboard_release", self.keyboard_release)
        
        self.register_method("screen_capture", self.screen_capture)
        self.register_method("screen_size", self.screen_size)
        self.register_method("find_on_screen", self.find_on_screen)
        self.register_method("wait_for_image", self.wait_for_image)
        self.register_method("pixel_color", self.pixel_color)
        
        self.register_method("get_window_list", self.get_window_list)
        self.register_method("activate_window", self.activate_window)
        
    async def mouse_move(self, x: int, y: int, duration: float = 0.5, relative: bool = False) -> Dict[str, Any]:
        """Move mouse to coordinates."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            if relative:
                pyautogui.moveRel(x, y, duration=duration)
            else:
                pyautogui.moveTo(x, y, duration=duration)
                
            new_x, new_y = pyautogui.position()
            return {"success": True, "position": {"x": new_x, "y": new_y}}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def mouse_click(self, x: int = None, y: int = None, button: str = "left", clicks: int = 1, interval: float = 0.0) -> Dict[str, Any]:
        """Click mouse at coordinates."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button, clicks=clicks, interval=interval)
            else:
                pyautogui.click(button=button, clicks=clicks, interval=interval)
                
            return {"success": True, "button": button, "clicks": clicks}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def mouse_drag(self, x: int, y: int, duration: float = 0.5, button: str = "left", relative: bool = False) -> Dict[str, Any]:
        """Drag mouse to coordinates."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            if relative:
                pyautogui.dragRel(x, y, duration=duration, button=button)
            else:
                pyautogui.dragTo(x, y, duration=duration, button=button)
                
            return {"success": True}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def mouse_scroll(self, clicks: int, x: int = None, y: int = None) -> Dict[str, Any]:
        """Scroll mouse wheel."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
                
            pyautogui.scroll(clicks)
            return {"success": True, "scrolled": clicks}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def mouse_position(self) -> Dict[str, Any]:
        """Get current mouse position."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            x, y = pyautogui.position()
            return {"x": x, "y": y}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def keyboard_type(self, text: str, interval: float = 0.0) -> Dict[str, Any]:
        """Type text on keyboard."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            pyautogui.typewrite(text, interval=interval)
            return {"success": True, "typed": text}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def keyboard_hotkey(self, keys: List[str]) -> Dict[str, Any]:
        """Press keyboard shortcut."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            pyautogui.hotkey(*keys)
            return {"success": True, "keys": keys}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def keyboard_press(self, key: str) -> Dict[str, Any]:
        """Press and hold a key."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            pyautogui.keyDown(key)
            return {"success": True, "key": key}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def keyboard_release(self, key: str) -> Dict[str, Any]:
        """Release a held key."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            pyautogui.keyUp(key)
            return {"success": True, "key": key}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def screen_capture(self, region: List[int] = None, monitor: int = None) -> Dict[str, Any]:
        """Capture screen or region."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            with mss.mss() as sct:
                if monitor is not None:
                    if monitor >= len(sct.monitors):
                        return {"error": f"Monitor {monitor} not found"}
                    mon = sct.monitors[monitor]
                elif region:
                    if len(region) != 4:
                        return {"error": "Region must be [x, y, width, height]"}
                    mon = {"left": region[0], "top": region[1], 
                           "width": region[2], "height": region[3]}
                else:
                    mon = sct.monitors[0]  # All monitors
                    
                screenshot = sct.grab(mon)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                img_base64 = base64.b64encode(buffer.getvalue()).decode()
                
                return {
                    "success": True,
                    "image": img_base64,
                    "width": img.width,
                    "height": img.height,
                    "format": "base64_png"
                }
                
        except Exception as e:
            return {"error": str(e)}
            
    async def screen_size(self, monitor: int = None) -> Dict[str, Any]:
        """Get screen size."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            if monitor is None:
                width, height = pyautogui.size()
                return {"width": width, "height": height}
            else:
                with mss.mss() as sct:
                    if monitor >= len(sct.monitors):
                        return {"error": f"Monitor {monitor} not found"}
                    mon = sct.monitors[monitor]
                    return {
                        "width": mon["width"],
                        "height": mon["height"],
                        "left": mon["left"],
                        "top": mon["top"]
                    }
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def find_on_screen(self, image_path: str = None, image_base64: str = None, 
                           confidence: float = 0.8, region: List[int] = None) -> Dict[str, Any]:
        """Find image on screen."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            # Load image
            if image_base64:
                img_data = base64.b64decode(image_base64)
                img = Image.open(io.BytesIO(img_data))
            elif image_path:
                img = Image.open(image_path)
            else:
                return {"error": "Either image_path or image_base64 must be provided"}
                
            # Search for image
            location = pyautogui.locateOnScreen(img, confidence=confidence, region=region)
            
            if location:
                center = pyautogui.center(location)
                return {
                    "found": True,
                    "x": center.x,
                    "y": center.y,
                    "left": location.left,
                    "top": location.top,
                    "width": location.width,
                    "height": location.height
                }
            else:
                return {"found": False}
                
        except Exception as e:
            return {"error": str(e)}
            
    async def wait_for_image(self, image_path: str = None, image_base64: str = None,
                           timeout: float = 10.0, confidence: float = 0.8,
                           region: List[int] = None) -> Dict[str, Any]:
        """Wait for image to appear on screen."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                result = await self.find_on_screen(image_path, image_base64, confidence, region)
                if result.get("found"):
                    result["wait_time"] = time.time() - start_time
                    return result
                    
                await asyncio.sleep(0.5)
                
            return {"found": False, "timeout": True}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def pixel_color(self, x: int, y: int) -> Dict[str, Any]:
        """Get color of pixel at coordinates."""
        if not CONTROL_AVAILABLE:
            return {"error": "Remote control not available"}
            
        try:
            # Use mss for pixel color
            with mss.mss() as sct:
                # Capture 1x1 pixel
                mon = {"left": x, "top": y, "width": 1, "height": 1}
                screenshot = sct.grab(mon)
                
                # Get pixel color
                pixel = screenshot.pixel(0, 0)  # BGRA format
                
                return {
                    "r": pixel[2],
                    "g": pixel[1],
                    "b": pixel[0],
                    "hex": f"#{pixel[2]:02x}{pixel[1]:02x}{pixel[0]:02x}"
                }
                
        except Exception as e:
            return {"error": str(e)}
            
    async def get_window_list(self) -> Dict[str, Any]:
        """Get list of open windows."""
        try:
            # This is Windows-specific, would need different implementation for other OS
            import win32gui
            
            windows = []
            
            def enum_handler(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    window_text = win32gui.GetWindowText(hwnd)
                    if window_text:
                        windows.append({
                            "title": window_text,
                            "handle": hwnd
                        })
                        
            win32gui.EnumWindows(enum_handler, None)
            
            return {"windows": windows, "count": len(windows)}
            
        except ImportError:
            return {"error": "Window management not available on this platform"}
        except Exception as e:
            return {"error": str(e)}
            
    async def activate_window(self, title: str) -> Dict[str, Any]:
        """Activate a window by title."""
        try:
            # Try using pyautogui first
            windows = pyautogui.getWindowsWithTitle(title)
            if windows:
                windows[0].activate()
                return {"success": True, "window": title}
            else:
                return {"error": f"Window '{title}' not found"}
                
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = create_argument_parser("MCP Remote Control Server")
    args = parser.parse_args()
    
    server = RemoteControlServer(port=args.port)
    server.run()