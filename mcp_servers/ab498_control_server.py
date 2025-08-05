#!/usr/bin/env python
"""AB498 control server – version conforme README, avec alias & coords relatives."""
from __future__ import annotations
import argparse, io, base64, logging
from typing import Any, Dict

import pyautogui
from PIL import Image
from aiohttp import web

pyautogui.FAILSAFE = False
log = logging.getLogger("ab498")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AI_CROP = {"x0": 0, "y0": 0, "w": None, "h": None}  # None = plein écran
# ---------------------------------------------------------------------
def _rel2abs(x: float | int | None,
             y: float | int | None) -> tuple[int | None, int | None]:
    """Convertit (x_rel/y_rel) ∈ 0-1 en pixels écran selon AI_CROP ou écran plein."""
    if x is None or y is None:
        return x, y
        
    screen_w, screen_h = pyautogui.size()
    
    # Determine the base area for coordinate calculation
    if AI_CROP["w"] is None:  # Full screen mode
        base_x, base_y, base_w, base_h = 0, 0, screen_w, screen_h
    else:  # Cropped area mode
        base_x = AI_CROP["x0"]
        base_y = AI_CROP["y0"]
        base_w = AI_CROP["w"]
        base_h = AI_CROP["h"]
    
    xf, yf = float(x), float(y)
    
    # If coordinates are in 0-1 range, treat as relative
    if 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:
        xf = base_x + xf * base_w
        yf = base_y + yf * base_h
    
    return int(round(xf)), int(round(yf))

def _png(img: Image.Image) -> str:
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def _extract_xy(p: Dict[str, Any]) -> tuple[int | None, int | None]:
    if "x_rel" in p and "y_rel" in p:
        return _rel2abs(p["x_rel"], p["y_rel"])
    return p.get("x"), p.get("y")

async def rpc(req: web.Request):
    d: Dict[str, Any] = await req.json()
    m, p = d.get("method"), d.get("params", {}) or {}
    out: Dict[str, Any] = {"jsonrpc": "2.0", "id": d.get("id")}
    try:
        # --- KEYBOARD ---------------------------------------------------
        if m in {"type_text", "keyboard_type"}:       # ← alias support
            pyautogui.write(p["text"])
            res = True

        elif m == "set_ai_crop":
            # params: {x0, y0, w, h}  (pixels dans l'écran physique)
            AI_CROP.update({
                "x0": int(p["x0"]),
                "y0": int(p["y0"]),
                "w": int(p["w"]),
                "h": int(p["h"]),
            })
            res = {"status": "crop-updated"}

        # --- CLICK ---------------------------------------------------------
        elif m in {"click_screen", "mouse_click"}:
            # priorité aux coords relatives si présentes
            if "x_rel" in p and "y_rel" in p:
                x, y = _rel2abs(p["x_rel"], p["y_rel"])
            else:
                x, y = _rel2abs(p.get("x"), p.get("y"))
            pyautogui.click(x=x, y=y, button=p.get("button", "left"))
            res = True

        # --- MOVE ----------------------------------------------------------
        elif m in {"move_mouse", "mouse_move"}:
            if "x_rel" in p and "y_rel" in p:
                x, y = _rel2abs(p["x_rel"], p["y_rel"])
            else:
                x, y = _rel2abs(p.get("x"), p.get("y"))
            pyautogui.moveTo(x, y, duration=p.get("duration", 0.2))
            res = True

        # --- SCREENSHOT -------------------------------------------------
        elif m in {"take_screenshot", "screen_capture"}:
            monitor = p.get("monitor", 0)  # 0 = all monitors
            
            # Try MSS first for multi-monitor support
            try:
                import mss
                with mss.mss() as sct:
                    monitors = sct.monitors
                    if monitor < len(monitors):
                        screenshot = sct.grab(monitors[monitor])
                        from PIL import Image
                        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                        res = {"image": _png(img), "method": "mss", "monitor": monitor}
                    else:
                        res = {"error": f"Monitor {monitor} not found. Available: 0-{len(monitors)-1}"}
            except ImportError:
                # Fallback to pyautogui
                res = {"image": _png(pyautogui.screenshot()), "method": "pyautogui", "monitor": 0}

        else:
            raise ValueError(f"Unknown method: {m}")

        out["result"] = res
    except Exception as e:
        out["error"] = str(e)
    return web.json_response(out)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3011)
    port = ap.parse_args().port
    app = web.Application()
    app.router.add_post("/rpc", rpc)
    log.info("AB498 control server listening on 127.0.0.1:%s", port)
    web.run_app(app, host="127.0.0.1", port=port)

if __name__ == "__main__":
    main()
