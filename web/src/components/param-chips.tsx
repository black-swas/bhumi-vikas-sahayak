import { Pencil } from "lucide-react";
import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import type { ChipKey, ChipValue } from "#/lib/chips";
import { formatNumber } from "#/lib/format";
import { cn } from "#/utils/utils";

const LABEL: Record<ChipKey, I18nKey> = {
  plot_area_sqm: I18nKey.CHIP$PLOT,
  road_width_m: I18nKey.CHIP$ROAD,
  height_m: I18nKey.CHIP$HEIGHT,
  building_type: I18nKey.CHIP$TYPE,
  use: I18nKey.CHIP$USE,
};

const TYPE_OPTIONS: [string, I18nKey][] = [
  ["detached", I18nKey.TYPE$DETACHED],
  ["semi_detached", I18nKey.TYPE$SEMI_DETACHED],
  ["row", I18nKey.TYPE$ROW],
];

const USE_OPTIONS: [string, I18nKey][] = [
  ["residential", I18nKey.USE$RESIDENTIAL],
  ["commercial", I18nKey.USE$COMMERCIAL],
  ["shop_cum_residence", I18nKey.USE$SHOP_CUM_RESIDENCE],
  ["public", I18nKey.USE$PUBLIC],
  ["industrial", I18nKey.USE$INDUSTRIAL],
];

const SELECT_OPTIONS: Partial<Record<ChipKey, [string, I18nKey][]>> = {
  building_type: TYPE_OPTIONS,
  use: USE_OPTIONS,
};

const UNIT: Partial<Record<ChipKey, I18nKey>> = {
  plot_area_sqm: I18nKey.CHIP$UNIT_SQM,
  road_width_m: I18nKey.CHIP$UNIT_M,
  height_m: I18nKey.CHIP$UNIT_M,
};

interface ParamChipsProps {
  chips: ChipValue[];
  disabled?: boolean;
  onEdit: (key: ChipKey, value: string | number) => void;
}

/** The inputs behind an answer. Selecting one edits it and re-runs the calculators. */
export function ParamChips({
  chips,
  disabled = false,
  onEdit,
}: ParamChipsProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = React.useState<ChipKey | null>(null);
  const [draft, setDraft] = React.useState("");

  if (chips.length === 0) return null;

  const displayValue = (chip: ChipValue): string => {
    if (chip.value === null) {
      return chip.key === "height_m"
        ? t(I18nKey.CHIP$HEIGHT_ASSUMED)
        : t(I18nKey.CHIP$NOT_GIVEN);
    }
    const options = SELECT_OPTIONS[chip.key];
    if (options) {
      const hit = options.find(([v]) => v === chip.value);
      return hit ? t(hit[1]) : String(chip.value);
    }
    const unit = UNIT[chip.key];
    const n =
      typeof chip.value === "number" ? formatNumber(chip.value) : chip.value;
    return unit ? `${n} ${t(unit)}` : String(n);
  };

  const begin = (chip: ChipValue) => {
    setEditing(chip.key);
    setDraft(chip.value === null ? "" : String(chip.value));
  };

  // Escape cancels the edit without also closing the evidence panel.
  const cancelOnEscape = (e: React.KeyboardEvent) => {
    if (e.key !== "Escape") return;
    e.stopPropagation();
    e.nativeEvent.stopImmediatePropagation();
    setEditing(null);
  };

  const commit = (chip: ChipValue) => {
    const text = draft.trim();
    setEditing(null);
    if (text === "") return;
    if (SELECT_OPTIONS[chip.key]) {
      onEdit(chip.key, text);
      return;
    }
    const n = Number(text);
    if (Number.isFinite(n) && n > 0) onEdit(chip.key, n);
  };

  return (
    <div data-testid="param-chips" className="flex flex-col gap-2">
      <span className="text-sm text-text-secondary">
        {t(I18nKey.CARD$INPUTS)}
      </span>
      <ul className="flex flex-wrap gap-2">
        {chips.map((chip) => {
          const label = t(LABEL[chip.key]);
          const options = SELECT_OPTIONS[chip.key];
          if (editing === chip.key) {
            return (
              <li key={chip.key}>
                <form
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    commit(chip);
                  }}
                >
                  <label className="flex items-center gap-2 text-sm text-text-secondary">
                    {label}
                    {options ? (
                      <select
                        // eslint-disable-next-line jsx-a11y/no-autofocus
                        autoFocus
                        value={draft}
                        onChange={(e) => {
                          // choosing an option is the edit: recompute at once
                          setEditing(null);
                          onEdit(chip.key, e.target.value);
                        }}
                        onKeyDown={cancelOnEscape}
                        className="rounded-md border border-border-input bg-base-secondary px-2 py-1 text-contrast"
                      >
                        <option value="" disabled>
                          {t(I18nKey.CHIP$NOT_GIVEN)}
                        </option>
                        {options.map(([value, key]) => (
                          <option key={value} value={value}>
                            {t(key)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        // eslint-disable-next-line jsx-a11y/no-autofocus
                        autoFocus
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="any"
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={cancelOnEscape}
                        className="w-28 rounded-md border border-border-input bg-base-secondary px-2 py-1 text-contrast"
                      />
                    )}
                  </label>
                  <button
                    type="submit"
                    className="min-h-9 rounded-md bg-primary px-3 py-1 text-sm font-semibold text-on-primary"
                  >
                    {t(I18nKey.CHIP$SAVE)}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(null)}
                    className="min-h-9 rounded-md px-2 py-1 text-sm text-text-secondary underline"
                  >
                    {t(I18nKey.CHIP$CANCEL)}
                  </button>
                </form>
              </li>
            );
          }
          return (
            <li key={chip.key}>
              <button
                type="button"
                disabled={disabled}
                data-testid={`chip-${chip.key}`}
                aria-label={t(I18nKey.CHIP$EDIT, { name: label })}
                onClick={() => begin(chip)}
                className={cn(
                  "inline-flex min-h-11 items-center gap-2 rounded-lg border border-border-input bg-surface px-3 py-1.5 text-start text-sm",
                  "hover:bg-surface-raised disabled:cursor-wait disabled:opacity-60",
                )}
              >
                <span className="text-text-secondary">{label}:</span>
                <span className="font-semibold text-contrast">
                  {displayValue(chip)}
                </span>
                {chip.assumed && chip.value !== null ? (
                  <span className="rounded bg-amber-100 px-1.5 text-xs font-semibold text-amber-950">
                    {t(I18nKey.CHIP$ASSUMED)}
                  </span>
                ) : null}
                <Pencil className="size-3.5 text-text-dim" aria-hidden />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
