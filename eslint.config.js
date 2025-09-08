import eslint from '@eslint/js';
import { fixupConfigRules, fixupPluginRules } from "@eslint/compat";
import _import from "eslint-plugin-import";
import globals from "globals";
import path from "node:path";
import { fileURLToPath } from "node:url";
import js from "@eslint/js";
import { FlatCompat } from "@eslint/eslintrc";
import eslintConfigPreact from "eslint-config-preact";
import eslintPluginReact from "eslint-plugin-react";
import eslintPluginReactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

export default tseslint.config({
  files: ["frontend/src/**/*.ts", "frontend/src/**/*.tsx"],
  extends: [
    eslint.configs.recommended,
    tseslint.configs.recommended,
    ...fixupConfigRules(
      compat.extends(
        "plugin:import/recommended",
        "plugin:react-hooks/recommended"
      )
    ),
  ],
  plugins: {
    import: fixupPluginRules(_import),
    react: fixupPluginRules(eslintPluginReact),
    "react-hooks": fixupPluginRules(eslintPluginReactHooks),
  },

  languageOptions: {
    globals: {
      ...globals.browser,
    },

    ecmaVersion: 2023,
    sourceType: "module",

    parserOptions: {
      ecmaFeatures: {
        jsx: false,
        impliedStrict: true,
      },
    },
  },

  settings: {
    "import/resolver": {
      node: {
        moduleDirectory: [
          "frontend/src",
          "node_modules"
        ],
        extensions: [".ts", ".tsx"],
      },
      typescript: {
         alwaysTryTypes: true,
      }
    },
    react: eslintConfigPreact.settings.react,
  },

  rules: {
    ...eslintConfigPreact.rules,
    "no-unused-vars": "off",
    "@typescript-eslint/no-unused-vars": [
        "error",
        {
          "argsIgnorePattern": "^_",
        }
    ],
    "import/no-unresolved": [
      "error",
      {
        ignore: [
          "^@dashlive/",
          "socket.io",
          "codec-string",
          "^wouter-preact/memory-location",
          "^wouter-preact/use-browser-location",
        ],
      },
    ],
    "import/first": "error",
    "import/no-amd": "error",
    "import/no-anonymous-default-export": "warn",
    "import/no-named-as-default": "off",
  },
});
