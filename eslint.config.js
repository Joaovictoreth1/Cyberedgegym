import js from '@eslint/js';
import globals from 'globals';

export default [
    js.configs.recommended,
    { files: ['frontend/*.js'], languageOptions: { globals: globals.browser } },
    { files: ['scripts/*.mjs', 'frontend/tests/*.js', '*.js', '*.cjs'], languageOptions: { globals: globals.node } },
    { ignores: ['dist/**', 'playwright-report/**', 'test-results/**'] },
];
