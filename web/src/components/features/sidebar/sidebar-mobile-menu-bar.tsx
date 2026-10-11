import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import { SidebarMobileMenuToggle } from "./sidebar-mobile-menu-toggle";

/** The top bar below the `md` breakpoint: the menu button that opens the navigation drawer. */
export function SidebarMobileMenuBar() {
  const { t } = useTranslation();

  return (
    <header
      className="flex md:hidden h-12 shrink-0 items-center gap-2 px-2.5"
      aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
    >
      <SidebarMobileMenuToggle />
      <span className="text-base font-semibold text-contrast">
        {t(I18nKey.BRAND$NAME)}
      </span>
    </header>
  );
}
