import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { AnswerCard } from "#/components/answer-card";
import { EvidencePanel } from "#/components/evidence-panel";
import { server } from "#/mocks/node";
import { useThreadStore } from "#/stores/thread-store";
import { useUiStore } from "#/stores/ui-store";
import {
  FIXTURES,
  cardOf,
  renderWithProviders,
  resetApp,
  seedTurn,
} from "#/test-utils";

function Live({ id }: { id: string }) {
  const turn = useThreadStore((s) => s.turns.find((t) => t.id === id))!;
  return (
    <>
      <AnswerCard turn={turn} />
      <EvidencePanel />
    </>
  );
}

beforeEach(resetApp);

describe("every status fixture renders", () => {
  const cases: [keyof typeof FIXTURES, string][] = [
    ["ANSWERED", "ANSWERED"],
    ["PARTIAL", "PARTIAL"],
    ["PARTIAL_HINDI", "PARTIAL"],
    ["PARTIAL_AMENDMENT", "PARTIAL"],
    ["NOT_FOUND", "NOT_FOUND"],
    ["NEEDS_REVIEW", "NEEDS_REVIEW"],
    ["ERROR", "ERROR"],
  ];
  it.each(cases)("%s", (name, status) => {
    const id = seedTurn(FIXTURES[name]);
    renderWithProviders(<Live id={id} />);
    const badge = screen.getByTestId("status-badge");
    expect(badge).toHaveAttribute("data-status", status);
    // icon + word, never colour alone
    expect(badge.querySelector("svg")).not.toBeNull();
    expect(badge.textContent?.trim().length).toBeGreaterThan(3);
    expect(screen.getByTestId("answer-card")).toBeInTheDocument();
  });
});

describe("answer card content", () => {
  it("shows the flagship numbers, sources, notices and the working", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<Live id={id} />);
    expect(screen.getByTestId("answer-text")).toHaveTextContent(
      "Front open space is 3.0 m",
    );
    const card = within(screen.getByTestId("answer-card"));
    expect(card.getAllByTestId("citation").length).toBe(2);
    expect(screen.getByTestId("warning-dp_precedence")).toHaveTextContent(
      "Rule 103",
    );
    expect(screen.getByTestId("missing-info")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show working" }));
    const calcs = screen.getAllByTestId("working-calc");
    expect(calcs.length).toBe(5);
    expect(
      within(calcs[0]).getByText("1. Up to 9.0 meters 3.0 meters"),
    ).toBeInTheDocument();
    expect(within(calcs[3]).getByText("₹3,000")).toBeInTheDocument();
  });

  it("shows the amendment warning as a notice, not as a quote", () => {
    const id = seedTurn(FIXTURES.PARTIAL_AMENDMENT);
    renderWithProviders(<Live id={id} />);
    const warning = screen.getByTestId("warning-amendment");
    expect(warning).toHaveTextContent("28/08/2026");
    expect(warning).toHaveTextContent("Gazette");
    for (const q of screen.getAllByRole("blockquote", { hidden: true })) {
      expect(q.textContent).not.toContain("28/08/2026");
    }
  });

  it("shows candidates and no answer text for NEEDS_REVIEW", () => {
    const id = seedTurn(FIXTURES.NEEDS_REVIEW);
    renderWithProviders(<Live id={id} />);
    expect(screen.queryByTestId("answer-text")).toBeNull();
    expect(screen.getByTestId("candidates")).toHaveTextContent("Read rule 103");
    expect(screen.getByText(/could not be verified/i)).toBeInTheDocument();
  });

  it("renders model text as plain text, never as HTML", () => {
    const card = cardOf(FIXTURES.ANSWERED);
    card.answer = '<img src=x onerror="alert(1)"><b>bold</b> Rule 83';
    useThreadStore.getState().addTurn("q");
    const t = useThreadStore.getState().turns[0];
    useThreadStore.getState().updateTurn(t.id, { state: "done", card });
    const { container } = renderWithProviders(<Live id={t.id} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByTestId("answer-text").textContent).toContain(
      "<img src=x",
    );
  });

  it("marks Hindi cards lang=hi and keeps the quote in English", () => {
    const id = seedTurn(FIXTURES.PARTIAL_HINDI);
    renderWithProviders(<Live id={id} />);
    expect(screen.getByTestId("answer-card")).toHaveAttribute("lang", "hi");
    expect(
      within(screen.getByTestId("answer-card"))
        .getByTestId("citation")
        .querySelector("blockquote"),
    ).toHaveAttribute("lang", "en");
  });

  it("offers a print slip, a report dialog and the limits links", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<Live id={id} />);
    expect(
      screen.getByRole("button", { name: /Print slip for citizen/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "What this tool does NOT do" }),
    ).toHaveAttribute("href", "/limits");
    await userEvent.click(
      screen.getByRole("button", { name: "Report this answer" }),
    );
    const dialog = screen.getByRole("dialog");
    const send = within(dialog).getByRole("button", { name: "Send report" });
    expect(send).toBeDisabled(); // consent is required
    await userEvent.click(within(dialog).getByRole("checkbox"));
    expect(send).toBeEnabled();
  });
});

