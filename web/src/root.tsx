import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { Toaster } from "react-hot-toast";
import { useTranslation } from "react-i18next";
import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLocation,
  useNavigate,
} from "react-router";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  NavigationProvider,
  type NavigationContextValue,
} from "#/context/navigation-context";
import { useColorTheme } from "#/hooks/use-color-theme";
import "#/i18n";
import { I18nKey } from "#/i18n/declaration";
import {
  applyColorTheme,
  COLOR_THEME_BOOTSTRAP_SCRIPT,
  COLOR_THEMES,
  readPersistedColorTheme,
} from "#/themes/color-themes";
import { cn } from "#/utils/utils";
import "./tailwind.css";
import "./index.css";

const THEME_SCRIPT = { __html: COLOR_THEME_BOOTSTRAP_SCRIPT };

/** Applies the persisted palette before paint; useEffect would land a frame late. */
function ColorThemeApplier() {
  React.useLayoutEffect(() => {
    applyColorTheme(readPersistedColorTheme());
  }, []);
  return null;
}

export function Layout({ children }: { children: React.ReactNode }) {
  const colorTheme = useColorTheme();
  const appearance = COLOR_THEMES[colorTheme].appearance;
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
        {/* The only raw HTML in the app: our own theme script, which sets the palette before paint. */}
        {/* eslint-disable-next-line react/no-danger */}
        <script dangerouslySetInnerHTML={THEME_SCRIPT} />
      </head>
      <body data-bvs-ui="" className="m-0">
        <div
          className={cn(appearance, "min-h-dvh text-foreground")}
          data-theme={appearance}
        >
          <ColorThemeApplier />
          {children}
          <Toaster />
        </div>
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

/** Lets the shell's link components navigate through react-router. */
function NavigationBridge({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const value = React.useMemo<NavigationContextValue>(
    () => ({
      currentPath: location.pathname,
      conversationId: null,
      isNavigating: false,
      navigate: (to, options) => {
        void navigate(to, { replace: options?.replace });
      },
    }),
    [location.pathname, navigate],
  );
  return <NavigationProvider value={value}>{children}</NavigationProvider>;
}

export default function App() {
  const { i18n } = useTranslation();
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { refetchOnWindowFocus: false } },
      }),
  );

  React.useEffect(() => {
    document.documentElement.lang = i18n.resolvedLanguage ?? "en";
  }, [i18n.resolvedLanguage]);

  return (
    <QueryClientProvider client={queryClient}>
      <NavigationBridge>
        <Outlet />
      </NavigationBridge>
    </QueryClientProvider>
  );
}

export function HydrateFallback() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-canvas-base">
      <LoadingSpinner size="large" />
    </main>
  );
}

export function ErrorBoundary() {
  const { t } = useTranslation();
  return (
    <main className="mx-auto flex max-w-xl flex-col gap-3 p-6">
      <h1 className="text-2xl font-semibold">
        {t(I18nKey.ERROR$BOUNDARY_TITLE)}
      </h1>
      <p>{t(I18nKey.ERROR$BOUNDARY_BODY)}</p>
    </main>
  );
}
