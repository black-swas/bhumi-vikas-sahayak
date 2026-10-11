import {
  CircleAlert,
  CircleCheck,
  CircleX,
  SearchX,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Status } from "#/api/types";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";

const STATUS_STYLE: Record<
  Status,
  { key: I18nKey; icon: typeof CircleCheck; className: string }
> = {
  ANSWERED: {
    key: I18nKey.STATUS$ANSWERED,
    icon: CircleCheck,
    className:
      "border-emerald-700 bg-emerald-100 text-emerald-950 dark:border-emerald-500 dark:bg-emerald-950 dark:text-emerald-100",
  },
  PARTIAL: {
    key: I18nKey.STATUS$PARTIAL,
    icon: CircleAlert,
    className:
      "border-amber-700 bg-amber-100 text-amber-950 dark:border-amber-500 dark:bg-amber-950 dark:text-amber-100",
  },
  NOT_FOUND: {
    key: I18nKey.STATUS$NOT_FOUND,
    icon: SearchX,
    className:
      "border-gray-600 bg-gray-100 text-gray-900 dark:border-gray-400 dark:bg-gray-800 dark:text-gray-100",
  },
  NEEDS_REVIEW: {
    key: I18nKey.STATUS$NEEDS_REVIEW,
    icon: TriangleAlert,
    className:
      "border-orange-700 bg-orange-100 text-orange-950 dark:border-orange-500 dark:bg-orange-950 dark:text-orange-100",
  },
  ERROR: {
    key: I18nKey.STATUS$ERROR,
    icon: CircleX,
    className:
      "border-red-700 bg-red-100 text-red-950 dark:border-red-500 dark:bg-red-950 dark:text-red-100",
  },
};

/** Status as icon + word + colour, never colour alone. */
export function StatusBadge({
  status,
  className,
}: {
  status: Status;
  className?: string;
}) {
  const { t } = useTranslation();
  const { key, icon: Icon, className: tone } = STATUS_STYLE[status];
  return (
    <span
      data-testid="status-badge"
      data-status={status}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold",
        tone,
        className,
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      {t(key)}
    </span>
  );
}
