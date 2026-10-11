import { CircleDot } from "lucide-react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import { useHealth } from "#/hooks/use-health";
import { cn } from "#/utils/utils";

const MODES = {
  live: {
    label: I18nKey.MODE$LIVE,
    help: I18nKey.MODE$LIVE_HELP,
    tone: "text-emerald-800 dark:text-emerald-300",
  },
  replay: {
    label: I18nKey.MODE$REPLAY,
    help: I18nKey.MODE$REPLAY_HELP,
    tone: "text-sky-800 dark:text-sky-300",
  },
  offline: {
    label: I18nKey.MODE$OFFLINE,
    help: I18nKey.MODE$OFFLINE_HELP,
    tone: "text-amber-800 dark:text-amber-300",
  },
} as const;

/** LIVE, REPLAY or OFFLINE from /api/health, or NO SERVER when it cannot be reached. */
export function ModeBadge() {
  const { t } = useTranslation();
  const { data, isError } = useHealth();
  const mode = data ? MODES[data.mode] : null;
  const label = mode
    ? t(mode.label)
    : t(isError ? I18nKey.MODE$UNKNOWN : I18nKey.COMMON$DASH);
  return (
    <p
      data-testid="mode-badge"
      data-mode={data?.mode ?? (isError ? "unreachable" : "unknown")}
      title={mode ? t(mode.help) : undefined}
      className={cn(
        "flex items-center gap-2 text-sm font-semibold",
        mode?.tone ?? "text-red-800 dark:text-red-300",
      )}
    >
      <CircleDot className="size-4" aria-hidden />
      <span className="text-text-secondary font-normal">
        {t(I18nKey.MODE$LABEL)}:
      </span>
      {label}
    </p>
  );
}

/** A banner under the top one when the API cannot be reached. */
export function UnreachableBanner() {
  const { t } = useTranslation();
  const { isError } = useHealth();
  if (!isError) return null;
  return (
    <div
      role="alert"
      data-testid="unreachable-banner"
      className="border-b border-red-700 bg-red-100 px-4 py-2 text-sm font-medium text-red-950 dark:bg-red-950 dark:text-red-100"
    >
      {t(I18nKey.MODE$UNREACHABLE)}
    </div>
  );
}
