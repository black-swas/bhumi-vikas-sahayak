import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AccuracyRoute from "#/routes/accuracy";
import AppLayout from "#/routes/app-layout";
import AskRoute from "#/routes/ask";
import LimitsRoute from "#/routes/limits";
import SlipRoute from "#/routes/slip";
import { server } from "#/mocks/node";
import { useThreadStore } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";
import {
  FIXTURES,
  renderWithProviders,
  resetApp,
  seedTurn,
} from "#/test-utils";

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<AskRoute />} />
        <Route path="accuracy" element={<AccuracyRoute />} />
        <Route path="limits" element={<LimitsRoute />} />
      </Route>
      <Route path="slip/:turnId" element={<SlipRoute />} />
    </Routes>
  );
}

beforeEach(resetApp);

describe("shell", () => {
  it("shows the prototype banner with the amendment count from /api/health", async () => {
    renderWithProviders(<App />);
    const banner = screen.getByTestId("top-banner");
    expect(banner).toHaveTextContent("PROTOTYPE");
    expect(banner).toHaveTextContent("Not legal advice");
    expect(banner).toHaveTextContent("Rules as consolidated to 06/03/2025");
    await waitFor(() =>
      expect(banner).toHaveTextContent("1 later amendment tracked"),
    );
  });

  it("shows the mode badge and a banner when the server cannot be reached", async () => {
    server.use(http.get("/api/health", () => HttpResponse.error()));
    renderWithProviders(<App />);
    await waitFor(() =>
      expect(screen.getByTestId("mode-badge")).toHaveAttribute(
        "data-mode",
        "unreachable",
      ),
    );
    expect(screen.getByTestId("unreachable-banner")).toBeInTheDocument();
  });

  it.each(["live", "replay", "offline"] as const)(
    "mode badge shows %s",
    async (mode) => {
      server.use(
        http.get("/api/health", () =>
          HttpResponse.json({
            status: "ok",
            mode,
            prototype: true,
            amendments: [],
            corpus: {},
          }),
        ),
      );
      renderWithProviders(<App />);
      await waitFor(() =>
        expect(screen.getByTestId("mode-badge")).toHaveAttribute(
          "data-mode",
          mode,
        ),
      );
      expect(screen.getByTestId("mode-badge")).toHaveTextContent(
        mode.toUpperCase(),
      );
    },
  );

  it("has the rail: new question, recent, Ask, Accuracy, Limits, language and theme", () => {
    renderWithProviders(<App />);
    const rail = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(rail).getByTestId("new-question")).toBeInTheDocument();
    for (const id of ["nav-ask", "nav-accuracy", "nav-limits"]) {
      expect(within(rail).getByTestId(id)).toBeInTheDocument();
    }
    expect(within(rail).getByTestId("lang-en")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      within(rail).getByText("Nothing asked yet in this session"),
    ).toBeInTheDocument();
  });

  it("switches the whole interface to Hindi and back", async () => {
    renderWithProviders(<App />);
    await userEvent.click(screen.getByTestId("lang-hi"));
    expect(document.documentElement.lang).toBe("hi");
    expect(screen.getByTestId("nav-accuracy")).toHaveTextContent("सटीकता");
    expect(screen.getByTestId("new-question")).toHaveTextContent("नया प्रश्न");
    expect(screen.getByTestId("top-banner")).toHaveTextContent("प्रोटोटाइप");
    expect(screen.getByTestId("top-banner")).toHaveTextContent(
      "कानूनी सलाह नहीं",
    );
    expect(screen.getByLabelText("आपका प्रश्न")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("lang-en"));
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByTestId("nav-accuracy")).toHaveTextContent("Accuracy");
  });
});

