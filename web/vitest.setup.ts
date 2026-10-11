import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { server } from "#/mocks/node";

// jsdom has no ResizeObserver or scrollTo; HeroUI and the thread use them.
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  vi.stubGlobal("ResizeObserver", MockResizeObserver);
  HTMLElement.prototype.scrollTo = vi.fn();
  window.scrollTo = vi.fn();
});

afterEach(() => {
  server.resetHandlers();
  cleanup();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

afterAll(() => {
  server.close();
  vi.unstubAllGlobals();
});
