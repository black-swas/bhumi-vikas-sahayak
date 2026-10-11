import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import { useHealth } from "#/hooks/use-health";

/** On every screen, the hosted copy included: what this is and which rules version it knows. */
export function TopBanner() {
  const { t } = useTranslation();
  const { data } = useHealth();
  const count = data?.amendments.length;
  const parts = [
    t(I18nKey.BANNER$PROTOTYPE),
    t(I18nKey.BANNER$NOT_LEGAL_ADVICE),
    t(I18nKey.BANNER$RULES_VERSION),
  ];
  if (count !== undefined) {
    parts.push(
      count === 0
        ? t(I18nKey.BANNER$NO_AMENDMENTS)
        : t(
            count === 1
              ? I18nKey.BANNER$AMENDMENTS_ONE
              : I18nKey.BANNER$AMENDMENTS_OTHER,
            {
              count,
            },
          ),
    );
  }
  return (
    <div
      role="note"
      data-testid="top-banner"
      className="border-b border-amber-700 bg-amber-100 px-4 py-2 text-sm font-medium text-amber-950 dark:bg-amber-950 dark:text-amber-100"
    >
      {parts.join(" · ")}
    </div>
  );
}
