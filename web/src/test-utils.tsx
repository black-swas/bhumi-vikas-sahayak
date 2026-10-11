import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import React from "react";
import { MemoryRouter, useLocation, useNavigate } from "react-router";
import { NavigationProvider } from "#/context/navigation-context";
import "#/i18n";
import i18n from "#/i18n";
import type { AnswerCard } from "#/api/types";
import { useThreadStore } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";

import answered from "#/mocks/fixtures/answer_answered.json";
import amendment from "#/mocks/fixtures/answer_amendment_q11.json";
import errorCard from "#/mocks/fixtures/answer_error.json";
import flagship from "#/mocks/fixtures/answer_flagship.json";
import hindi from "#/mocks/fixtures/answer_hindi_q14.json";
import needsReview from "#/mocks/fixtures/answer_needs_review.json";
import notFound from "#/mocks/fixtures/answer_not_found.json";

export const FIXTURES = {
  ANSWERED: answered,
  PARTIAL: flagship,
  PARTIAL_HINDI: hindi,
  PARTIAL_AMENDMENT: amendment,
  NOT_FOUND: notFound,
  NEEDS_REVIEW: needsReview,
  ERROR: errorCard,
} as const;

export const cardOf = (fixture: unknown): AnswerCard =>
  structuredClone(fixture) as unknown as AnswerCard;

function Bridge({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <NavigationProvider
      value={{
        currentPath: location.pathname,
        conversationId: null,
        isNavigating: false,
        navigate: (to) => void navigate(to),
      }}
    >
      {children}
    </NavigationProvider>
  );
}

export function Providers({
  children,
  route = "/",
}: {
  children: React.ReactNode;
  route?: string;
}) {
  const [client] = React.useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Bridge>{children}</Bridge>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

export function renderWithProviders(
  ui: React.ReactElement,
  options: RenderOptions & { route?: string } = {},
) {
  const { route, ...rest } = options;
  return render(ui, {
    wrapper: ({ children }) => <Providers route={route}>{children}</Providers>,
    ...rest,
  });
}

/** Puts an answered question into the thread store and returns its id. */
export function seedTurn(fixture: unknown, question?: string): string {
  const card = cardOf(fixture);
  useThreadStore.getState().addTurn(question ?? card.question);
  const turn = useThreadStore.getState().turns.at(-1)!;
  useThreadStore.getState().updateTurn(turn.id, { state: "done", card });
  useUiStore.getState().selectTurn(turn.id);
  return turn.id;
}

/** Fresh stores and English before every test. */
export async function resetApp() {
  useThreadStore.setState({ turns: [] });
  useUiStore.getState().reset();
  useUiStore.setState({ panelOpen: true });
  await i18n.changeLanguage("en");
}