describe("PDF buttons", () => {
  it("open the English and Hindi page in the PDF tab", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<Live id={id} />);
    const [first] = screen.getAllByTestId("citation");
    await userEvent.click(
      within(first).getByRole("button", { name: "English PDF p.77" }),
    );
    expect(useUiStore.getState()).toMatchObject({
      tab: "pdf",
      pdf: { lang: "en", page: 77 },
    });
    const frame = await screen.findByTitle("Official rules PDF page");
    expect(frame).toHaveAttribute("src", "/pdf/rules-en.pdf#page=77");

    await userEvent.click(
      within(first).getByRole("button", { name: "हिंदी PDF p.77" }),
    );
    expect(useUiStore.getState().pdf).toEqual({ lang: "hi", page: 77 });
    expect(await screen.findByTitle("Official rules PDF page")).toHaveAttribute(
      "src",
      "/pdf/rules-hi.pdf#page=77",
    );
  });

  it("switch language and page inside the PDF tab", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<Live id={id} />);
    await userEvent.click(
      within(screen.getAllByTestId("citation")[0]).getByRole("button", {
        name: "English PDF p.77",
      }),
    );
    const tab = screen.getByTestId("pdf-tab");
    await userEvent.click(within(tab).getByRole("button", { name: "Hindi" }));
    expect(screen.getByTitle("Official rules PDF page")).toHaveAttribute(
      "src",
      "/pdf/rules-hi.pdf#page=77",
    );
    expect(
      within(tab).getByRole("link", { name: /Open in a new tab/ }),
    ).toHaveAttribute("href", "/pdf/rules-hi.pdf#page=77");
  });
});

