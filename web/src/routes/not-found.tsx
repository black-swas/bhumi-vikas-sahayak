import { useTranslation } from "react-i18next";
import { NavigationLink } from "#/components/shared/navigation-link";
import { I18nKey } from "#/i18n/declaration";

export default function NotFoundRoute() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-3 p-6">
      <h1 className="text-3xl font-semibold text-contrast">
        {t(I18nKey.NOTFOUND$TITLE)}
      </h1>
      <p className="text-text-secondary">{t(I18nKey.NOTFOUND$BODY)}</p>
      <NavigationLink to="/" className="underline">
        {t(I18nKey.RULE$BACK)}
      </NavigationLink>
    </div>
  );
}
