import { createInstance, type i18n as I18nInstance } from "i18next";
import { initReactI18next } from "react-i18next";
import translationDefinitions from "./translation.json";

// The scripts/check-translation-completeness.cjs script reads this list: en and hi only.
export const AvailableLanguages = [
  { label: "English", value: "en" },
  { label: "हिंदी", value: "hi" },
] as const;

export type Language = (typeof AvailableLanguages)[number]["value"];

const LANGUAGE_STORAGE_KEY = "bvs-language";

type Definitions = Record<string, Partial<Record<string, string>>>;

function buildResources(definitions: Definitions) {
  const resources: Record<string, { translation: Record<string, string> }> = {};
  for (const [key, translations] of Object.entries(definitions)) {
    for (const [lang, value] of Object.entries(translations)) {
      if (typeof value !== "string") continue;
      (resources[lang] ??= { translation: {} }).translation[key] = value;
    }
  }
  return resources;
}

export function readStoredLanguage(): Language {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored === "hi" || stored === "en") return stored;
  } catch {
    // privacy mode: fall through to the default
  }
  return "en";
}

const instance: I18nInstance = createInstance();

void instance.use(initReactI18next).init({
  resources: buildResources(translationDefinitions as Definitions),
  lng: typeof window === "undefined" ? "en" : readStoredLanguage(),
  fallbackLng: "en",
  supportedLngs: AvailableLanguages.map((l) => l.value),
  defaultNS: "translation",
  initAsync: false,
  // React escapes at render time; double escaping would corrupt text such as "&".
  interpolation: { escapeValue: false },
});

/** Switch language, remember it for next time, and keep <html lang> in step. */
export function setLanguage(lang: Language): void {
  void instance.changeLanguage(lang);
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
  } catch {
    // ignore
  }
  if (typeof document !== "undefined") document.documentElement.lang = lang;
}

export default instance;
