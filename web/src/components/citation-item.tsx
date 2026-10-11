import { BadgeCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Citation } from "#/api/types";
import { I18nKey } from "#/i18n/declaration";
import { useUiStore } from "#/stores/ui-store";

interface CitationItemProps {
  citation: Citation;
  turnId: string;
}

const BUTTON =
  "min-h-9 rounded-md border border-border-input bg-surface px-3 py-1 text-sm font-medium text-contrast hover:bg-surface-raised";

/** One verified quote with its rule label, page, and links to both official PDF pages. */
export function CitationItem({ citation, turnId }: CitationItemProps) {
  const { t } = useTranslation();
  const openPdf = useUiStore((s) => s.openPdf);
  const openRule = useUiStore((s) => s.openRule);

  return (
    <li
      data-testid="citation"
      className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface p-3"
    >
      <div className="text-sm font-semibold text-contrast">
        {t(I18nKey.CARD$QUOTE_FROM, {
          label: citation.label,
          title: citation.title,
          page: citation.page,
        })}
      </div>
      {/* The quote is plain text from the rules, never markup. */}
      <blockquote
        lang="en"
        className="border-s-4 border-primary ps-3 text-base text-text-secondary [overflow-wrap:anywhere]"
      >
        {citation.quote}
      </blockquote>
      <div className="flex items-center gap-1.5 text-sm text-emerald-800 dark:text-emerald-300">
        <BadgeCheck className="size-4" aria-hidden />
        {t(I18nKey.CARD$VERIFIED)}
        <span className="text-text-dim">· {t(I18nKey.CARD$OFFICIAL_TEXT)}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={BUTTON}
          onClick={() => openPdf(turnId, { lang: "en", page: citation.page })}
        >
          {t(I18nKey.CARD$PDF_EN, { page: citation.page })}
        </button>
        <button
          type="button"
          className={BUTTON}
          onClick={() => openPdf(turnId, { lang: "hi", page: citation.page })}
        >
          {t(I18nKey.CARD$PDF_HI, { page: citation.page })}
        </button>
        <button
          type="button"
          className={BUTTON}
          onClick={() =>
            openRule(turnId, { rule: citation.rule, quote: citation.quote })
          }
        >
          {t(I18nKey.CARD$OPEN_RULE, { rule: citation.rule })}
        </button>
      </div>
    </li>
  );
}