describe("ask flow", () => {
  it("offers three example chips and answers the flagship from the mock API", async () => {
    renderWithProviders(<App />);
    expect(screen.getByTestId("example-0")).toHaveTextContent(
      "200 sq m plot, 9 m road: front gap, floors, fee?",
    );
    expect(screen.getByTestId("example-1")).toHaveTextContent(
      "मेरा 200 वर्ग मीटर का प्लॉट",
    );
    expect(screen.getByTestId("example-2")).toHaveTextContent(
      "How to pay property tax?",
    );

    await userEvent.click(screen.getByTestId("example-0"));
    const card = await screen.findByTestId("answer-card");
    expect(card).toHaveAttribute("data-status", "PARTIAL");
    expect(screen.getAllByTestId("citation").length).toBeGreaterThan(0);
    // the question is in the thread and in "Recent questions"
    expect(screen.getByTestId("question-text")).toHaveTextContent(
      "200 sq m on a 9 m road",
    );
    expect(
      within(screen.getByTestId("recent-questions")).getAllByRole("button"),
    ).toHaveLength(1);
  });

  it("answers the out-of-scope example with NOT FOUND", async () => {
    renderWithProviders(<App />);
    await userEvent.click(screen.getByTestId("example-2"));
    expect(await screen.findByTestId("answer-card")).toHaveAttribute(
      "data-status",
      "NOT_FOUND",
    );
  });

  it("submits typed questions with Enter and clears the box", async () => {
    renderWithProviders(<App />);
    const input = screen.getByLabelText("Your question");
    await userEvent.type(input, "Is a lift required over 15 m?{Enter}");
    expect(await screen.findByTestId("answer-card")).toHaveAttribute(
      "data-status",
      "ANSWERED",
    );
    expect(input).toHaveValue("");
  });

  it("does not submit an empty question", async () => {
    let called = false;
    server.use(
      http.post("/api/ask", () => ((called = true), HttpResponse.json({}))),
    );
    renderWithProviders(<App />);
    await userEvent.type(screen.getByLabelText("Your question"), "   {Enter}");
    expect(called).toBe(false);
    expect(useThreadStore.getState().turns).toHaveLength(0);
  });

  it("shows an error message when the server fails and keeps earlier answers", async () => {
    renderWithProviders(<App />);
    await userEvent.click(screen.getByTestId("example-0"));
    await screen.findByTestId("answer-card");
    server.use(
      http.post("/api/ask", () =>
        HttpResponse.json({ detail: "x" }, { status: 429 }),
      ),
    );
    await userEvent.type(
      screen.getByLabelText("Your question"),
      "again{Enter}",
    );
    expect(await screen.findByTestId("turn-error")).toHaveTextContent(
      "Too many questions",
    );
    expect(screen.getAllByTestId("answer-card")).toHaveLength(1);
  });

  it("Escape closes the evidence panel", async () => {
    renderWithProviders(<App />);
    expect(screen.getByTestId("evidence-panel")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByTestId("evidence-panel")).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Show evidence panel" }),
    );
    expect(screen.getByTestId("evidence-panel")).toBeInTheDocument();
  });

  it("Escape closes a dialog first and leaves the panel open", async () => {
    seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Report this answer" }),
    );
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByTestId("evidence-panel")).toBeInTheDocument();
  });

  it("New question clears the selection and focuses the box", async () => {
    seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<App />);
    useUiStore.getState().selectTurn(useThreadStore.getState().turns[0].id);
    await userEvent.click(screen.getByTestId("new-question"));
    expect(useUiStore.getState().activeTurnId).toBeNull();
    expect(screen.getByLabelText("Your question")).toHaveFocus();
  });

  it("keeps at most 20 turns, in sessionStorage and not localStorage", async () => {
    for (let i = 0; i < 25; i += 1)
      useThreadStore.getState().addTurn(`question ${i}`);
    expect(useThreadStore.getState().turns).toHaveLength(20);
    expect(useThreadStore.getState().turns[0].question).toBe("question 5");
    seedTurn(FIXTURES.ANSWERED);
    expect(sessionStorage.getItem("bvs-thread")).toContain("fx-answered");
    expect(localStorage.getItem("bvs-thread")).toBeNull();
  });

  it("clears recent questions", async () => {
    seedTurn(FIXTURES.ANSWERED);
    renderWithProviders(<App />);
    await userEvent.click(
      screen.getByRole("button", { name: "Clear recent questions" }),
    );
    expect(useThreadStore.getState().turns).toHaveLength(0);
  });
});

