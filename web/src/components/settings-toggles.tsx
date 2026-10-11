import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import { AvailableLanguages, setLanguage, type Language } from "#/i18n";
import { setColorTheme } from "#/themes/color-themes";
import { useColorTheme } from "#/hooks/use-color-theme";
import type { ColorThemeKey } from "#/themes/color-themes";
import { cn } from "#/utils/utils";

const SEGMENT =
  "min-h-9 flex-1 px-3 py-1 text-sm font-medium first:rounded-s-md last:rounded-e-md border border-border-input";

/** EN | हिंदी. The page language, the clerk's choice, remembered for next time. */
export function LanguageToggle() {
  const { t, i18n } = useTranslation();
  const current = (i18n.resolvedLanguage ?? i18n.language) as Language;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-text-secondary">
        {t(I18nKey.NAV$LANGUAGE)}
      </span>
      <div role="group" aria-label={t(I18nKey.NAV$LANGUAGE)} className="flex">
        {AvailableLanguages.map(({ label, value }) => (
          <button
            key={value}
            type="button"
            lang={value}
            aria-pressed={current === value}
            data-testid={`lang-${value}`}
            onClick={() => setLanguage(value)}
            className={cn(
              SEGMENT,
              current === value
                ? "bg-primary text-on-primary"
                : "bg-surface text-contrast hover:bg-surface-raised",
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

const THEMES: [ColorThemeKey, I18nKey][] = [
  ["light-plus", I18nKey.THEME$LIGHT],
  ["neutral-dark", I18nKey.THEME$DARK],
];

export function ThemeToggle() {
  const { t } = useTranslation();
  const current = useColorTheme();
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-text-secondary">
        {t(I18nKey.NAV$THEME)}
      </span>
      <div role="group" aria-label={t(I18nKey.NAV$THEME)} className="flex">
        {THEMES.map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={current === key}
            onClick={() => setColorTheme(key)}
            className={cn(
              SEGMENT,
              current === key
                ? "bg-primary text-on-primary"
                : "bg-surface text-contrast hover:bg-surface-raised",
            )}
          >
            {t(label)}
          </button>
        ))}
      </div>
    </div>
  );
}
