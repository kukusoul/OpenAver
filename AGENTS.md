# OpenAver - Codex Review Guidelines

## Review guidelines

### Security

- API responses MUST NOT contain `str(e)` or Python exception details. Error messages to frontend must be fixed Chinese strings (e.g. `"操作失敗"`), with details logged server-side via `logger.error()` or `logger.exception()`.
- No SQL injection — all database queries must use parameterized statements.
- No unvalidated user input used directly in file system operations (`open()`, `Path()`, `os.path`).
- No hardcoded secrets, API keys, passwords, or tokens in source code.

### Path handling

- All `file:///` URI construction and parsing MUST go through `core/path_utils.py`.
- Forbidden patterns outside `path_utils.py`:
  - `path[8:]` or `path[len('file:///'):]` (manual URI strip)
  - `f"file:///{...}"` (manual URI construction)
  - `replace('/', '\\')` for path conversion
  - `startswith('file:///')` + manual handling
- If you see any of these patterns, flag as P0.

### Alpine.js

- `document.querySelector('[x-data]')` without a scoped selector (e.g. `.search-container[x-data]`) is a bug — it selects the sidebar instead of the page component.
- Alpine methods in templates must be called with `()` — `:disabled="!canGoPrev"` is wrong, `:disabled="!canGoPrev()"` is correct.

### i18n

- Strategy: **source locale only + milestone sync**. During development PRs, only `locales/zh_TW.json` is required to be updated.
- Missing keys or entire subtrees in `zh_CN.json`, `ja.json`, or `en.json` during development **are not findings**.
- **Flag these**:
  - hardcoded Chinese UI text in HTML/JS that should use `t()` / `window.t()`
  - `t()` / `window.t()` referencing keys missing from `zh_TW.json`
  - HTML-containing translations rendered without `| safe`
- **Out of scope for i18n review**:
  - `showToast()`, `alert()`, `confirm()`
  - SSE messages
  - `console.*`
  - technical terms such as NFO, API Key, Jellyfin, Proxy
  - browser/platform built-in text
  - **`design-system` and `motion-lab` page demo content** — these are internal dev-reference pages (not in main nav, not user-facing), and demo labels often contain Fluent design tokens (`fluent-decel`, `Acrylic 30px`, `--surface-1` etc.) that should not be translated. Page chrome (nav / page title) still goes through i18n; only demo body text is exempt.
- At milestone/release, all 4 locales must have identical key sets.

### General code quality

- No `console.log` left in production JavaScript (except intentional debug modes).
- Python `except` blocks should not silently swallow errors — at minimum `logger.error()`.
- Avoid introducing new inline `<script>` blocks in templates; prefer separate `.js` files.

### Out of scope (handled by automated tooling)

The following are enforced by `eslint.config.mjs` / `stylelint.config.js` within their
configured file scopes — DO NOT flag in code review (file an eslint/stylelint config
issue if a rule is missing or if scope needs broadening):

**ESLint** (base scope `web/static/js/**/*.js` unless noted):
- `no-alert` — no `alert()` / `confirm()` / `prompt()` anywhere in JS (global scope)
- `no-console` — **search pages only** (`web/static/js/pages/search/**/*.js`); `console.error` and `console.warn` are allowed; all other JS directories are NOT covered
- `no-restricted-syntax` `window.confirm` — no `window.confirm()` anywhere in JS (global scope)
- `no-restricted-syntax` `document.createElement` — **state mixins only** (`web/static/js/pages/**/state/**/*.js`); allowed in component files outside `state/` (e.g. ghost-fly.js, tutorial.js)
- `no-restricted-syntax` `showModal()` — **search state only** (`web/static/js/pages/search/state/**/*.js`); other page state dirs are NOT covered

**Stylelint** (`web/static/css/**/*.css`, excluding `tailwind.css` and `design-system.css`):
- `color-no-hex` — no hex color values; use design token `var(--...)` instead
- `declaration-property-value-disallowed-list` — no bare `0.Xs` durations in `transition`; no `blur(Npx)` literals in `filter`/`backdrop-filter`; no `rgba(N...)` in `box-shadow`; no `Npx` literals in `border-radius`
- `selector-disallowed-list` — no `:is(...manual-input...)` selector patterns

**Still enforced by pytest** (NOT by lint — flag these in review if violated):
- HTML template inline handlers (`onclick=` etc.) — `TestNoVanillaHandlers` (HTML scan, eslint does not parse `.html`)
- HTML template `style="...display:none..."` combined with `x-show` — `TestNoInlineStyleDisplay` (HTML scan)
- Specific Chinese `confirm()` strings in `settings/state-config.js` — `TestSettingsResetConfigNoNativeConfirm` (string fingerprint guard; `no-alert` cannot constrain string content)
- Specific Chinese `confirm()` strings in `scanner/state-alias.js` — `TestScannerDeleteAliasGroupNoNativeConfirm` test1 (same reason)
- Alpine state contracts (modal open class, method names, escape ladder in HTML) — `TestNoDuplicateNativeDialog` test2, `TestScannerDeleteAliasGroupNoNativeConfirm` test2/test3 (cross-language contract)
- `navigator.clipboard?.writeText` optional-chaining guard pattern — `TestNoAlertInSearchJs` clipboard tests (guard count/presence, not expressible in eslint)

(Anything outside this list — including `console.log` outside search pages, `createElement` outside `state/` dirs, formatting, unused variables, dead code — is still in code-review scope unless explicitly added to the lint config.)

### Test bloat policy

DO NOT request new pytest tests for issues that fit eslint/stylelint scope.
If a regression of this class arises, the fix is:
- Add an eslint/stylelint rule to the existing config, OR
- If the rule cannot be expressed in eslint/stylelint (cross-file/cross-language contract), add a dedicated lint script and wire it into `npm run lint` or pre-merge — NOT a new TestNoXxx pytest class.
