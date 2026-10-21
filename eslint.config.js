// Lint rules.
//
// Replaces ruff and black, which linted the Python that is gone. Deliberately
// small: `tsc --noEmit` already catches most of what a linter would, and a
// rule that only restates the compiler is noise in a diff.
//
// The one set that earns its keep here is react-hooks. This app is effect
// heavy -- a reader per frame for the cloud, the pose and the curves, each
// with a staleness guard -- and a missing dependency in one of those is a
// panel that quietly stops updating. That is exactly the bug this catches,
// and it is the bug this codebase is most likely to have.

import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'

export default tseslint.config(
  {
    // Build output, dependencies, and the three.js modules carried over from
    // the Dash app -- those are still JavaScript and become TypeScript one
    // file at a time, with their own review.
    ignores: ['out/**', 'dist/**', 'node_modules/**', 'src/renderer/gl/**', 'build/**']
  },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ['src/renderer/**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn'
    }
  },

  {
    rules: {
      // The IPC boundary hands over values the contract types on the far
      // side; an `any` there is the honest description of what arrives, and
      // the handler table in src/data/index.ts is built on it.
      '@typescript-eslint/no-explicit-any': 'off',
      // An unused argument named with a leading underscore is saying so
      // deliberately -- an event parameter a handler does not read, for one.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }
      ]
    }
  },

  {
    files: ['scripts/**/*.mjs', '*.config.ts', '*.config.js'],
    languageOptions: {
      globals: { process: 'readonly', console: 'readonly', __dirname: 'readonly' }
    }
  }
)
