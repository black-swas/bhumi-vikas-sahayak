import React from "react";
import { api, ApiError } from "#/api/client";
import { useThreadStore, type TurnError } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";

function errorKind(error: unknown): TurnError {
  if (error instanceof ApiError) {
    if (error.status === 429) return "rate_limit";
    if (error.status === 0) return "network";
  }
  return "generic";
}

/** Asking a question, and re-running the calculators on edited inputs (no model call). */
export function useAsk() {
  const ask = React.useCallback(
    async (question: string): Promise<string | null> => {
      const text = question.trim();
      if (!text) return null;
      const { addTurn, updateTurn } = useThreadStore.getState();
      const id = addTurn(text);
      useUiStore.getState().selectTurn(id);
      try {
        const card = await api.ask({ question: text });
        updateTurn(id, { state: "done", card });
      } catch (error) {
        updateTurn(id, { state: "error", error: errorKind(error) });
      }
      return id;
    },
    [],
  );

  const recompute = React.useCallback(
    async (
      turnId: string,
      override: Record<string, unknown>,
    ): Promise<void> => {
      const { turns, updateTurn } = useThreadStore.getState();
      const turn = turns.find((t) => t.id === turnId);
      if (!turn?.card) return;
      // The card stays on screen while the calculators run again.
      updateTurn(turnId, { state: "pending", recomputeError: false });
      const started = performance.now();
      try {
        const card = await api.ask({
          question: turn.question,
          lang: turn.card.lang,
          params_override: override,
        });
        updateTurn(turnId, {
          state: "done",
          card,
          recomputeMs: Math.max(1, Math.round(performance.now() - started)),
        });
      } catch {
        updateTurn(turnId, { state: "done", recomputeError: true });
      }
    },
    [],
  );

  return { ask, recompute };
}
