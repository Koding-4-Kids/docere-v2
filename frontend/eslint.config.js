import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Legitimate init/sync patterns (auth, theme, URL parsing) flag false positives.
      'react-hooks/set-state-in-effect': 'off',
      // App exports hooks (useAuth, useToast) alongside providers; HMR hint only.
      'react-refresh/only-export-components': 'off',
      // useRef(Date.now()) and similar are intentional for timers; ref init is not render output.
      'react-hooks/purity': 'off',
    },
  },
])
