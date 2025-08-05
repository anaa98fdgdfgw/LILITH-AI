import { tool, text, ToolsProviderController } from "@lmstudio/sdk";
import { z } from "zod";

async function callRpc(port: number, method: string, params: any = {}) {
  const body = { jsonrpc: "2.0", method, params, id: 1 };
  const r = await fetch(`http://127.0.0.1:${port}/rpc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

export async function toolsProvider(_: ToolsProviderController) {
  const port = 3011;                                         // ← fixe le port

  /* ========== type_text ================================================ */
  const typeText = tool({
    name: "type_text",
    description: text`Types the given string via the local keyboard.`,
    parameters: { text: z.string() },
    implementation: async ({ text }) => {
      await callRpc(port, "type_text", { text });
      return "typed";
    },
  });

  /* ========== click_screen ============================================= */
  const clickScreen = tool({
    name: "click_screen",
    description: text`Clicks the screen at absolute (x,y) pixels or relative (x_rel,y_rel).`,
    parameters: {
      x: z.number().optional(),
      y: z.number().optional(),
      x_rel: z.number().min(0).max(1).optional(),
      y_rel: z.number().min(0).max(1).optional(),
      button: z.enum(["left", "right", "middle"]).optional().default("left"),
    },
    implementation: async (args) => {
      await callRpc(port, "click_screen", args);
      return "clicked";
    },
  });

  /* ========== move_mouse ============================================== */
  const moveMouse = tool({
    name: "move_mouse",
    description: text`Moves the mouse to absolute or relative coords.`,
    parameters: {
      x: z.number().optional(),
      y: z.number().optional(),
      x_rel: z.number().min(0).max(1).optional(),
      y_rel: z.number().min(0).max(1).optional(),
      duration: z.number().optional().default(0.2),
    },
    implementation: async (args) => {
      await callRpc(port, "move_mouse", args);
      return "moved";
    },
  });

  /* ========== take_screenshot ========================================= */
  const takeScreenshot = tool({
    name: "take_screenshot",
    description: text`Captures the screen and returns a base64 PNG.`,
    parameters: {},
    implementation: async () => {
      const { image } = await callRpc(port, "take_screenshot");
      return image;
    },
  });

  return { typeText, clickScreen, moveMouse, takeScreenshot };
}
