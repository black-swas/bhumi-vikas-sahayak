// Copies the backend's AnswerCard fixtures into src/mocks/fixtures so the UI can run (and be
// tested) with no backend. The copies are committed; rerun this after changing a backend fixture.
import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const from = join(here, "../../backend/tests/fixtures");
const to = join(here, "../src/mocks/fixtures");
mkdirSync(to, { recursive: true });
for (const name of readdirSync(from).filter((n) => /^answer_.*\.json$/.test(n))) {
  copyFileSync(join(from, name), join(to, name));
  console.log(`synced ${name}`);
}
