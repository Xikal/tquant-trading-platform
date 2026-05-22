import tseslint from "typescript-eslint";

const zustandMessage = "页面/组件状态必须进入 Zustand store；不要在 Web 业务 TS/TSX 中重新引入 useState/useReducer。";

export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "dist-native/**",
      "node_modules/**",
      "src/test/**",
      "src/mobile/**",
      "src/main-native.tsx",
      "*.config.js",
      "*.config.ts",
    ],
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: "latest",
        ecmaFeatures: { jsx: true },
        sourceType: "module",
      },
    },
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "react",
              importNames: ["useState", "useReducer"],
              message: zustandMessage,
            },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name=/^(useState|useReducer)$/]",
          message: zustandMessage,
        },
        {
          selector: "CallExpression[callee.object.name='React'][callee.property.name=/^(useState|useReducer)$/]",
          message: zustandMessage,
        },
      ],
    },
  },
);
