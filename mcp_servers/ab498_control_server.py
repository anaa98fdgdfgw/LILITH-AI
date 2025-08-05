#!/usr/bin/env python
"""AB498 control server – Enhanced with full computer-control-mcp capabilities."""
from __future__ import annotations
import argparse, io, base64, logging, json
from typing import Any, Dict

import pyautogui
from PIL import Image
from aiohttp import web
import asyncio

# Import our enhanced computer control
try:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from lilith.computer_control import get_computer_controller
    ENHANCED_CONTROL_AVAILABLE = True
except ImportError:
    ENHANCED_CONTROL_AVAILABLE = False

pyautogui.FAILSAFE = False
log = logging.getLogger("ab498")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global computer controller
computer_controller = None

def init_computer_controller():
    """Initialize the enhanced computer controller."""
    global computer_controller
    if ENHANCED_CONTROL_AVAILABLE and computer_controller is None:
        try:
            computer_controller = get_computer_controller()
            log.info("✅ Enhanced computer controller initialized")
        except Exception as e:
            log.warning(f"⚠️ Enhanced computer controller failed: {e}")

# Initialize on startup
init_computer_controller()

AI_CROP = {"x0": 0, "y0": 0, "w": None, "h": None}  # None = plein écran

def _rel2abs(x: float | int | None, y: float | int | None) -> tuple[int | None, int | None]:
    """Convertit (x_rel/y_rel) ∈ 0-1 en pixels écran ; sinon retourne les pixels."""
    if x is None or y is None:
        return x, y
    w, h = pyautogui.size()
    xf, yf = float(x), float(y)
    if 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:
        xf *= w
        yf *= h
    return int(round(xf)), int(round(yf))

def _png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

