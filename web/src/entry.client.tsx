import { startTransition, StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

async function startMockWorkerIfRequested(): Promise<void> {
  // A literal comparison, so a production build drops the mock worker and MSW entirely.
  if (import.meta.env.VITE_MOCK_API !== "true") return;
  const { worker } = await import("#/mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass", quiet: true });
}

// With VITE_MOCK_API=true the API is served from fixtures, so the UI runs without a backend.
void startMockWorkerIfRequested().then(() => {
  startTransition(() => {
    hydrateRoot(
      document,
      <StrictMode>
        <HydratedRouter />
      </StrictMode>,
    );
  });
});
