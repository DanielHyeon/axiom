import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', '*.cjs'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      // Phase 0: 하드코딩 색상/폰트 방지 — 디자인 토큰 사용 강제
      'no-restricted-syntax': [
        'warn',
        {
          selector: 'Literal[value=/^#[0-9A-Fa-f]{3,8}$/]',
          message: 'Hex 색상값 하드코딩 금지. 디자인 토큰(bg-muted, text-foreground 등)을 사용하세요.',
        },
      ],
    },
  },
  // Feature Boundary Rules (apply only to features)
  {
    files: ['src/features/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              // Prevent importing from other features
              group: ['@/features/*'],
              message: 'Cross-feature imports are not allowed. Features must be independent. Use shared components or Zustand stores.',
            },
            {
              // Prevent importing pages or layouts
              group: ['@/pages/*', '@/layouts/*'],
              message: 'Features must not import pages or layouts.',
            },
            {
              // Prevent importing infrastructure directly (Axios)
              group: ['@/lib/api/*'],
              message: 'Features must not directly import infrastructure like Axios. Use custom hooks.',
            },
            {
              // Prevent going up multiple directories to bypass alias restrictions
              group: ['../../features/*', '../../../features/*'],
              message: 'Use absolute alias @/ instead of relative paths to bypass boundaries.',
            },
          ],
        },
      ],
    },
  },
  // Shared Boundary Rules
  {
    files: ['src/shared/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/features/*', '@/pages/*', '@/layouts/*'],
              message: 'Shared components must not import features, pages, or layouts (Reverse dependency).',
            },
          ],
        },
      ],
    },
  },
  // Pages Boundary Rules
  {
    files: ['src/pages/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              // Prevent importing infrastructure directly
              group: ['@/lib/api/*'],
              message: 'Pages must not directly import infrastructure.',
            },
          ],
        },
      ],
    },
  }
)