describe("evidence panel tabs", () => {
  it("has the five tabs and switches with the arrow keys", async () => {
    const id = seedTurn(FIXTURES.ANSWERED);
    renderWithProviders(<Live id={id} />);
    const tabs = screen.getAllByRole("tab").map((t) => t.textContent);
    expect(tabs).toEqual(["Sources", "Working", "Rule", "PDF", "Details"]);
    screen.getByRole("tab", { name: "Sources" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Working" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("loads the full rule text and highlights the verified quote", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    renderWithProviders(<Live id={id} />);
    const [first] = screen.getAllByTestId("citation");
    await userEvent.click(
      within(first).getByRole("button", { name: "Read rule 56" }),
    );
    const tab = await screen.findByTestId("rule-tab");
    await waitFor(() => expect(tab.querySelector("mark")).not.toBeNull());
    expect(tab.querySelector("mark")?.textContent).toMatch(
      /Up to 9\.0 meters\s+3\.0 meters/,
    );
  });

  it("shows details: latency, models, tokens", async () => {
    const id = seedTurn(FIXTURES.ANSWERED);
    renderWithProviders(<Live id={id} />);
    await userEvent.click(screen.getByRole("tab", { name: "Details" }));
    const details = screen.getByTestId("details-tab");
    expect(details).toHaveTextContent("1.90 s");
    expect(details).toHaveTextContent("claude-haiku-5-5");
    expect(details).toHaveTextContent("in 2400 · out 180 · cached 512");
  });

  it("asks to choose an answer when none is selected", () => {
    renderWithProviders(<EvidencePanel />);
    expect(screen.getByText(/Choose an answer/)).toBeInTheDocument();
  });
});

describe("parameter chips", () => {
  it("shows the inputs, marks assumptions, and recomputes on edit with no model call", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    let body: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/ask", async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        const card = cardOf(FIXTURES.PARTIAL);
        card.calculations[0].result.value = 3.6;
        card.calculations[0].matched_row_text =
          "2. More than 9.0 meters and up to 12 meters 3.6 meters";
        (card.calculations[0].inputs as Record<string, unknown>).road_width_m =
          10;
        card.answer = "Front open space is 3.6 m.";
        card.meta.calls = 0;
        return HttpResponse.json(card);
      }),
    );
    renderWithProviders(<Live id={id} />);

    expect(screen.getByTestId("chip-plot_area_sqm")).toHaveTextContent(
      "200 sq m",
    );
    expect(screen.getByTestId("chip-road_width_m")).toHaveTextContent("9 m");
    expect(screen.getByTestId("chip-height_m")).toHaveTextContent(
      "12.5 m (assumed)",
    );
    expect(screen.getByTestId("chip-use")).toHaveTextContent("Residential");
    expect(screen.getByTestId("chip-use")).toHaveTextContent("assumed");
    expect(screen.getByTestId("chip-building_type")).toHaveTextContent(
      "not given",
    );

    await userEvent.click(screen.getByTestId("chip-road_width_m"));
    const input = screen.getByRole("spinbutton");
    await userEvent.clear(input);
    await userEvent.type(input, "10");
    await userEvent.keyboard("{Enter}");

    await waitFor(() =>
      expect(screen.getByTestId("answer-text")).toHaveTextContent("3.6 m"),
    );
    // the override carries the edited value, the kept values and the intent, and no assumed ones
    expect(body).toMatchObject({
      question: expect.stringContaining("200 sq m on a 9 m road"),
      lang: "en",
      params_override: {
        intent: "plot_norms",
        road_width_m: 10,
        plot_area_sqm: 200,
      },
    });
    const override = (
      body as unknown as { params_override: Record<string, unknown> }
    ).params_override;
    expect(override).not.toHaveProperty("height_m"); // the assumed height is not pinned
    expect(override).not.toHaveProperty("use"); // nor the assumed use
    expect(screen.getByTestId("chip-road_width_m")).toHaveTextContent("10 m");
    expect(screen.getByTestId("latency")).toHaveTextContent(
      /recomputed in \d+ ms, no model call/,
    );
  });

  it("lets Escape cancel an edit and ignores a non-positive number", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    let called = false;
    server.use(
      http.post("/api/ask", () => {
        called = true;
        return HttpResponse.json(cardOf(FIXTURES.PARTIAL));
      }),
    );
    renderWithProviders(<Live id={id} />);
    await userEvent.click(screen.getByTestId("chip-road_width_m"));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("spinbutton")).toBeNull();
    await userEvent.click(screen.getByTestId("chip-road_width_m"));
    const input = screen.getByRole("spinbutton");
    await userEvent.clear(input);
    await userEvent.type(input, "-3{Enter}");
    expect(called).toBe(false);
  });

  it("shows a select for the building type and sends the choice", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    let body: { params_override?: Record<string, unknown> } = {};
    server.use(
      http.post("/api/ask", async ({ request }) => {
        body = (await request.json()) as typeof body;
        return HttpResponse.json(cardOf(FIXTURES.PARTIAL));
      }),
    );
    renderWithProviders(<Live id={id} />);
    await userEvent.click(screen.getByTestId("chip-building_type"));
    await userEvent.selectOptions(
      screen.getByRole("combobox"),
      "semi_detached",
    );
    await userEvent.keyboard("{Enter}");
    await waitFor(() =>
      expect(body.params_override?.building_type).toBe("semi_detached"),
    );
  });

  it("keeps the card and flags the failure when the recompute fails", async () => {
    const id = seedTurn(FIXTURES.PARTIAL);
    server.use(
      http.post("/api/ask", () =>
        HttpResponse.json({ detail: "bad" }, { status: 422 }),
      ),
    );
    renderWithProviders(<Live id={id} />);
    await userEvent.click(screen.getByTestId("chip-road_width_m"));
    const input = screen.getByRole("spinbutton");
    await userEvent.clear(input);
    await userEvent.type(input, "12{Enter}");
    expect(
      await screen.findByText(/edited value could not be used/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("answer-text")).toHaveTextContent(
      "Front open space is 3.0 m",
    );
  });

  it("has no chips for answers that are not about plot norms", () => {
    const id = seedTurn(FIXTURES.ANSWERED);
    renderWithProviders(<Live id={id} />);
    expect(screen.queryByTestId("param-chips")).toBeNull();
  });
});
