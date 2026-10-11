import { useQuery } from "@tanstack/react-query";
import { ExternalLink, PanelRightClose } from "lucide-react";
import React from "react";
import { useTranslation } from "react-i18next";
import { api } from "#/api/client";
import type { AnswerCard, CalculationResult } from "#/api/types";
import { CitationItem } from "#/components/citation-item";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { I18nKey } from "#/i18n/declaration";
import { formatNumber, formatResult, splitAtQuote } from "#/lib/format";
import { turnById, useThreadStore } from "#/stores/thread-store";
import { useUiStore, type EvidenceTab } from "#/stores/ui-store";
import { buildAppPath } from "#/utils/base-path";
import { cn } from "#/utils/utils";

const TABS: [EvidenceTab, I18nKey][] = [
  ["sources", I18nKey.TAB$SOURCES],
  ["working", I18nKey.TAB$WORKING],
  ["rule", I18nKey.TAB$RULE],
  ["pdf", I18nKey.TAB$PDF],
  ["details", I18nKey.TAB$DETAILS],
];

const CALC_NAME: Record<string, I18nKey> = {
  front_open_space: I18nKey.CALC$FRONT_OPEN_SPACE,
  rear_open_space: I18nKey.CALC$REAR_OPEN_SPACE,
  plot_types: I18nKey.CALC$PLOT_TYPES,
  side_open_space: I18nKey.CALC$SIDE_OPEN_SPACE,
  max_built_up: I18nKey.CALC$MAX_BUILT_UP,
  application_fee: I18nKey.CALC$APPLICATION_FEE,
  permission_fee: I18nKey.CALC$PERMISSION_FEE,
  instant_approval_threshold: I18nKey.CALC$INSTANT_APPROVAL,
  electric_line_clearance: I18nKey.CALC$ELECTRIC_LINE,
  high_rise_norms: I18nKey.CALC$HIGH_RISE,
  farm_house: I18nKey.CALC$FARM_HOUSE,
  permission_validity: I18nKey.CALC$PERMISSION_VALIDITY,
};

const INPUT_NAME: Record<string, I18nKey> = {
  plot_area_sqm: I18nKey.INPUT$PLOT_AREA_SQM,
  road_width_m: I18nKey.INPUT$ROAD_WIDTH_M,
  height_m: I18nKey.INPUT$HEIGHT_M,
  built_up_area_sqm: I18nKey.INPUT$BUILT_UP_AREA_SQM,
  frontage_m: I18nKey.INPUT$FRONTAGE_M,
  use: I18nKey.INPUT$USE,
  building_type: I18nKey.INPUT$BUILDING_TYPE,
  voltage: I18nKey.INPUT$VOLTAGE,
  high_rise: I18nKey.INPUT$HIGH_RISE,
  grant_date: I18nKey.INPUT$GRANT_DATE,
  grant_year: I18nKey.INPUT$GRANT_YEAR,
  commercial_category: I18nKey.INPUT$COMMERCIAL_CATEGORY,
  cinema_seats: I18nKey.INPUT$CINEMA_SEATS,
};

const PDF_LANGS = ["en", "hi"] as const;

const SOURCE_BUTTON =
  "min-h-9 rounded-md border border-border-input bg-surface px-3 py-1 text-sm font-medium text-contrast hover:bg-surface-raised";

function Empty({ text }: { text: string }) {
  return <p className="text-text-secondary">{text}</p>;
}

function SourcesTab({ card, turnId }: { card: AnswerCard; turnId: string }) {
  const { t } = useTranslation();
  if (card.citations.length === 0)
    return <Empty text={t(I18nKey.PANEL$NO_SOURCES)} />;
  return (
    <ul className="flex flex-col gap-3">
      {card.citations.map((c) => (
        <CitationItem
          key={`${c.chunk_id}-${c.quote}`}
          citation={c}
          turnId={turnId}
        />
      ))}
    </ul>
  );
}

