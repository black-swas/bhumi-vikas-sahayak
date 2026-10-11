#!/usr/bin/env node
// Fails when a translation key has no Hindi, has an unsupported language, or when the Hindi
// value is just the English text copied over. Only en and hi are supported (SPEC §14).
const fs = require("fs");
const path = require("path");

// Keys whose value is genuinely the same in both languages (numbers, symbols, shared terms).
const IDENTICAL_VALUE_ALLOWLIST = new Set(["COMMON$DASH", "SLIP$PDF_PAGE_FORMAT"]);

function getSupportedLanguageCodes() {
  const source = fs.readFileSync(path.join(__dirname, "../src/i18n/index.ts"), "utf8");
  const re = /\{ label: "[^"]+", value: "([^"]+)" \}/g;
  const codes = [];
  let m;
  while ((m = re.exec(source)) !== null) codes.push(m[1]);
  return codes;
}

function checkTranslations(translationJson, supported) {
  const missing = {};
  const extra = {};
  const untranslated = {};
  const nonEnglish = supported.filter((c) => c !== "en");
  for (const [key, translations] of Object.entries(translationJson)) {
    const available = Object.keys(translations);
    const gone = supported.filter((c) => !available.includes(c) || !String(translations[c]).trim());
    if (gone.length) missing[key] = gone;
    const more = available.filter((c) => !supported.includes(c));
    if (more.length) extra[key] = more;
    if (
      !IDENTICAL_VALUE_ALLOWLIST.has(key) &&
      translations.en !== undefined &&
      nonEnglish.every((c) => translations[c] === translations.en)
    ) {
      untranslated[key] = translations.en;
    }
  }
  return { missing, extra, untranslated };
}

module.exports = { IDENTICAL_VALUE_ALLOWLIST, getSupportedLanguageCodes, checkTranslations };

if (require.main === module) {
  const json = JSON.parse(
    fs.readFileSync(path.join(__dirname, "../src/i18n/translation.json"), "utf8"),
  );
  const supported = getSupportedLanguageCodes();
  if (supported.join() !== "en,hi") {
    console.error(`ERROR: supported languages must be exactly en and hi, found: ${supported}`);
    process.exit(1);
  }
  const { missing, extra, untranslated } = checkTranslations(json, supported);
  let failed = false;
  for (const [title, found, fmt] of [
    ["Missing translations", missing, (v) => `missing: ${v.join(", ")}`],
    ["Unsupported languages", extra, (v) => `extra: ${v.join(", ")}`],
    ["English copied into Hindi", untranslated, (v) => `same text: "${v}"`],
  ]) {
    if (Object.keys(found).length) {
      failed = true;
      console.error(`\x1b[31mERROR: ${title}\x1b[0m`);
      for (const [key, v] of Object.entries(found)) console.error(`- ${key}: ${fmt(v)}`);
    }
  }
  if (failed) process.exit(1);
  console.log(`\x1b[32mAll ${Object.keys(json).length} translation keys have en and hi.\x1b[0m`);
}
