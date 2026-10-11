import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";
import { api } from "#/api/client";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { NavigationLink } from "#/components/shared/navigation-link";
import { I18nKey } from "#/i18n/declaration";

/** The full text of one rule, with its pages and the two official PDF links. */
export default function RuleRoute() {
  const { t } = useTranslation();
  const { ruleId = "" } = useParams();
  const query = useQuery({
    queryKey: ["rule", ruleId],
    queryFn: () => api.rule(ruleId),
    retry: false,
    staleTime: Infinity,
  });

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 overflow-y-auto p-4 pb-12">
      <NavigationLink to="/" className="text-sm underline">
        {t(I18nKey.RULE$BACK)}
      </NavigationLink>
      {query.isPending ? (
        <div role="status" className="flex items-center gap-2">
          <LoadingSpinner size="small" />
          {t(I18nKey.PANEL$RULE_LOADING)}
        </div>
      ) : query.isError ? (
        <p role="alert">{t(I18nKey.RULE$NOT_FOUND)}</p>
      ) : (
        <>
          <h1 className="text-3xl font-semibold text-contrast">
            {t(I18nKey.RULE$TITLE, { rule: query.data.rule })} ·{" "}
            {query.data.title}
          </h1>
          <p className="text-text-secondary">
            {t(I18nKey.PANEL$RULE_PAGES, {
              start: query.data.page_start,
              end: query.data.page_end,
            })}
            {query.data.parent
              ? ` · ${t(I18nKey.RULE$INSERTED_IN, { parent: query.data.parent })}`
              : ""}
          </p>
          <div className="flex gap-3">
            <a
              className="underline"
              href={query.data.pdf_en}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t(I18nKey.CARD$PDF_EN, { page: query.data.page_start })}
            </a>
            <a
              className="underline"
              href={query.data.pdf_hi}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t(I18nKey.CARD$PDF_HI, { page: query.data.page_start })}
            </a>
          </div>
          <pre
            lang="en"
            className="whitespace-pre-wrap rounded-lg border border-border-subtle bg-surface p-4 font-sans text-contrast"
          >
            {query.data.text}
          </pre>
        </>
      )}
    </div>
  );
}
