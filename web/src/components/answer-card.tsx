import { Printer, TriangleAlert } from "lucide-react";
import React from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import type { AnswerCard as AnswerCardData, CardWarning } from "#/api/types";
import { CitationItem } from "#/components/citation-item";
import { ParamChips } from "#/components/param-chips";
import { ReportDialog } from "#/components/report-dialog";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { NavigationLink } from "#/components/shared/navigation-link";
import { StatusBadge } from "#/components/status-badge";
import { I18nKey } from "#/i18n/declaration";
import { chipsFor, overrideFor, type ChipKey } from "#/lib/chips";
import { ruleFromChunkId } from "#/lib/format";
import { useThreadStore, type Turn } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";
import { cn } from "#/utils/utils";
import { useAsk } from "#/hooks/use-ask";
import { useNavigation } from "#/context/navigation-context";

const INITIAL_SOURCES = 3;
const LINK_BUTTON =
  "min-h-10 rounded-md border border-border-input bg-surface px-3 py-2 text-sm font-medium text-contrast hover:bg-surface-raised";

function WarningLine({ warning }: { warning: CardWarning }) {
  const tone =
    warning.type === "amendment" || warning.type === "dp_precedence"
      ? "border-amber-600 bg-amber-50 text-amber-950 dark:bg-amber-950 dark:text-amber-100"
      : "border-border-input bg-surface text-text-secondary";
  return (
    <li
      data-testid={`warning-${warning.type}`}
      className={cn(
        "flex items-start gap-2 rounded-lg border p-3 text-sm",
        tone,
      )}
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span lang={warning.type === "calculation" ? "en" : undefined}>
        {warning.text}
      </span>
    </li>
  );
}

function latencyLine(card: AnswerCardData, turn: Turn, t: TFunction) {
  const seconds = (card.meta.latency_ms ?? 0) / 1000;
  const parts = [t(I18nKey.CARD$ANSWERED_IN, { seconds: seconds.toFixed(1) })];
  const modelTime = Object.values(card.meta.model_time_s ?? {}).reduce(
    (a, b) => a + b,
    0,
  );
  parts.push(
    card.meta.calls > 0
      ? t(I18nKey.CARD$MODEL_TIME, { seconds: modelTime.toFixed(1) })
      : t(I18nKey.CARD$NO_MODEL_CALL),
  );
  if (turn.recomputeMs !== undefined) {
    parts.push(t(I18nKey.CARD$RECOMPUTED, { ms: turn.recomputeMs }));
  }
  return parts.join(" · ");
}

interface AnswerCardProps {
  turn: Turn;
}

