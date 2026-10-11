# Third-party notices

## OpenHands Agent Canvas (the base of the `web/` shell)

Parts of the `web/` user interface are adapted from the Agent Canvas web app v1.26.0 in the
OpenHands project (https://github.com/OpenHands/OpenHands), which is MIT licensed. This product is
not affiliated with or endorsed by OpenHands, and shows none of its names or logos.

Files copied from it, then edited (imports, names, strings):

- Toolchain: `web/react-router.config.ts`, `web/tsconfig.json`, `web/tailwind.config.js`,
  `web/hero.ts`, `web/.prettierrc.json`, `web/public/mockServiceWorker.js`
- Styling and tokens: `web/src/tailwind.css`, `web/src/styles/agent-server-ui-style-scope.ts`,
  `web/src/themes/color-themes.ts`, `web/src/themes/color-theme/` (types, runtime, the registry,
  the light and dark definitions, the neutral palette), `web/src/hooks/use-color-theme.ts`
- Components: `web/src/ui/divider.tsx`, `web/src/ui/typography.tsx`,
  `web/src/components/shared/` (badge, loading spinner, navigation link, styled
  tooltip, modal button, modal backdrop, modal body, modal close button),
  `web/src/components/ui/resize-handle.tsx`, `web/src/context/navigation-context.tsx`
- Sidebar: `web/src/components/features/sidebar/` (layout, nav link, collapsed icon slot, mobile
  nav context, mobile menu toggle, mobile menu bar)
- Utilities: `web/src/utils/base-path.ts`, `hover-reveal-classes.ts`, `form-control-classes.ts`,
  `mobile-top-bar-icon-button-classes.ts`
- Icons: `web/src/icons/loading-outer.svg`, `block-drawer-left.svg`, `modal-close.svg`
- Mock setup: `web/src/mocks/browser.ts`, `node.ts`
- Scripts: `web/scripts/make-i18n-translations.cjs` and `check-translation-completeness.cjs`
  are rewritten from the originals (English and Hindi only)

Everything else in `web/` (root, routes, answer card, evidence panel, stores, API client, i18n
runtime, tests) is written for this project. The shell's agent, terminal, editor, telemetry,
backend and settings features were not imported.

```
The MIT License (MIT)

Copyright © 2025 OpenHands contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Fonts

`@fontsource/outfit` and `@fontsource/noto-sans-devanagari`, SIL Open Font License 1.1, bundled with
the app (no CDN).
