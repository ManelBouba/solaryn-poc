export default [{
  files: ['*.js'],
  languageOptions: {
    ecmaVersion: 2022, sourceType: 'module',
    globals: Object.fromEntries(['document', 'window', 'navigator', 'localStorage', 'AbortController', 'clearTimeout', 'setTimeout', 'location', 'history', 'sessionStorage', 'fetch', 'URL', 'URLSearchParams', 'Blob', 'L'].map(name => [name, 'readonly'])),
  },
  rules: { 'no-undef': 'error', 'no-unreachable': 'error', 'no-constant-condition': 'error', 'no-dupe-keys': 'error', 'no-unused-vars': 'error', 'valid-typeof': 'error' },
}];
