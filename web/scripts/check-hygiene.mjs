// SPEC §16.3 / CLAUDE.md #11, #13: fails if imported-shell leftovers or secrets reach the bundle.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const SKIP_DIRS = new Set(["node_modules", "build", ".react-router", "pdf", "locales"]);
const SKIP_FILES = new Set([
  "mockServiceWorker.js",
  "package-lock.json",
  "check-hygiene.mjs",
  "eslint.config.js", // names the banned packages in its no-restricted-imports rule
]);
const FORBIDDEN = [
  "googleapis",
  "posthog",
  "openhands.dev",
  "assets.openhands",
  "react-markdown",
  "rehype-raw",
  "@xterm",
  "monaco-editor",
  "typescript-client",
  "@openhands",
  "OpenHands",
  "Agent Canvas",
];
// dangerouslySetInnerHTML is allowed only for the theme bootstrap script in root.tsx.
const DANGER_ALLOWED = new Set(["src/root.tsx"]);
const SECRET_VITE = /VITE_[A-Z0-9_]*(KEY|SECRET|TOKEN|PASSWORD|DATABASE|HASH)/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name) || SKIP_FILES.has(name)) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(ts|tsx|js|mjs|cjs|json|css|html|svg|md)$/.test(name)) yield full;
  }
}

const problems = [];
for (const file of walk(root)) {
  const rel = relative(root, file).replaceAll("\\", "/");
  const text = readFileSync(file, "utf8");
  for (const word of FORBIDDEN) {
    if (text.includes(word)) problems.push(`${rel}: contains "${word}"`);
  }
  if (text.includes("dangerouslySetInnerHTML") && !DANGER_ALLOWED.has(rel)) {
    problems.push(`${rel}: dangerouslySetInnerHTML`);
  }
  if (SECRET_VITE.test(text)) problems.push(`${rel}: a secret-looking VITE_ variable`);
}
const lock = readFileSync(join(root, "package-lock.json"), "utf8");
for (const word of ["posthog-js", "@xterm/", "monaco-editor", "react-markdown", "rehype-raw", "@openhands/"]) {
  if (lock.includes(`"node_modules/${word}`) || lock.includes(`"${word}`)) {
    problems.push(`package-lock.json: depends on ${word}`);
  }
}
if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log("hygiene ok: no telemetry, CDN fonts, OpenHands branding, markdown renderers or secret VITE_ vars");
