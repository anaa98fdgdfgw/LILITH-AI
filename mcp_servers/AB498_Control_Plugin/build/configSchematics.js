"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.configSchematics = void 0;
const zod_1 = require("zod");
/** Schéma de config du plugin AB498. */
exports.configSchematics = {
    rpcPort: zod_1.z
        .number()
        .default(3011)
        .describe("Local JSON-RPC port for AB498 control server"),
};