async def rpc(req: web.Request):
    """Enhanced RPC handler with computer-control-mcp capabilities."""
    try:
        data: Dict[str, Any] = await req.json()
    except Exception as e:
        return web.json_response({
            "jsonrpc": "2.0", 
            "error": {"code": -32700, "message": f"Parse error: {e}"}, 
            "id": None
        })
    
    method = data.get("method")
    params = data.get("params", {}) or {}
    request_id = data.get("id")
    
    response: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    
    try:
        # Enhanced computer control methods
        if method == "analyze_screen":
            if computer_controller:
                monitor = params.get("monitor", 0)
                include_ocr = params.get("include_ocr", True)
                include_ui = params.get("include_ui_elements", True)
                result = computer_controller.analyze_screen(monitor, include_ocr, include_ui)
            else:
                result = {"error": "Enhanced computer control not available"}
        
        elif method == "capture_full_screen":
            if computer_controller:
                monitor = params.get("monitor", 0)
                screenshot = computer_controller.vision.capture_screen(monitor)
                _, buffer = computer_controller.vision.cv2.imencode('.jpg', screenshot)
                result = {"image": base64.b64encode(buffer).decode('utf-8')}
            else:
                # Fallback to basic screenshot
                screenshot = pyautogui.screenshot()
                result = {"image": _png(screenshot)}
        
        elif method == "extract_text":
            if computer_controller:
                monitor = params.get("monitor", 0)
                screenshot = computer_controller.vision.capture_screen(monitor)
                text_results = computer_controller.vision.extract_text(screenshot)
                result = {"text_elements": text_results}
            else:
                result = {"error": "OCR not available without enhanced control"}
        
        elif method == "click_at_text":
            if computer_controller:
                text = params.get("text", "")
                monitor = params.get("monitor", 0)
                success = computer_controller.find_and_click_text(text, monitor)
                result = {"success": success, "text": text}
            else:
                result = {"error": "Text clicking not available without enhanced control"}
        
        elif method == "get_all_windows":
            if computer_controller:
                windows = computer_controller.window_manager.get_all_windows()
                result = {"windows": windows}
            else:
                result = {"error": "Window management not available without enhanced control"}
        
        elif method == "activate_window":
            if computer_controller:
                title = params.get("title_pattern", "")
                success = computer_controller.window_manager.activate_window(title)
                result = {"success": success, "title": title}
            else:
                result = {"error": "Window management not available without enhanced control"}
        
        elif method == "get_system_info":
            if computer_controller:
                info = computer_controller.get_system_info()
                result = info
            else:
                # Basic system info fallback
                screen_size = pyautogui.size()
                mouse_pos = pyautogui.position()
                result = {
                    "screen_size": {"width": screen_size.width, "height": screen_size.height},
                    "mouse_position": {"x": mouse_pos.x, "y": mouse_pos.y},
                    "enhanced_control": False
                }
        
        elif method == "automate_task":
            if computer_controller:
                description = params.get("description", "")
                steps = params.get("steps", [])
                result = computer_controller.automate_task(description, steps)
            else:
                result = {"error": "Task automation not available without enhanced control"}
        
        # Legacy methods with enhanced fallback
        elif method in {"type_text", "keyboard_type"}:
            text = params.get("text", "")
            interval = params.get("interval", 0.0)
            
            if computer_controller:
                success = computer_controller.input.type_text(text, interval)
                result = {"success": success}
            else:
                pyautogui.write(text, interval=interval)
                result = {"success": True}
        
        elif method in {"click_screen", "mouse_click"}:
            # Enhanced click with relative coordinates support
            x = params.get("x")
            y = params.get("y")
            x_rel = params.get("x_rel")
            y_rel = params.get("y_rel")
            button = params.get("button", "left")
            
            if computer_controller:
                if x_rel is not None and y_rel is not None:
                    success = computer_controller.input.click_relative(x_rel, y_rel, button)
                else:
                    x, y = _rel2abs(x, y)
                    success = computer_controller.input.click(x, y, button)
                result = {"success": success, "x": x, "y": y}
            else:
                # Legacy click
                x, y = _rel2abs(x, y)
                pyautogui.click(x=x, y=y, button=button)
                result = {"success": True, "x": x, "y": y}
        
        elif method in {"move_mouse", "mouse_move"}:
            x = params.get("x")
            y = params.get("y")
            x_rel = params.get("x_rel")
            y_rel = params.get("y_rel")
            duration = params.get("duration", 0.2)
            
            if x_rel is not None and y_rel is not None:
                x, y = _rel2abs(x_rel, y_rel)
            else:
                x, y = _rel2abs(x, y)
            
            pyautogui.moveTo(x, y, duration=duration)
            result = {"success": True, "x": x, "y": y}
        
        elif method == "scroll":
            x = params.get("x", 0)
            y = params.get("y", 0)
            clicks = params.get("clicks", 3)
            direction = params.get("direction", "up")
            
            if computer_controller:
                success = computer_controller.input.scroll(x, y, clicks, direction)
                result = {"success": success}
            else:
                scroll_amount = clicks if direction == "up" else -clicks
                pyautogui.scroll(scroll_amount, x=x, y=y)
                result = {"success": True}
        
        elif method == "press_key":
            key = params.get("key", "")
            presses = params.get("presses", 1)
            
            if computer_controller:
                success = computer_controller.input.press_key(key, presses)
                result = {"success": success}
            else:
                pyautogui.press(key, presses=presses)
                result = {"success": True}
        
        elif method == "key_combination":
            keys = params.get("keys", [])
            
            if computer_controller:
                success = computer_controller.input.key_combination(keys)
                result = {"success": success}
            else:
                pyautogui.hotkey(*keys)
                result = {"success": True}
        
        elif method in {"take_screenshot", "screen_capture"}:
            if computer_controller:
                monitor = params.get("monitor", 0)
                screenshot = computer_controller.vision.capture_screen(monitor)
                _, buffer = computer_controller.vision.cv2.imencode('.jpg', screenshot)
                result = {"image": base64.b64encode(buffer).decode('utf-8')}
            else:
                screenshot = pyautogui.screenshot()
                result = {"image": _png(screenshot)}
        
        elif method == "set_ai_crop":
            # Set AI crop region for focused analysis
            AI_CROP.update({
                "x0": int(params.get("x0", 0)),
                "y0": int(params.get("y0", 0)),
                "w": int(params.get("w")) if params.get("w") else None,
                "h": int(params.get("h")) if params.get("h") else None,
            })
            result = {"status": "crop-updated", "crop": AI_CROP}
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        response["result"] = result
        
    except Exception as e:
        log.error(f"RPC error for method '{method}': {e}")
        response["error"] = {"code": -32603, "message": str(e)}
    
    return web.json_response(response)

async def health_check(req: web.Request):
    """Health check endpoint."""
    return web.json_response({
        "status": "healthy",
        "enhanced_control": ENHANCED_CONTROL_AVAILABLE,
        "capabilities": {
            "basic_control": True,
            "enhanced_vision": ENHANCED_CONTROL_AVAILABLE,
            "ocr": ENHANCED_CONTROL_AVAILABLE,
            "window_management": ENHANCED_CONTROL_AVAILABLE,
            "task_automation": ENHANCED_CONTROL_AVAILABLE
        }
    })

def main() -> None:
    ap = argparse.ArgumentParser(description="AB498 Enhanced Computer Control Server")
    ap.add_argument("--port", type=int, default=3011, help="Server port")
    ap.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    args = ap.parse_args()
    
    app = web.Application()
    app.router.add_post("/rpc", rpc)
    app.router.add_get("/health", health_check)
    
    log.info(f"🚀 AB498 Enhanced Control Server starting on {args.host}:{args.port}")
    log.info(f"Enhanced control: {'✅ Available' if ENHANCED_CONTROL_AVAILABLE else '❌ Basic mode only'}")
    
    web.run_app(app, host=args.host, port=args.port, access_log=log)

if __name__ == "__main__":
    main()