function CalcBlock({ calc }: { calc: CalculationResult }) {
  const { t } = useTranslation();
  const details = (calc.details ?? {}) as Record<string, unknown>;
  const result = formatResult(calc.result, details.display);
  const name = CALC_NAME[calc.calc_id];
  const inputs = Object.entries(calc.inputs as Record<string, unknown>);
  return (
    <li
      data-testid="working-calc"
      className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface p-3"
    >
      <h4 className="font-semibold text-contrast">
        {name ? t(name) : calc.calc_id}
      </h4>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-text-secondary">{t(I18nKey.WORKING$INPUTS)}</dt>
        <dd className="text-contrast">
          {inputs.length === 0
            ? t(I18nKey.COMMON$DASH)
            : inputs
                .map(([k, v]) => {
                  const label = INPUT_NAME[k] ? t(INPUT_NAME[k]) : k;
                  return `${label}: ${typeof v === "number" ? formatNumber(v) : String(v)}`;
                })
                .join(" · ")}
        </dd>
        {calc.matched_row_text ? (
          <>
            <dt className="text-text-secondary">
              {t(I18nKey.WORKING$MATCHED_ROW)}
            </dt>
            <dd
              lang="en"
              className="font-mono text-contrast [overflow-wrap:anywhere]"
            >
              {calc.matched_row_text}
            </dd>
          </>
        ) : null}
        <dt className="text-text-secondary">{t(I18nKey.WORKING$RESULT)}</dt>
        <dd className="font-semibold text-contrast">
          {result ?? t(I18nKey.WORKING$NO_VALUE)}
        </dd>
      </dl>
      <p className="text-xs text-text-dim">
        {t(I18nKey.WORKING$SOURCE, {
          rule: calc.rule,
          sub: calc.sub_rule,
          page: calc.page,
        })}
      </p>
      {calc.assumptions.length > 0 ? (
        <div className="rounded-md border border-amber-600 bg-amber-50 p-2 text-sm text-amber-950 dark:bg-amber-950 dark:text-amber-100">
          <strong>{t(I18nKey.CARD$ASSUMPTIONS)}:</strong>
          <ul className="list-disc ps-5">
            {calc.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}

function WorkingTab({ card }: { card: AnswerCard }) {
  const { t } = useTranslation();
  if (card.calculations.length === 0)
    return <Empty text={t(I18nKey.PANEL$NO_WORKING)} />;
  return (
    <ul className="flex flex-col gap-3">
      {card.calculations.map((c, i) => (
        <CalcBlock key={`${c.calc_id}-${i}`} calc={c} />
      ))}
    </ul>
  );
}

function RuleTab({ turnId }: { turnId: string }) {
  const { t } = useTranslation();
  const target = useUiStore((s) => s.ruleTarget);
  const openPdf = useUiStore((s) => s.openPdf);
  const query = useQuery({
    queryKey: ["rule", target?.rule],
    queryFn: () => api.rule(target?.rule ?? ""),
    enabled: Boolean(target),
    staleTime: Infinity,
    retry: false,
  });
  if (!target) return <Empty text={t(I18nKey.PANEL$NO_RULE)} />;
  if (query.isPending) {
    return (
      <div
        role="status"
        className="flex items-center gap-2 text-text-secondary"
      >
        <LoadingSpinner size="small" />
        {t(I18nKey.PANEL$RULE_LOADING)}
      </div>
    );
  }
  if (query.isError) return <Empty text={t(I18nKey.PANEL$RULE_ERROR)} />;
  const rule = query.data;
  const parts = splitAtQuote(rule.text, target.quote);
  return (
    <div className="flex flex-col gap-3" data-testid="rule-tab">
      <h4 className="text-lg font-semibold text-contrast">
        {t(I18nKey.RULE$TITLE, { rule: rule.rule })} · {rule.title}
      </h4>
      <p className="text-sm text-text-secondary">
        {t(I18nKey.PANEL$RULE_PAGES, {
          start: rule.page_start,
          end: rule.page_end,
        })}
        {rule.parent
          ? ` · ${t(I18nKey.RULE$INSERTED_IN, { parent: rule.parent })}`
          : ""}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className={SOURCE_BUTTON}
          onClick={() => openPdf(turnId, { lang: "en", page: rule.page_start })}
        >
          {t(I18nKey.CARD$PDF_EN, { page: rule.page_start })}
        </button>
        <button
          type="button"
          className={SOURCE_BUTTON}
          onClick={() => openPdf(turnId, { lang: "hi", page: rule.page_start })}
        >
          {t(I18nKey.CARD$PDF_HI, { page: rule.page_start })}
        </button>
      </div>
      {/* Official text, shown as plain text; the verified quote is highlighted inside it. */}
      <pre
        lang="en"
        className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border border-border-subtle bg-surface p-3 font-sans text-sm text-contrast"
      >
        {parts ? (
          <>
            {parts[0]}
            <mark className="bg-amber-200 text-amber-950">{parts[1]}</mark>
            {parts[2]}
          </>
        ) : (
          rule.text
        )}
      </pre>
    </div>
  );
}

function PdfTab() {
  const { t } = useTranslation();
  const pdf = useUiStore((s) => s.pdf);
  const setPdf = useUiStore((s) => s.setPdf);
  if (!pdf) return <Empty text={t(I18nKey.PANEL$NO_PDF)} />;
  const src = buildAppPath(`/pdf/rules-${pdf.lang}.pdf#page=${pdf.page}`);
  return (
    <div
      className="flex h-full min-h-[60vh] flex-col gap-2"
      data-testid="pdf-tab"
    >
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="group"
          aria-label={t(I18nKey.PANEL$PDF_LANGUAGE)}
          className="flex gap-1"
        >
          {PDF_LANGS.map((lang) => (
            <button
              key={lang}
              type="button"
              aria-pressed={pdf.lang === lang}
              onClick={() => setPdf({ ...pdf, lang })}
              className={cn(
                SOURCE_BUTTON,
                pdf.lang === lang &&
                  "border-primary bg-primary text-on-primary",
              )}
            >
              {t(lang === "en" ? I18nKey.PANEL$PDF_EN : I18nKey.PANEL$PDF_HI)}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1 text-sm text-text-secondary">
          {t(I18nKey.PANEL$PDF_PAGE)}
          <input
            type="number"
            min={1}
            max={108}
            value={pdf.page}
            onChange={(e) => {
              const n = Math.round(Number(e.target.value));
              if (n >= 1 && n <= 108) setPdf({ ...pdf, page: n });
            }}
            className="w-20 rounded-md border border-border-input bg-surface px-2 py-1 text-contrast"
          />
        </label>
        <a
          href={src}
          target="_blank"
          rel="noopener noreferrer"
          className="ms-auto inline-flex items-center gap-1 text-sm text-text-secondary underline"
        >
          {t(I18nKey.PANEL$PDF_OPEN_NEW)}
          <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </div>
      {/* A hash-only change does not reload the viewer, so the frame is keyed by page. */}
      <iframe
        key={`${pdf.lang}-${pdf.page}`}
        src={src}
        title={t(I18nKey.PANEL$PDF_FRAME_TITLE)}
        className="min-h-[60vh] w-full flex-1 rounded-lg border border-border-subtle bg-white"
      />
    </div>
  );
}

function DetailsTab({ card }: { card: AnswerCard }) {
  const { t } = useTranslation();
  const m = card.meta;
  const modelTime = Object.entries(m.model_time_s ?? {});
  const rows: [string, React.ReactNode][] = [
    [
      t(I18nKey.DETAILS$LATENCY),
      `${((m.latency_ms ?? 0) / 1000).toFixed(2)} s`,
    ],
    [
      t(I18nKey.DETAILS$MODEL_TIME),
      modelTime.length === 0
        ? t(I18nKey.CARD$NO_MODEL_CALL)
        : modelTime
            .map(
              ([step, s]) =>
                `${t(step === "A" ? I18nKey.DETAILS$STEP_A : I18nKey.DETAILS$STEP_B)}: ${s.toFixed(2)} s`,
            )
            .join(" · "),
    ],
    [t(I18nKey.DETAILS$CALLS), String(m.calls)],
    [
      t(I18nKey.DETAILS$MODELS),
      Object.entries(m.models ?? {})
        .map(([step, name]) => `${step}: ${name}`)
        .join(" · ") || t(I18nKey.COMMON$DASH),
    ],
    [
      t(I18nKey.DETAILS$PROVIDERS),
      Object.entries(m.providers ?? {})
        .map(([step, name]) => `${step}: ${name}`)
        .join(" · ") || t(I18nKey.COMMON$DASH),
    ],
    [
      t(I18nKey.DETAILS$TOKENS),
      t(I18nKey.DETAILS$TOKENS_FORMAT, {
        input: m.tokens?.input ?? 0,
        output: m.tokens?.output ?? 0,
        cached: m.tokens?.cached ?? 0,
      }),
    ],
    [
      t(I18nKey.DETAILS$REPLAY),
      t(m.replay ? I18nKey.DETAILS$YES : I18nKey.DETAILS$NO),
    ],
    [t(I18nKey.DETAILS$CORPUS), card.version.corpus_sha256.slice(0, 12)],
    [t(I18nKey.DETAILS$REQUEST), card.request_id],
  ];
  return (
    <dl
      data-testid="details-tab"
      className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm"
    >
      {rows.map(([k, v]) => (
        <React.Fragment key={k}>
          <dt className="text-text-secondary">{k}</dt>
          <dd className="text-contrast [overflow-wrap:anywhere]">{v}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

/** Sources, Working, Rule, PDF and Details for the selected answer. */
export function EvidencePanel({ onCollapse }: { onCollapse?: () => void }) {
  const { t } = useTranslation();
  const tab = useUiStore((s) => s.tab);
  const setTab = useUiStore((s) => s.setTab);
  const activeId = useUiStore((s) => s.activeTurnId);
  const turn = useThreadStore((s) => turnById(s.turns, activeId));
  const card = turn?.card;

  // Arrow keys move between tabs (WAI-ARIA tabs pattern); focus follows the selection.
  const onTabKeyDown = (e: React.KeyboardEvent) => {
    const i = TABS.findIndex(([k]) => k === tab);
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    const next = TABS[(i + step + TABS.length) % TABS.length][0];
    setTab(next);
    document.getElementById(`tab-${next}`)?.focus();
  };

  return (
    <section
      aria-label={t(I18nKey.PANEL$TITLE)}
      data-testid="evidence-panel"
      className="flex h-full min-h-0 flex-col gap-3 bg-base-secondary p-3"
    >
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-contrast">
          {t(I18nKey.PANEL$TITLE)}
        </h2>
        {onCollapse ? (
          <button
            type="button"
            onClick={onCollapse}
            aria-label={t(I18nKey.PANEL$COLLAPSE)}
            className="ms-auto rounded-md p-2 text-text-secondary hover:bg-surface-raised"
          >
            <PanelRightClose className="size-5" aria-hidden />
          </button>
        ) : null}
      </div>
      <div
        role="tablist"
        aria-label={t(I18nKey.TAB$LIST_LABEL)}
        className="flex flex-wrap gap-1 border-b border-border-subtle"
      >
        {TABS.map(([key, label]) => (
          <button
            key={key}
            id={`tab-${key}`}
            type="button"
            role="tab"
            aria-selected={tab === key}
            aria-controls={`panel-${key}`}
            tabIndex={tab === key ? 0 : -1}
            onClick={() => setTab(key)}
            onKeyDown={onTabKeyDown}
            className={cn(
              "min-h-10 rounded-t-md px-3 py-2 text-sm font-medium",
              tab === key
                ? "border-b-2 border-primary bg-surface text-contrast"
                : "text-text-secondary hover:bg-surface-raised",
            )}
          >
            {t(label)}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="min-h-0 flex-1 overflow-auto"
      >
        {!turn || !card ? (
          <Empty text={t(I18nKey.PANEL$EMPTY)} />
        ) : tab === "sources" ? (
          <SourcesTab card={card} turnId={turn.id} />
        ) : tab === "working" ? (
          <WorkingTab card={card} />
        ) : tab === "rule" ? (
          <RuleTab turnId={turn.id} />
        ) : tab === "pdf" ? (
          <PdfTab />
        ) : (
          <DetailsTab card={card} />
        )}
      </div>
    </section>
  );
}
