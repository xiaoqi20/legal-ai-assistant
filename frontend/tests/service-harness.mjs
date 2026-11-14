import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// Exercise the shipped service source for each uni-app compile target without
// adding a second bundler or requiring a running/paid upstream service.
export function loadService(name, { platform = "H5", request, globals = {}, modules = {} } = {}) {
  let source = readFileSync(new URL(`../src/services/${name}.ts`, import.meta.url), "utf8");
  const active = [true];
  source = source.split("\n").filter((line) => {
    const condition = line.match(/^\s*\/\/ #(ifdef|ifndef) (\S+)/);
    if (condition) {
      const matches = condition[2] === platform;
      active.push(active.at(-1) && (condition[1] === "ifdef" ? matches : !matches));
      return false;
    }
    if (/^\s*\/\/ #endif/.test(line)) { active.pop(); return false; }
    return active.at(-1);
  }).join("\n");
  class ApiError extends Error {
    constructor(status, code, message) { super(message); Object.assign(this, { status, code }); }
  }
  const exports = {};
  let redirects = 0;
  const context = vm.createContext({
    exports, ArrayBuffer, Uint8Array, Uint32Array, DataView, TextEncoder,
    AbortController, Response, ReadableStream, Blob, FormData, File,
    setTimeout, clearTimeout, console, crypto: globalThis.crypto,
    require: (id) => {
      if (Object.hasOwn(modules, id)) return modules[id];
      if (!id.endsWith("request")) throw new Error(`Unexpected runtime import: ${id}`);
      return {
        API_BASE_URL: "http://test.invalid/api/v1", getStoredToken: () => "test-only-token",
        USE_MOCK: false, request, ApiError, redirectToLogin: () => redirects++,
        parseApiError: (status, body) => new ApiError(status, body?.error?.code, body?.error?.message || "请求失败"),
      };
    },
    ...globals,
  });
  vm.runInContext(ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText, context, { filename: `${name}.${platform}.js` });
  return { service: exports, redirects: () => redirects };
}
