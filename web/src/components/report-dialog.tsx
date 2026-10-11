import React from "react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { api } from "#/api/client";
import type { AnswerCard, FeedbackReason } from "#/api/types";
import { ModalBackdrop } from "#/components/shared/modals/modal-backdrop";
import { ModalBody } from "#/components/shared/modals/modal-body";
import { ModalCloseButton } from "#/components/shared/modals/modal-close-button";
import { I18nKey } from "#/i18n/declaration";

const REASONS: [FeedbackReason, I18nKey][] = [
  ["wrong_number", I18nKey.REPORT$REASON_WRONG_NUMBER],
  ["wrong_rule", I18nKey.REPORT$REASON_WRONG_RULE],
  ["rule_not_found", I18nKey.REPORT$REASON_RULE_NOT_FOUND],
  ["bad_hindi", I18nKey.REPORT$REASON_BAD_HINDI],
  ["unclear", I18nKey.REPORT$REASON_UNCLEAR],
  ["other", I18nKey.REPORT$REASON_OTHER],
];

const NOTE_MAX = 300;

interface ReportDialogProps {
  card: AnswerCard;
  onClose: () => void;
}

/** "Report this answer": a reason, an optional note and an explicit consent line. */
export function ReportDialog({ card, onClose }: ReportDialogProps) {
  const { t } = useTranslation();
  const [reason, setReason] = React.useState<FeedbackReason>("wrong_number");
  const [note, setNote] = React.useState("");
  const [consent, setConsent] = React.useState(false);
  const [sending, setSending] = React.useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!consent || sending) return;
    setSending(true);
    try {
      const ack = await api.feedback({
        request_id: card.request_id,
        reason,
        note: note.slice(0, NOTE_MAX),
        question: card.question,
        consent: true,
      });
      toast.success(t(I18nKey.REPORT$SENT, { id: ack.ack_id }));
      onClose();
    } catch {
      toast.error(t(I18nKey.REPORT$FAILED));
      setSending(false);
    }
  };

  return (
    <ModalBackdrop onClose={onClose} aria-label={t(I18nKey.REPORT$TITLE)}>
      <ModalBody width="md" className="max-w-[92vw] items-stretch">
        <ModalCloseButton onClose={onClose} />
        <h2 className="text-xl font-semibold text-contrast">
          {t(I18nKey.REPORT$TITLE)}
        </h2>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium text-text-secondary">
              {t(I18nKey.REPORT$REASON)}
            </legend>
            {REASONS.map(([value, key]) => (
              <label
                key={value}
                className="flex min-h-9 items-center gap-2 text-contrast"
              >
                <input
                  type="radio"
                  name="reason"
                  value={value}
                  checked={reason === value}
                  onChange={() => setReason(value)}
                />
                {t(key)}
              </label>
            ))}
          </fieldset>
          <label className="flex flex-col gap-1 text-sm text-text-secondary">
            {t(I18nKey.REPORT$NOTE)}
            <textarea
              value={note}
              maxLength={NOTE_MAX}
              rows={3}
              onChange={(e) => setNote(e.target.value)}
              className="rounded-md border border-border-input bg-surface p-2 text-base text-contrast"
            />
          </label>
          <label className="flex items-start gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1"
            />
            {t(I18nKey.REPORT$CONSENT)}
          </label>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="min-h-10 rounded-md px-4 py-2 text-text-secondary underline"
            >
              {t(I18nKey.BUTTON$CANCEL)}
            </button>
            <button
              type="submit"
              disabled={!consent || sending}
              className="min-h-10 rounded-md bg-primary px-4 py-2 font-semibold text-on-primary disabled:opacity-50"
            >
              {t(I18nKey.REPORT$SEND)}
            </button>
          </div>
        </form>
      </ModalBody>
    </ModalBackdrop>
  );
}
