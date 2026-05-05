// eslint.config.mjs — ESLint 9 flat config
// OpenAver frontend JS lint rules
// Replaces: TestNoCreateElement, TestNoDuplicateNativeDialog(test1),
//           TestSearchConsoleLogGuard, TestShowcaseRemoveActressNoNativeConfirm,
//           TestNoAlertInSearchJs(前9 alert tests)
//
// Flat config 注意事項：
// 同一條 rule（特別是 array-style 如 no-restricted-syntax）在多個 matching configs
// 會被「後者完全替換」而非 array merge。為避免規則靜默失效，本檔以 `ignores` 切出
// 不重疊的 file glob 區段，每個區段給該 file group 完整的 selector 清單。
import js from "@eslint/js";

// ── 共用 selector 物件 ─────────────────────────────────────────
const SEL_CREATE_ELEMENT = {
  selector:
    "CallExpression[callee.object.name='document'][callee.property.name='createElement']",
  message:
    "Use Alpine x-if / x-for instead of document.createElement in state mixins. " +
    "createElement is only allowed in component files (e.g. ghost-fly.js, tutorial.js).",
};

const SEL_SHOW_MODAL = {
  selector: "CallExpression[callee.property.name='showModal']",
  message:
    "Use Alpine state-driven modal pattern instead of native showModal() in search state files. " +
    "See TestNoDuplicateNativeDialog pattern.",
};

const SEL_WINDOW_CONFIRM = {
  selector:
    "CallExpression[callee.object.name='window'][callee.property.name='confirm']",
  message:
    "Use fluent-modal pattern instead of window.confirm(). " +
    "See CD-52-11 decision for migration pattern.",
};

export default [
  // ── 全域基礎設定 ──────────────────────────────────────────────
  {
    ...js.configs.recommended,
    files: ["web/static/js/**/*.js"],
    rules: {
      // Alpine x-data 注入的 $store / $dispatch 等為 runtime global
      "no-undef": "off",
    },
  },

  // ── 全域禁止 alert / confirm（A-class: no-alert）──────────────
  // no-alert 涵蓋 alert() + confirm() + prompt()，跨所有 file group 一致
  {
    files: ["web/static/js/**/*.js"],
    rules: {
      "no-alert": "error",
    },
  },

  // ── search 頁面禁 console.log（A-class: no-console）──────────
  {
    files: ["web/static/js/pages/search/**/*.js"],
    rules: {
      "no-console": ["error", { allow: ["error", "warn"] }],
    },
  },

  // ── no-restricted-syntax：依 file group 切三段，避免覆蓋 ─────
  //
  // Group 1: search/state/** — createElement + showModal + window.confirm（最嚴）
  {
    files: ["web/static/js/pages/search/state/**/*.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_CREATE_ELEMENT,
        SEL_SHOW_MODAL,
        SEL_WINDOW_CONFIRM,
      ],
    },
  },

  // Group 2: 其他 state/** — createElement + window.confirm（不含 showModal）
  {
    files: ["web/static/js/pages/**/state/**/*.js"],
    ignores: ["web/static/js/pages/search/state/**/*.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_CREATE_ELEMENT,
        SEL_WINDOW_CONFIRM,
      ],
    },
  },

  // Group 3: 非 state/ JS — 只禁 window.confirm
  {
    files: ["web/static/js/**/*.js"],
    ignores: ["web/static/js/pages/**/state/**/*.js"],
    rules: {
      "no-restricted-syntax": ["error", SEL_WINDOW_CONFIRM],
    },
  },

  // Group 4: clip-lab thin host — 禁止核心邏輯洩漏到 thin host（CD-56B-8 lint guard）
  {
    files: ["web/static/js/pages/clip-lab/main.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Property[key.name='drawSVG']",
          message:
            "drawSVG 屬於核心層（shared/constellation/rails.js），禁止在 thin host main.js 的 GSAP property bag 直接使用。",
        },
        {
          selector: "Property[key.value='drawSVG']",
          message:
            "drawSVG 屬於核心層（shared/constellation/rails.js），禁止在 thin host main.js 直接使用（quoted key form）。",
        },
        {
          selector: "MemberExpression[property.name='drawSVG']",
          message:
            "drawSVG 屬於核心層，禁止在 thin host main.js 透過 member access 使用。",
        },
        {
          selector: "CallExpression[callee.name='railDrawIn']",
          message:
            "railDrawIn 是核心函式，thin host 只能呼叫 animations.js 的 play* 函式，不能直接呼叫 railDrawIn。",
        },
      ],
    },
  },

  // Group 5: animations.js 禁直接 setAttribute('x2')（rail endpoint 必須經 rails.js setRailCoords）
  {
    files: ["web/static/js/shared/constellation/animations.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "CallExpression[callee.property.name='setAttribute'][arguments.0.value='x2']",
          message:
            "SVG rail x2 屬性只能在 rails.js（setRailCoords）或 breathing.js（ticker follow）內設定，不在 animations.js 直接 setAttribute。",
        },
      ],
    },
  },
];
