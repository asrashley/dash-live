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

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
    baseDirectory: __dirname,
    recommendedConfig: js.configs.recommended,
    allConfig: js.configs.all
});

export default [
  ...fixupConfigRules(compat.extends(
    "eslint:recommended",
    "plugin:import/recommended",
    "plugin:react-hooks/recommended",
  )),
  {
    files: [
        "static/js/**/*.js"
    ],
    ignores: [
        'node_modules/*'
    ],
    plugins: {
      "import": fixupPluginRules(_import),
      react: fixupPluginRules(eslintPluginReact),
      "react-hooks": fixupPluginRules(eslintPluginReactHooks)
    },

    languageOptions: {
        globals: {
            ...globals.browser,
        },

        ecmaVersion: 2022,
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
                paths: ["src"],
                extensions: [".js"],
            },
        },
        "react": eslintConfigPreact.settings.react,
    },

    rules: {
      ...eslintConfigPreact.rules,
        "no-unused-vars": ["error", {
            argsIgnorePattern: "^_",
        }],
        "import/no-unresolved": [
          "error",
          {
            ignore: [
              "^@dashlive/hooks",
              "^@dashlive/ui",
              "^/libs/default-options.js$",
              "^/libs/routemap.js$",
              "^/libs/content_roles.js$",
              "socket.io",
              "^wouter-preact/use-browser-location"
            ],
          },
        ],
        "import/first": "error",
        "import/no-amd": "error",
        "import/no-anonymous-default-export": "warn",
        "import/no-named-as-default": "off",
    },
}];
