import { useQuery } from "@tanstack/react-query";
import { CircleCheck, CircleX } from "lucide-react";
import type React from "react";
import { useTranslation } from "react-i18next";
import { api } from "#/api/client";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { I18nKey } from "#/i18n/declaration";
import { formatIst } from "#/lib/format";

function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border bg-base-secondary p-4">
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd className="text-2xl font-semibold text-contrast">{value}</dd>
      {note ? <dd className="text-xs text-text-dim">{note}</dd> : null}
    </div>
  );
}

const pct = (x: number) => `${Math.round(x * 1000) / 10}%`;
const ms = (x: number) =>
  x >= 1000 ? `${(x / 1000).toFixed(1)} s` : `${Math.round(x)} ms`;

/** The latest evaluation report from /api/eval/latest, as measured. */
export default function AccuracyRoute() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["eval"],
    queryFn: api.evalLatest,
    retry: false,
  });

  let body: React.ReactNode;
  if (query.isPending) {
    body = (
      <div
        role="status"
        className="flex items-center gap-2 text-text-secondary"
      >
        <LoadingSpinner size="small" />
        {t(I18nKey.ACCURACY$LOADING)}
      </div>
    );
  } else if (query.isError) {
    body = <p role="alert">{t(I18nKey.ACCURACY$ERROR)}</p>;
  } else if (!query.data.available) {
    body = <p data-testid="no-report">{t(I18nKey.ACCURACY$NO_REPORT)}</p>;
  } else {
    const { summary: s, cases, generated_at: generated } = query.data;
    const passed = cases.filter((c) => c.pass).length;
    const measured = t(I18nKey.ACCURACY$MEASURED);
    body = (
      <>
        {generated ? (
          <p className="text-sm text-text-dim">
            {t(I18nKey.ACCURACY$GENERATED, { when: formatIst(generated) })}
          </p>
        ) : null}
        <dl
          data-testid="eval-summary"
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          <Stat
            label={t(I18nKey.ACCURACY$STATUS)}
            value={pct(s.status_accuracy)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$RULE_HIT)}
            value={t(I18nKey.ACCURACY$OF, {
              n: s.rule_hit,
              total: s.rule_hit_total,
            })}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$VALUES)}
            value={pct(s.value_accuracy)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$ABSTENTION)}
            value={pct(s.abstention)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$FABRICATION_SHOWN)}
            value={String(s.fabrication_shown)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$FABRICATION_TRIED)}
            value={String(s.fabrication_attempted)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$INJECTION)}
            value={pct(s.injection_resistance)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$LATENCY_P50)}
            value={ms(s.latency_ms.p50)}
            note={measured}
          />
          <Stat
            label={t(I18nKey.ACCURACY$LATENCY_P95)}
            value={ms(s.latency_ms.p95)}
            note={measured}
          />
        </dl>
        <section className="flex flex-col gap-2" aria-labelledby="cases-title">
          <h2 id="cases-title" className="text-xl font-semibold text-contrast">
            {t(I18nKey.ACCURACY$CASES)} (
            {t(I18nKey.ACCURACY$OF, { n: passed, total: cases.length })})
          </h2>
          <div className="overflow-x-auto rounded-xl border border-border">
            <table
              data-testid="eval-cases"
              className="w-full text-start text-sm"
            >
              <thead className="bg-surface text-text-secondary">
                <tr>
                  <th className="p-2 text-start">
                    {t(I18nKey.ACCURACY$COL_ID)}
                  </th>
                  <th className="p-2 text-start">
                    {t(I18nKey.ACCURACY$COL_QUESTION)}
                  </th>
                  <th className="p-2 text-start">
                    {t(I18nKey.ACCURACY$COL_EXPECTED)}
                  </th>
                  <th className="p-2 text-start">
                    {t(I18nKey.ACCURACY$COL_GOT)}
                  </th>
                  <th className="p-2 text-start">
                    {t(I18nKey.ACCURACY$COL_RESULT)}
                  </th>
                  <th className="p-2 text-end">{t(I18nKey.ACCURACY$COL_MS)}</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id} className="border-t border-border-subtle">
                    <td className="p-2 font-mono">{c.id}</td>
                    <td className="p-2 [overflow-wrap:anywhere]">
                      {c.question}
                    </td>
                    <td className="p-2">{c.expected_status}</td>
                    <td className="p-2">{c.status}</td>
                    <td className="p-2">
                      <span
                        className={
                          c.pass
                            ? "inline-flex items-center gap-1 font-semibold text-emerald-800 dark:text-emerald-300"
                            : "inline-flex items-center gap-1 font-semibold text-red-800 dark:text-red-300"
                        }
                      >
                        {c.pass ? (
                          <CircleCheck className="size-4" aria-hidden />
                        ) : (
                          <CircleX className="size-4" aria-hidden />
                        )}
                        {t(
                          c.pass
                            ? I18nKey.ACCURACY$PASS
                            : I18nKey.ACCURACY$FAIL,
                        )}
                      </span>
                    </td>
                    <td className="p-2 text-end">
                      {c.latency_ms ?? t(I18nKey.COMMON$DASH)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 overflow-y-auto p-4 pb-12">
      <h1 className="text-3xl font-semibold text-contrast">
        {t(I18nKey.ACCURACY$TITLE)}
      </h1>
      <p className="text-text-secondary">{t(I18nKey.ACCURACY$INTRO)}</p>
      {body}
    </div>
  );
}
