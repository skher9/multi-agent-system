// The gate's code-smell scan (backend/agents/quality.py): SonarSource's rules for bugs
// and code smells, run on the files an agent changed. Standalone on purpose: it never
// reads the repo's own ESLint config, so it works the same on every repo, and the
// repo's own lint still runs separately (pnpm lint).
import sonarjs from "eslint-plugin-sonarjs";
import tseslint from "typescript-eslint";

export default [
  {
    files: ["**/*.{js,jsx,mjs,cjs,ts,tsx,mts,cts}"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { sonarjs },
    rules: {
      ...sonarjs.configs.recommended.rules,
      // Notes for people, not defects: a TODO an agent leaves is caught by the
      // gate's placeholder scan when it stands in for real code.
      "sonarjs/todo-tag": "off",
      "sonarjs/fixme-tag": "off",
    },
  },
];