describe("slip", () => {
  it("prints a plain slip with the disclaimer, IST time, values, sources and version", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    renderWithProviders(<App />, { route: `/slip/${id}` });
    const slip = await screen.findByTestId("slip");
    expect(screen.queryByTestId("top-banner")).toBeNull(); // no rail, no panel
    expect(screen.queryByTestId("evidence-panel")).toBeNull();
    expect(screen.getByTestId("slip-disclaimer")).toHaveTextContent(
      "Prototype, not legal advice",
    );
    expect(screen.getByTestId("slip-date").textContent).toMatch(
      /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/,
    );
    expect(slip).toHaveTextContent("₹3,000");
    expect(slip).toHaveTextContent("Rule 56(1) · p.77");
    expect(slip).toHaveTextContent("consolidated to 06/03/2025");
    expect(slip).toHaveTextContent("Up to 9.0 meters 3.0 meters");
    // no logo, no QR code, no seal
    expect(
      slip.querySelector("img, canvas, svg:not([aria-hidden])"),
    ).toBeNull();
    await userEvent.click(screen.getByTestId("print-button"));
    expect(print).toHaveBeenCalledTimes(1);
  });

  it("says so when the turn is gone from this session", async () => {
    renderWithProviders(<App />, { route: "/slip/nope" });
    expect(await screen.findByTestId("slip-missing")).toHaveTextContent(
      "no longer in this browser session",
    );
  });

  it("opens from the card's print button", async () => {
    seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: /Print slip for citizen/ }),
    );
    expect(await screen.findByTestId("slip")).toBeInTheDocument();
  });

  it("is bilingual for a Hindi question", async () => {
    const id = seedTurn(FIXTURES.PARTIAL_HINDI);
    renderWithProviders(<App />, { route: `/slip/${id}` });
    const slip = await screen.findByTestId("slip");
    expect(slip).toHaveAttribute("lang", "hi");
    expect(slip).toHaveTextContent("सामने का खुला स्थान");
  });
});

describe("limits and accuracy pages", () => {
  it("lists what the tool does not do and when to escalate", () => {
    renderWithProviders(<App />, { route: "/limits" });
    expect(
      screen.getByRole("heading", { name: "What this tool does NOT do" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "When to escalate" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/does not give legal advice/)).toBeInTheDocument();
    expect(screen.getByText(/Rule 103/)).toBeInTheDocument();
    expect(
      screen.getByText(/never prints a helpline number/),
    ).toBeInTheDocument();
  });

  it("shows the latest evaluation: summary stats and a pass/fail table", async () => {
    renderWithProviders(<App />, { route: "/accuracy" });
    const summary = await screen.findByTestId("eval-summary");
    expect(summary).toHaveTextContent("90%");
    expect(summary).toHaveTextContent("16 of 17");
    expect(summary).toHaveTextContent("1.4 s");
    expect(summary).toHaveTextContent("3.9 s");
    expect(within(summary).getAllByText("measured").length).toBeGreaterThan(5);
    const rows = within(screen.getByTestId("eval-cases")).getAllByRole("row");
    expect(rows).toHaveLength(5); // header + 4 cases
    expect(within(rows[4]).getByText("Fail")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Pass")).toBeInTheDocument();
  });

  it("says so when there is no report yet", async () => {
    server.use(
      http.get("/api/eval/latest", () =>
        HttpResponse.json({ available: false }),
      ),
    );
    renderWithProviders(<App />, { route: "/accuracy" });
    expect(await screen.findByTestId("no-report")).toBeInTheDocument();
  });
});
