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

        # --- CLICK ------------------------------------------------------
        elif m in {"click_screen", "mouse_click"}:
            x, y = _extract_xy(p)
            pyautogui.click(x=x, y=y, button=p.get("button", "left"))
            res = True

        # --- MOVE -------------------------------------------------------
        elif m in {"move_mouse", "mouse_move"}:
            x, y = _extract_xy(p)
            pyautogui.moveTo(x, y, duration=p.get("duration", 0.2))
            res = True

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
