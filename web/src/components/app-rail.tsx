import {
  Gauge,
  MessageSquarePlus,
  ScrollText,
  Search,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { LanguageToggle, ThemeToggle } from "#/components/settings-toggles";
import { ModeBadge } from "#/components/mode-badge";
import { SidebarNavLink } from "#/components/features/sidebar/sidebar-nav-link";
import {
  sidebarNavListClassName,
  SIDEBAR_HEADER_ROW_CLASS,
} from "#/components/features/sidebar/sidebar-layout";
import { useNavigation } from "#/context/navigation-context";
import { I18nKey } from "#/i18n/declaration";
import { useThreadStore } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";
import { cn } from "#/utils/utils";

/** Left rail: brand, new question, recent questions, page links, language, theme and mode. */
export function AppRail({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();
  const { navigate } = useNavigation();
  const turns = useThreadStore((s) => s.turns);
  const clear = useThreadStore((s) => s.clear);
  const activeId = useUiStore((s) => s.activeTurnId);
  const selectTurn = useUiStore((s) => s.selectTurn);
  const reset = useUiStore((s) => s.reset);
  const focusInput = useUiStore((s) => s.focusInput);
  const recent = [...turns].reverse();

  const goToTurn = (id: string) => {
    selectTurn(id);
    navigate("/");
    onNavigate?.();
    // the thread mounts after the route change, so scroll on the next frame
    requestAnimationFrame(() =>
      document
        .getElementById(`turn-${id}`)
        ?.scrollIntoView?.({ block: "start" }),
    );
  };

  return (
    <nav
      aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
      className="flex h-full min-h-0 w-full flex-col gap-3 overflow-y-auto bg-surface p-3"
    >
      <div
        className={cn(
          SIDEBAR_HEADER_ROW_CLASS,
          "h-auto min-h-10 flex-col items-start gap-0",
        )}
      >
        <span className="text-lg font-semibold text-contrast">
          {t(I18nKey.BRAND$NAME)}
        </span>
        <span className="text-xs text-text-secondary">
          {t(I18nKey.BRAND$TAGLINE)}
        </span>
      </div>

      <button
        type="button"
        data-testid="new-question"
        onClick={() => {
          reset();
          navigate("/");
          focusInput();
          onNavigate?.();
        }}
        className="flex min-h-11 items-center gap-2 rounded-lg bg-primary px-3 py-2 font-semibold text-on-primary"
      >
        <MessageSquarePlus className="size-5" aria-hidden />
        {t(I18nKey.NAV$NEW_QUESTION)}
      </button>

      <section
        aria-label={t(I18nKey.NAV$RECENT)}
        className="flex min-h-0 flex-col gap-1"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-secondary">
            {t(I18nKey.NAV$RECENT)}
          </h2>
          {recent.length > 0 ? (
            <button
              type="button"
              onClick={() => {
                clear();
                reset();
              }}
              aria-label={t(I18nKey.NAV$CLEAR_HISTORY)}
              title={t(I18nKey.NAV$CLEAR_HISTORY)}
              className="rounded-md p-1.5 text-text-secondary hover:bg-surface-raised"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          ) : null}
        </div>
        {recent.length === 0 ? (
          <p className="text-sm text-text-dim">{t(I18nKey.NAV$RECENT_EMPTY)}</p>
        ) : (
          <ul
            data-testid="recent-questions"
            className="flex max-h-56 flex-col gap-0.5 overflow-y-auto"
          >
            {recent.map((turn) => (
              <li key={turn.id}>
                <button
                  type="button"
                  onClick={() => goToTurn(turn.id)}
                  aria-current={turn.id === activeId ? "true" : undefined}
                  className={cn(
                    "block min-h-9 w-full truncate rounded-md px-2.5 py-1.5 text-start text-sm",
                    turn.id === activeId
                      ? "bg-tertiary text-contrast"
                      : "text-text-secondary hover:bg-surface-raised hover:text-contrast",
                  )}
                >
                  {turn.question}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div
        className={cn(
          sidebarNavListClassName(false),
          "mt-1 border-t border-border-subtle pt-3",
        )}
      >
        <SidebarNavLink
          to="/"
          end
          testId="nav-ask"
          label={t(I18nKey.NAV$ASK)}
          icon={<Search className="size-4.5" aria-hidden />}
        />
        <SidebarNavLink
          to="/accuracy"
          testId="nav-accuracy"
          label={t(I18nKey.NAV$ACCURACY)}
          icon={<Gauge className="size-4.5" aria-hidden />}
        />
        <SidebarNavLink
          to="/limits"
          testId="nav-limits"
          label={t(I18nKey.NAV$LIMITS)}
          icon={<ScrollText className="size-4.5" aria-hidden />}
        />
      </div>

      <div className="mt-auto flex flex-col gap-3 border-t border-border-subtle pt-3">
        <LanguageToggle />
        <ThemeToggle />
        <ModeBadge />
      </div>
    </nav>
  );
}
