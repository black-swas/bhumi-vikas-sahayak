import React from "react";
import { Outlet } from "react-router";
import { AppRail } from "#/components/app-rail";
import { SidebarMobileMenuBar } from "#/components/features/sidebar/sidebar-mobile-menu-bar";
import {
  SidebarMobileNavProvider,
  useSidebarMobileNav,
} from "#/components/features/sidebar/sidebar-mobile-nav-context";
import { UnreachableBanner } from "#/components/mode-badge";
import { TopBanner } from "#/components/top-banner";
import { useNavigation } from "#/context/navigation-context";
import { cn } from "#/utils/utils";

function Shell() {
  const { isOpen, close } = useSidebarMobileNav();
  const { currentPath } = useNavigation();

  // A drawer that stays open after the clerk picks a page would cover the page.
  React.useEffect(() => {
    close();
  }, [currentPath, close]);

  return (
    <div
      data-testid="root-layout"
      className="flex h-dvh flex-col bg-canvas-base text-foreground"
    >
      <SidebarMobileMenuBar />
      <div className="flex min-h-0 flex-1">
        {isOpen ? (
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            onClick={close}
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
          />
        ) : null}
        <aside
          className={cn(
            "w-72 shrink-0 border-e border-border-subtle",
            isOpen
              ? "fixed inset-y-0 start-0 z-50 block shadow-xl md:static md:shadow-none"
              : "hidden md:block",
          )}
        >
          <AppRail onNavigate={close} />
        </aside>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <TopBanner />
          <UnreachableBanner />
          <main className="flex min-h-0 flex-1 flex-col">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

export default function AppLayout() {
  return (
    <SidebarMobileNavProvider>
      <Shell />
    </SidebarMobileNavProvider>
  );
}