/** One question's answer: status, answer text, editable inputs, notices, verified sources. */
export function AnswerCard({ turn }: AnswerCardProps) {
  const { t } = useTranslation();
  const { navigate } = useNavigation();
  const { recompute } = useAsk();
  const selectTurn = useUiStore((s) => s.selectTurn);
  const setTab = useUiStore((s) => s.setTab);
  const openRule = useUiStore((s) => s.openRule);
  const [reporting, setReporting] = React.useState(false);
  const [showAll, setShowAll] = React.useState(false);
  const recomputing = useThreadStore(
    (s) => s.turns.find((x) => x.id === turn.id)?.state === "pending",
  );

  if (turn.state === "pending" && !turn.card) {
    return (
      <div
        role="status"
        className="flex items-center gap-3 text-text-secondary"
      >
        <LoadingSpinner size="small" />
        {t(I18nKey.ASK$WORKING)}
      </div>
    );
  }
  if (turn.state === "error" || !turn.card) {
    const key =
      turn.error === "rate_limit"
        ? I18nKey.ASK$ERROR_RATE_LIMIT
        : turn.error === "network"
          ? I18nKey.ASK$ERROR_NETWORK
          : I18nKey.ASK$ERROR_GENERIC;
    return (
      <div
        role="alert"
        data-testid="turn-error"
        className="text-red-800 dark:text-red-300"
      >
        {t(key)}
      </div>
    );
  }

  const { card } = turn;
  const chips = chipsFor(card);
  const assumptions = card.calculations.flatMap((c) => c.assumptions);
  const partialCount = new Set(assumptions).size + card.missing_info.length;
  const shownSources = showAll
    ? card.citations
    : card.citations.slice(0, INITIAL_SOURCES);
  const hasEvidence = card.citations.length > 0 || card.calculations.length > 0;
  const showCandidates =
    card.status === "NEEDS_REVIEW" && card.candidates.length > 0;
  const candidateRules = [
    ...new Set(
      card.candidates
        .map(ruleFromChunkId)
        .filter((r): r is string => r !== null),
    ),
  ];

  const onEdit = (key: ChipKey, value: string | number) => {
    void recompute(turn.id, overrideFor(card, chips, key, value));
  };

  return (
    <article
      data-testid="answer-card"
      data-status={card.status}
      lang={card.lang}
      className="flex flex-col gap-4 rounded-xl border border-border bg-base-secondary p-4"
    >
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <div role="status" aria-live="polite">
          <StatusBadge status={card.status} />
        </div>
        {card.status === "PARTIAL" && partialCount > 0 ? (
          <span className="text-sm text-text-secondary">
            {t(
              partialCount === 1
                ? I18nKey.STATUS$PARTIAL_DETAIL_ONE
                : I18nKey.STATUS$PARTIAL_DETAIL_OTHER,
              { count: partialCount },
            )}
          </span>
        ) : null}
        <span className="ms-auto text-sm text-text-dim" data-testid="latency">
          {latencyLine(card, turn, t)}
        </span>
      </header>

      {card.answer ? (
        <p
          data-testid="answer-text"
          className="whitespace-pre-line text-lg leading-relaxed text-contrast"
        >
          {card.answer}
        </p>
      ) : card.status === "NEEDS_REVIEW" &&
        !card.warnings.some((w) => w.type === "verification_failed") ? (
        <p className="text-lg text-contrast">
          {t(I18nKey.CARD$NO_ANSWER_TEXT)}
        </p>
      ) : null}

      {turn.recomputeError ? (
        <p role="alert" className="text-sm text-red-800 dark:text-red-300">
          {t(I18nKey.ASK$ERROR_RECOMPUTE)}
        </p>
      ) : null}

      <ParamChips chips={chips} disabled={recomputing} onEdit={onEdit} />

      {card.missing_info.length > 0 ? (
        <div data-testid="missing-info" className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold text-contrast">
            {t(I18nKey.CARD$MISSING)}
          </h3>
          <ul className="list-disc ps-5 text-text-secondary">
            {card.missing_info.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {card.warnings.length > 0 ? (
        <section aria-label={t(I18nKey.CARD$WARNINGS)}>
          <ul className="flex flex-col gap-2">
            {card.warnings.map((w) => (
              <WarningLine key={`${w.type}-${w.id ?? w.text}`} warning={w} />
            ))}
          </ul>
        </section>
      ) : null}

      {card.citations.length > 0 ? (
        <section
          className="flex flex-col gap-2"
          aria-label={t(I18nKey.CARD$SOURCES)}
        >
          <h3 className="text-sm font-semibold text-contrast">
            {t(I18nKey.CARD$SOURCES)}
          </h3>
          <ul className="flex flex-col gap-2">
            {shownSources.map((c) => (
              <CitationItem
                key={`${c.chunk_id}-${c.quote}`}
                citation={c}
                turnId={turn.id}
              />
            ))}
          </ul>
          {card.citations.length > INITIAL_SOURCES ? (
            <button
              type="button"
              className="self-start text-sm text-text-secondary underline"
              onClick={() => setShowAll((v) => !v)}
            >
              {showAll
                ? t(I18nKey.CARD$SHOW_LESS)
                : t(I18nKey.CARD$SHOW_ALL, { count: card.citations.length })}
            </button>
          ) : null}
        </section>
      ) : null}

      {showCandidates ? (
        <section className="flex flex-col gap-2" data-testid="candidates">
          <h3 className="text-sm font-semibold text-contrast">
            {t(I18nKey.CARD$CANDIDATES)}
          </h3>
          <ul className="flex flex-wrap gap-2">
            {candidateRules.map((rule) => (
              <li key={rule}>
                <button
                  type="button"
                  className={LINK_BUTTON}
                  onClick={() => openRule(turn.id, { rule })}
                >
                  {t(I18nKey.CARD$OPEN_RULE, { rule })}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <footer className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3">
        {hasEvidence ? (
          <>
            <button
              type="button"
              className={LINK_BUTTON}
              onClick={() => {
                selectTurn(turn.id);
                setTab("sources");
              }}
            >
              {t(I18nKey.CARD$SHOW_EVIDENCE)}
            </button>
            <button
              type="button"
              className={LINK_BUTTON}
              onClick={() => {
                selectTurn(turn.id);
                setTab("working");
              }}
            >
              {t(I18nKey.CARD$SHOW_WORKING)}
            </button>
          </>
        ) : null}
        <button
          type="button"
          className={cn(LINK_BUTTON, "inline-flex items-center gap-2")}
          onClick={() => navigate(`/slip/${turn.id}`)}
        >
          <Printer className="size-4" aria-hidden />
          {t(I18nKey.CARD$PRINT_SLIP)}
        </button>
        <button
          type="button"
          className={LINK_BUTTON}
          onClick={() => setReporting(true)}
        >
          {t(I18nKey.CARD$REPORT)}
        </button>
        <span className="ms-auto flex gap-4 text-sm">
          <NavigationLink
            to="/limits"
            className="text-text-secondary underline"
          >
            {t(I18nKey.CARD$LIMITS_LINK)}
          </NavigationLink>
          <NavigationLink
            to="/limits#escalate"
            className="text-text-secondary underline"
          >
            {t(I18nKey.CARD$ESCALATE_LINK)}
          </NavigationLink>
        </span>
      </footer>

      {reporting ? (
        <ReportDialog card={card} onClose={() => setReporting(false)} />
      ) : null}
    </article>
  );
}
