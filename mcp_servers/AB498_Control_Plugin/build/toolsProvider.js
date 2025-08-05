"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.toolsProvider = toolsProvider;
const sdk_1 = require("@lmstudio/sdk");
const zod_1 = require("zod");
/**
 * Simple helper to call the local AB498 JSON‑RPC server.
 */
async function callRpc(port, method, params = {}) {
    const payload = { jsonrpc: "2.0", method, params, id: 1 };
    const res = await fetch(`http://127.0.0.1:${port}/rpc`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.error)
        throw new Error(data.error);
    return data.result;
}
async function toolsProvider(_ctl) {
    // Port fixe ; change ici si besoin.
    const port = 3011;
    const keyboardType = (0, sdk_1.tool)({
        name: "keyboard_type",
        description: (0, sdk_1.text) `Types the given string using the local keyboard.`,
        parameters: {
            text: zod_1.z.string().describe("Text to type"),
            interval: zod_1.z.number().optional().default(0.0).describe("Delay between keystrokes in seconds")
        },
        implementation: async ({ text, interval }) => {
            await callRpc(port, "keyboard_type", { text, interval });
            return "typed";
        }
    });
    const mouseClick = (0, sdk_1.tool)({
        name: "mouse_click",
        description: (0, sdk_1.text) `Clicks the mouse. Defaults to left button.`,
        parameters: {
            button: zod_1.z.enum(["left", "right", "middle"]).optional().default("left")
        },
        implementation: async ({ button }) => {
            await callRpc(port, "mouse_click", { button });
            return "clicked";
        }
    });
    const mouseMove = (0, sdk_1.tool)({
        name: "mouse_move",
        description: (0, sdk_1.text) `Moves the mouse to absolute screen coordinates.`,
        parameters: {
            x: zod_1.z.number(),
            y: zod_1.z.number(),
            duration: zod_1.z.number().optional().default(0.2)
        },
        implementation: async ({ x, y, duration }) => {
            await callRpc(port, "mouse_move", { x, y, duration });
            return "moved";
        }
    });
    const screenCapture = (0, sdk_1.tool)({
        name: "screen_capture",
        description: (0, sdk_1.text) `Captures the entire screen and returns a base64 PNG data URI.`,
        parameters: {},
        implementation: async () => {
            const res = await callRpc(port, "screen_capture");
            return res.image;
        }
    });
    // Expose tools
    return { keyboardType, mouseClick, mouseMove, screenCapture };
}
