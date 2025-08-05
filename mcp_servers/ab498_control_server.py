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
def _rel2abs(rx: float | int | None, ry: float | int | None) -> tuple[int | None, int | None]:
    """Convertit (x_rel, y_rel) ∈ 0-1 dans la bbox AI_CROP (ou écran plein)."""
    if rx is None or ry is None:
        return rx, ry
    screen_w, screen_h = pyautogui.size()
    if AI_CROP["w"] is None:                      # flux == écran
        base_x, base_y, base_w, base_h = 0, 0, screen_w, screen_h
    else:
        base_x = AI_CROP["x0"]
        base_y = AI_CROP["y0"]
        base_w = AI_CROP["w"]
        base_h = AI_CROP["h"]
    xf, yf = float(rx), float(ry)
    if 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:     # relatifs
        xf = base_x + xf * base_w
        yf = base_y + yf * base_h
    return int(round(xf)), int(round(yf))

def _rel2abs(x: float | int | None,
             y: float | int | None) -> tuple[int | None, int | None]:
    """Convertit (x_rel/y_rel) ∈ 0-1 en pixels écran ; sinon retourne les pixels."""
    if x is None or y is None:
        return x, y
    w, h = pyautogui.size()
    xf, yf = float(x), float(y)
    if 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:
        xf *= w
        yf *= h
    return int(round(xf)), int(round(yf))

def mouse_move(x: float, y: float, duration: float = 0.2):
    x, y = _rel2abs(x, y)
    pyautogui.moveTo(x, y, duration=duration)
    return {"status": "ok"}

@rpc.method()
def mouse_click(x: float | None = None,
                y: float | None = None,
                button: str = "left"):
    x, y = _rel2abs(x, y)
    pyautogui.click(x=x, y=y, button=button)
    return {"status": "ok"}

def _png(img: Image.Image) -> str:
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def _rel2abs(rx: float, ry: float) -> tuple[int, int]:
    w, h = pyautogui.size()
    return int(rx * w), int(ry * h)

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

elif method == "set_ai_crop":
    # params: {x0, y0, w, h}  (pixels dans l'écran physique)
    AI_CROP.update({
        "x0": int(params["x0"]),
        "y0": int(params["y0"]),
        "w": int(params["w"]),
        "h": int(params["h"]),
    })
    result = {"status": "crop-updated"}


# --- CLICK ---------------------------------------------------------
elif method in {"click_screen", "mouse_click"}:
    # priorité aux coords relatives si présentes
if "x_rel" in params and "y_rel" in params:
    x, y = _rel2abs(params["x_rel"], params["y_rel"])
else:
    x, y = _rel2abs(params.get("x"), params.get("y"))
    else:
        x, y = _rel2abs(params.get("x"), params.get("y"))
    pyautogui.click(x=x, y=y, button=params.get("button", "left"))
    result = True

# --- MOVE ----------------------------------------------------------
elif method in {"move_mouse", "mouse_move"}:
if "x_rel" in params and "y_rel" in params:
    x, y = _rel2abs(params["x_rel"], params["y_rel"])
else:
    x, y = _rel2abs(params.get("x"), params.get("y"))
    else:
        x, y = _rel2abs(params.get("x"), params.get("y"))
    pyautogui.moveTo(x, y, duration=params.get("duration", 0.2))
    result = True

        # --- SCREENSHOT -------------------------------------------------
        elif m in {"take_screenshot", "screen_capture"}:
            res = {"image": _png(pyautogui.screenshot())}

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
