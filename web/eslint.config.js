// Flat ESLint config, trimmed from the shell's: the accessibility, i18n and react-hooks rules
// stay (a literal user-facing string in JSX fails the build, so every string is translated).
import { fileURLToPath } from "node:url";
import path from "node:path";

import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import jsxA11yPlugin from "eslint-plugin-jsx-a11y";
import prettierConfig from "eslint-config-prettier";
import globals from "globals";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const compat = new FlatCompat({
  baseDirectory: __dirname,
  resolvePluginsRelativeTo: __dirname,
});

export default [
  {
    ignores: [
      "node_modules/**",
      "build/**",
      "coverage/**",
      ".react-router/**",
      "public/mockServiceWorker.js",
      "src/i18n/declaration.ts",
      "src/api/schema.d.ts",
    ],
  },
  js.configs.recommended,
  // eslint-plugin-i18next still ships legacy config, so it comes in through FlatCompat.
  ...compat.extends("plugin:i18next/recommended"),
  {
    files: ["**/*.{ts,tsx}"],
    linterOptions: { reportUnusedDisableDirectives: "warn" },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parser: tsParser,
      parserOptions: { project: "./tsconfig.json", ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node, ...globals.es2024 },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
      "jsx-a11y": jsxA11yPlugin,
    },
    settings: { react: { version: "detect" } },
    rules: {
      ...tsPlugin.configs["eslint-recommended"].overrides[0].rules,
      ...tsPlugin.configs.recommended.rules,
      ...reactPlugin.configs.recommended.rules,
      ...reactPlugin.configs["jsx-runtime"].rules,
      ...reactHooksPlugin.configs.recommended.rules,
      ...jsxA11yPlugin.configs.recommended.rules,
      ...prettierConfig.rules,

      // Hard-coded user-facing text in JSX or in translatable attributes fails lint.
      "i18next/no-literal-string": [
        "error",
        {
          mode: "jsx-only",
          "jsx-attributes": {
            include: ["placeholder", "alt", "aria-label", "title", "label", "heading", "text"],
          },
          callees: {
            exclude: [
              "i18n(ext)?", "t", "require", "addEventListener", "removeEventListener",
              "postMessage", "getElementById", "dispatch", "commit", "includes", "indexOf",
              "endsWith", "startsWith", "cn",
            ],
          },
          "object-properties": { exclude: ["[A-Z_-]+", "className"] },
        },
      ],
      "@typescript-eslint/no-empty-object-type": [
        "error",
        { allowInterfaces: "with-single-extends" },
      ],
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          args: "after-used",
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
          caughtErrors: "none",
        },
      ],
      // React Compiler rules are opt-in; we have not adopted the compiler.
      "react-hooks/immutability": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      // Never render model or corpus text as HTML.
      "react/no-danger": "error",
      "no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "react-markdown", message: "Model and corpus text is shown as plain text." },
            { name: "rehype-raw", message: "No raw HTML from model or corpus text." },
            { name: "posthog-js", message: "No telemetry." },
          ],
        },
      ],
    },
  },
  // Tests may use literal strings and any-typed mocks.
  {
    files: ["**/*.test.{ts,tsx}", "src/mocks/**", "vitest.setup.ts", "test-utils.tsx"],
    rules: {
      "i18next/no-literal-string": "off",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
];
