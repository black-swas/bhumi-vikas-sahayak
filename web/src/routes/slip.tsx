import { Printer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";
import { NavigationLink } from "#/components/shared/navigation-link";
import { I18nKey } from "#/i18n/declaration";
import { formatIst, formatResult } from "#/lib/format";
import { turnById, useThreadStore } from "#/stores/thread-store";

/**
 * Print layout for one answer (SPEC §16.8): no rail, no panel, no logo, no QR code and no
 * official styling. It is the clerk's note to the citizen, labelled as a prototype.
 */
export default function SlipRoute() {
  const { t } = useTranslation();
  const { turnId } = useParams();
  const turn = useThreadStore((s) => turnById(s.turns, turnId ?? null));
  const card = turn?.card;

  if (!turn || !card) {
    return (
      <div className="mx-auto max-w-2xl p-6" data-testid="slip-missing">
        <p className="mb-4 text-lg">{t(I18nKey.SLIP$MISSING)}</p>
        <NavigationLink to="/" className="underline">
          {t(I18nKey.SLIP$BACK)}
        </NavigationLink>
      </div>
    );
  }

  const assumptions = [
    ...new Set(card.calculations.flatMap((c) => c.assumptions)),
  ];
  const values = card.calculations
    .map((c) => ({
      id: `${c.calc_id}-${c.sub_rule}-${c.matched_row_text}`,
      text: formatResult(
        c.result,
        ((c.details ?? {}) as Record<string, unknown>).display,
      ),
      calc: c,
    }))
    .filter((v) => v.text !== null);

  return (
    <div
      data-testid="slip"
      lang={card.lang}
      className="mx-auto flex max-w-3xl flex-col gap-5 bg-white p-6 text-black print:max-w-none print:p-0"
    >
      <div className="flex items-center justify-between gap-3 print:hidden">
        <NavigationLink to="/" className="text-sm underline">
          {t(I18nKey.SLIP$BACK)}
        </NavigationLink>
        <button
          type="button"
          data-testid="print-button"
          onClick={() => window.print()}
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-black px-4 py-2 font-semibold text-white"
        >
          <Printer className="size-5" aria-hidden />
          {t(I18nKey.SLIP$PRINT)}
        </button>
      </div>

      <header className="flex flex-col gap-1 border-b-2 border-black pb-3">
        <h1 className="text-2xl font-bold">{t(I18nKey.SLIP$TITLE)}</h1>
        <p className="text-lg font-bold" data-testid="slip-disclaimer">
          {t(I18nKey.SLIP$DISCLAIMER)}
        </p>
        <p className="text-sm">{t(I18nKey.SLIP$CLERK_DECIDES)}</p>
        <p className="text-sm">
          {t(I18nKey.SLIP$DATE)}:{" "}
          <span data-testid="slip-date">
            {formatIst(new Date().toISOString())}
          </span>
        </p>
      </header>

      <section>
        <h2 className="font-bold">{t(I18nKey.SLIP$QUESTION)}</h2>
        <p className="[overflow-wrap:anywhere]">{turn.question}</p>
      </section>

      <section>
        <h2 className="font-bold">
          {t(I18nKey.SLIP$ANSWER)} · {t(`STATUS$${card.status}` as I18nKey)}
        </h2>
        <p className="whitespace-pre-line">{card.answer}</p>
      </section>

      {values.length > 0 ? (
        <section>
          <h2 className="font-bold">{t(I18nKey.SLIP$VALUES)}</h2>
          <ul className="list-disc ps-5">
            {values.map(({ id, text, calc }) => (
              <li key={id}>
                {text} (
                {t(I18nKey.WORKING$SOURCE, {
                  rule: calc.rule,
                  sub: calc.sub_rule,
                  page: calc.page,
                })}
                )
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {assumptions.length > 0 ? (
        <section>
          <h2 className="font-bold">{t(I18nKey.SLIP$ASSUMPTIONS)}</h2>
          <ul className="list-disc ps-5">
            {assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {card.citations.length > 0 ? (
        <section>
          <h2 className="font-bold">{t(I18nKey.SLIP$SOURCES)}</h2>
          <ul className="flex flex-col gap-2">
            {card.citations.map((c) => (
              <li
                key={`${c.chunk_id}-${c.quote}`}
                className="break-inside-avoid"
              >
                <span className="font-semibold">
                  {t(I18nKey.SLIP$PDF_PAGE_FORMAT, {
                    label: `${t(I18nKey.RULE$TITLE, { rule: c.label })}`,
                    page: c.page,
                  })}
                </span>
                <blockquote
                  lang="en"
                  className="border-s-2 border-black ps-2 text-sm"
                >
                  {c.quote}
                </blockquote>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {card.warnings.length > 0 ? (
        <section>
          <h2 className="font-bold">{t(I18nKey.SLIP$NOTICES)}</h2>
          <ul className="list-disc ps-5 text-sm">
            {card.warnings.map((w) => (
              <li key={`${w.type}-${w.id ?? w.text}`}>{w.text}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <footer className="border-t border-black pt-2 text-sm">
        {t(I18nKey.SLIP$VERSION)}: {card.version.label} ·{" "}
        {card.version.corpus_sha256.slice(0, 12)}
        {card.version.amendments.length > 0
          ? ` · ${card.version.amendments.join(", ")}`
          : ""}
        <p className="font-bold">{t(I18nKey.SLIP$DISCLAIMER)}</p>
      </footer>
    </div>
  );
}
