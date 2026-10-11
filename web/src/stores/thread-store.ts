import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { AnswerCard } from "#/api/types";

export const MAX_TURNS = 20;

export type TurnError = "rate_limit" | "network" | "generic";

export interface Turn {
  id: string;
  question: string;
  askedAt: string; // ISO timestamp
  state: "pending" | "done" | "error";
  card?: AnswerCard;
  error?: TurnError;
  /** Round trip of the last parameter edit, which runs the calculators with no model call. */
  recomputeMs?: number;
  recomputeError?: boolean;
}

interface ThreadState {
  turns: Turn[];
  addTurn: (question: string) => string;
  updateTurn: (id: string, patch: Partial<Turn>) => void;
  clear: () => void;
}

let counter = 0;

function newId(): string {
  counter += 1;
  return `t${Date.now().toString(36)}${counter.toString(36)}`;
}

/**
 * The thread lives in sessionStorage, not localStorage: counter PCs are shared, so a closed tab
 * must forget the questions. It holds public rule text plus whatever the clerk typed (the UI asks
 * the clerk not to type names or ID numbers), capped at 20 turns.
 */
export const useThreadStore = create<ThreadState>()(
  persist(
    (set) => ({
      turns: [],
      addTurn: (question) => {
        const id = newId();
        const turn: Turn = {
          id,
          question,
          askedAt: new Date().toISOString(),
          state: "pending",
        };
        set((s) => ({ turns: [...s.turns, turn].slice(-MAX_TURNS) }));
        return id;
      },
      updateTurn: (id, patch) =>
        set((s) => ({
          turns: s.turns.map((t) => (t.id === id ? { ...t, ...patch } : t)),
        })),
      clear: () => set({ turns: [] }),
    }),
    {
      name: "bvs-thread",
      storage: createJSONStorage(() => sessionStorage),
      // A question still waiting for its answer cannot be resumed after a reload.
      partialize: (s) => ({
        turns: s.turns.filter((t) => t.state !== "pending"),
      }),
    },
  ),
);

export function turnById(turns: Turn[], id: string | null): Turn | undefined {
  return id ? turns.find((t) => t.id === id) : undefined;
}
