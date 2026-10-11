import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type EvidenceTab = "sources" | "working" | "rule" | "pdf" | "details";
export type PdfLang = "en" | "hi";

export interface PdfTarget {
  lang: PdfLang;
  page: number;
}

export interface RuleTarget {
  /** Rule id as the API takes it: "56", "12-A", "26-B". */
  rule: string;
  /** A verified quote to highlight inside the full text. */
  quote?: string;
}

export const MIN_PANEL_WIDTH = 320;
export const MAX_PANEL_WIDTH = 900;
export const DEFAULT_PANEL_WIDTH = 460;

interface UiState {
  activeTurnId: string | null;
  tab: EvidenceTab;
  pdf: PdfTarget | null;
  ruleTarget: RuleTarget | null;
  panelOpen: boolean;
  panelWidth: number;
  selectTurn: (id: string | null) => void;
  setTab: (tab: EvidenceTab) => void;
  openPdf: (turnId: string, target: PdfTarget) => void;
  openRule: (turnId: string, target: RuleTarget) => void;
  setPdf: (target: PdfTarget) => void;
  focusTick: number;
  focusInput: () => void;
  setPanelOpen: (open: boolean) => void;
  setPanelWidth: (width: number) => void;
  reset: () => void;
}

export const clampPanelWidth = (w: number) =>
  Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, Math.round(w)));

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      activeTurnId: null,
      tab: "sources",
      pdf: null,
      ruleTarget: null,
      panelOpen: true,
      panelWidth: DEFAULT_PANEL_WIDTH,
      selectTurn: (id) =>
        set({ activeTurnId: id, tab: "sources", pdf: null, ruleTarget: null }),
      setTab: (tab) => set({ tab }),
      openPdf: (turnId, pdf) =>
        set({ activeTurnId: turnId, pdf, tab: "pdf", panelOpen: true }),
      openRule: (turnId, ruleTarget) =>
        set({ activeTurnId: turnId, ruleTarget, tab: "rule", panelOpen: true }),
      setPdf: (pdf) => set({ pdf }),
      focusTick: 0,
      focusInput: () => set((s) => ({ focusTick: s.focusTick + 1 })),
      setPanelOpen: (panelOpen) => set({ panelOpen }),
      setPanelWidth: (width) => set({ panelWidth: clampPanelWidth(width) }),
      reset: () =>
        set({
          activeTurnId: null,
          tab: "sources",
          pdf: null,
          ruleTarget: null,
        }),
    }),
    {
      name: "bvs-ui",
      storage: createJSONStorage(() => localStorage),
      // Only the layout preference outlives the tab; what is selected does not.
      partialize: (s) => ({ panelWidth: s.panelWidth }),
    },
  ),
);
