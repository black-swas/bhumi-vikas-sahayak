import { PanelRightOpen, SendHorizontal } from "lucide-react";
import React from "react";
import { useTranslation } from "react-i18next";
import { AnswerCard } from "#/components/answer-card";
import { EvidencePanel } from "#/components/evidence-panel";
import { ResizeHandle } from "#/components/ui/resize-handle";
import { useAsk } from "#/hooks/use-ask";
import { I18nKey } from "#/i18n/declaration";
import { EXAMPLE_LABELS, EXAMPLE_QUESTIONS } from "#/lib/examples";
import { useThreadStore } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";
import { cn } from "#/utils/utils";

const MAX_QUESTION_CHARS = 500;
const KEY_RESIZE_STEP_PX = 40;

function useResize() {
  const setPanelWidth = useUiStore((s) => s.setPanelWidth);
  const [dragging, setDragging] = React.useState(false);

  React.useEffect(() => {
    if (!dragging) return undefined;
    const onMove = (e: MouseEvent) =>
      setPanelWidth(window.innerWidth - e.clientX);
    const onUp = () => setDragging(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging, setPanelWidth]);

  return { dragging, onMouseDown: () => setDragging(true) };
}

export default function AskRoute() {
  const { t } = useTranslation();
  const { ask } = useAsk();
  const turns = useThreadStore((s) => s.turns);
  const panelOpen = useUiStore((s) => s.panelOpen);
  const setPanelOpen = useUiStore((s) => s.setPanelOpen);
  const panelWidth = useUiStore((s) => s.panelWidth);
  const setPanelWidth = useUiStore((s) => s.setPanelWidth);
  const focusTick = useUiStore((s) => s.focusTick);
  const activeId = useUiStore((s) => s.activeTurnId);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [draft, setDraft] = React.useState("");
  const { dragging, onMouseDown } = useResize();
  const pending = turns.some((turn) => turn.state === "pending");

  React.useEffect(() => {
    inputRef.current?.focus();
  }, [focusTick]);

  // Esc closes the evidence panel, unless a dialog is open (the dialog closes first).
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || document.querySelector('[role="dialog"]'))
        return;
      setPanelOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setPanelOpen]);

  // Keep the newest turn in view.
  const lastId = turns.at(-1)?.id;
  React.useEffect(() => {
    if (lastId)
      document
        .getElementById(`turn-${lastId}`)
        ?.scrollIntoView?.({ block: "nearest" });
  }, [lastId, turns.length]);

  const submit = (question: string) => {
    if (!question.trim() || pending) return;
    setDraft("");
    setPanelOpen(true);
    void ask(question);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <section
        aria-label={t(I18nKey.THREAD$LABEL)}
        className="flex min-h-0 min-w-0 flex-1 flex-col"
      >
        <div
          className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-4"
          data-testid="thread"
        >
          {turns.length === 0 ? (
            <div className="mx-auto flex max-w-2xl flex-col gap-4 py-8">
              <h1 className="text-3xl font-semibold text-contrast">
                {t(I18nKey.ASK$TITLE)}
              </h1>
              <p className="text-lg text-text-secondary">
                {t(I18nKey.ASK$SUBTITLE)}
              </p>
              <div className="flex flex-col gap-2">
                <span className="text-sm text-text-secondary">
                  {t(I18nKey.ASK$EXAMPLES)}
                </span>
                <ul className="flex flex-wrap gap-2">
                  {EXAMPLE_QUESTIONS.map((question, i) => (
                    <li key={question}>
                      <button
                        type="button"
                        data-testid={`example-${i}`}
                        onClick={() => submit(question)}
                        className="min-h-11 rounded-full border border-border-input bg-surface px-4 py-2 text-start text-base text-contrast hover:bg-surface-raised"
                      >
                        {EXAMPLE_LABELS[i]}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            turns.map((turn) => (
              <div
                key={turn.id}
                id={`turn-${turn.id}`}
                data-testid="turn"
                className={cn(
                  "mx-auto flex w-full max-w-3xl flex-col gap-3 rounded-xl p-1",
                  turn.id === activeId && "ring-2 ring-primary/40",
                )}
              >
                <p className="flex gap-2 text-lg text-contrast">
                  <span className="font-semibold text-text-secondary">
                    {t(I18nKey.THREAD$YOU)}:
                  </span>
                  <span
                    data-testid="question-text"
                    className="[overflow-wrap:anywhere]"
                  >
                    {turn.question}
                  </span>
                </p>
                <AnswerCard turn={turn} />
              </div>
            ))
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(draft);
          }}
          className="flex flex-col gap-1 border-t border-border-subtle bg-surface p-3"
        >
          <div className="mx-auto flex w-full max-w-3xl items-center gap-2">
            <label htmlFor="question-input" className="sr-only">
              {t(I18nKey.ASK$INPUT_LABEL)}
            </label>
            <input
              id="question-input"
              ref={inputRef}
              type="text"
              value={draft}
              maxLength={MAX_QUESTION_CHARS}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={t(I18nKey.ASK$PLACEHOLDER)}
              autoComplete="off"
              className="min-h-12 min-w-0 flex-1 rounded-lg border border-border-input bg-base-secondary px-4 text-lg text-contrast"
            />
            <button
              type="submit"
              disabled={pending || draft.trim() === ""}
              className="inline-flex min-h-12 items-center gap-2 rounded-lg bg-primary px-5 font-semibold text-on-primary disabled:opacity-50"
            >
              <SendHorizontal className="size-5" aria-hidden />
              {t(pending ? I18nKey.ASK$WORKING : I18nKey.ASK$SUBMIT)}
            </button>
            {!panelOpen ? (
              <button
                type="button"
                onClick={() => setPanelOpen(true)}
                aria-label={t(I18nKey.PANEL$EXPAND)}
                title={t(I18nKey.PANEL$EXPAND)}
                className="inline-flex min-h-12 items-center rounded-lg border border-border-input px-3 text-text-secondary hover:bg-surface-raised"
              >
                <PanelRightOpen className="size-5" aria-hidden />
              </button>
            ) : null}
          </div>
          <p className="mx-auto w-full max-w-3xl text-sm text-text-dim">
            {t(I18nKey.ASK$PRIVACY_HINT)}
          </p>
        </form>
      </section>

      {panelOpen ? (
        <>
          <ResizeHandle
            testId="panel-resize"
            label={t(I18nKey.PANEL$RESIZE)}
            valueNow={panelWidth}
            // the panel is on the right, so a wider panel means moving the divider left
            onKeyResize={(direction) =>
              setPanelWidth(panelWidth - direction * KEY_RESIZE_STEP_PX)
            }
            onMouseDown={onMouseDown}
            isDragging={dragging}
            className="hidden md:block"
          />
          <aside
            data-testid="evidence-aside"
            style={{ ["--panel-width" as string]: `${panelWidth}px` }}
            className="max-h-[70vh] min-h-0 shrink-0 overflow-hidden border-t border-border-subtle md:max-h-none md:w-[var(--panel-width)] md:border-s md:border-t-0"
          >
            <EvidencePanel onCollapse={() => setPanelOpen(false)} />
          </aside>
        </>
      ) : null}
    </div>
  );
}
