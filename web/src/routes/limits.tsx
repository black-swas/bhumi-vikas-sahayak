import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

const NOT_ITEMS = [
  I18nKey.LIMITS$NOT_1,
  I18nKey.LIMITS$NOT_2,
  I18nKey.LIMITS$NOT_3,
  I18nKey.LIMITS$NOT_4,
  I18nKey.LIMITS$NOT_5,
  I18nKey.LIMITS$NOT_6,
];
const ESC_ITEMS = [
  I18nKey.LIMITS$ESC_1,
  I18nKey.LIMITS$ESC_2,
  I18nKey.LIMITS$ESC_3,
];

/** What the tool does NOT do, and when to escalate (SPEC §2.2, §2.3). */
export default function LimitsRoute() {
  const { t } = useTranslation();

  // the card links to #escalate; the router does not scroll to it by itself
  React.useEffect(() => {
    if (window.location.hash === "#escalate") {
      document.getElementById("escalate")?.scrollIntoView?.();
    }
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 overflow-y-auto p-4 pb-12">
      <h1 className="text-3xl font-semibold text-contrast">
        {t(I18nKey.LIMITS$TITLE)}
      </h1>
      <section aria-labelledby="not-title" className="flex flex-col gap-3">
        <h2 id="not-title" className="text-xl font-semibold text-contrast">
          {t(I18nKey.LIMITS$NOT_TITLE)}
        </h2>
        <ul className="list-disc space-y-2 ps-6 text-lg text-text-secondary">
          {NOT_ITEMS.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      </section>
      <section
        id="escalate"
        aria-labelledby="esc-title"
        className="flex flex-col gap-3"
      >
        <h2 id="esc-title" className="text-xl font-semibold text-contrast">
          {t(I18nKey.LIMITS$ESCALATE_TITLE)}
        </h2>
        <ul className="list-disc space-y-2 ps-6 text-lg text-text-secondary">
          {ESC_ITEMS.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
        <p className="text-text-secondary">{t(I18nKey.LIMITS$NO_CONTACTS)}</p>
      </section>
      <p className="text-sm text-text-dim">{t(I18nKey.LIMITS$ABOUT)}</p>
    </div>
  );
}
