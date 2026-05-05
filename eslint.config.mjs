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

// ── CD-56B-T2 共用 selector 物件 ────────────────────────────────
const SEL_BREATHING_MANAGER_NEW = {
  selector: "NewExpression[callee.name='BreathingManager']",
  message:
    "BreathingManager 只能在 pages/clip-lab/main.js 建立實例（host lifecycle 持有原則）。其他模組禁止直接 new BreathingManager（CD-56B-T2 lint guard）。",
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

  // ── no-restricted-syntax：依 file group 切段，避免覆蓋 ────────
  //
  // 設計原則：每個 file group 自成一段，給出該 group 完整的 no-restricted-syntax
  // 清單（包含從上游繼承的規則），不依賴 flat config 疊加（疊加會覆蓋）。
  //
  // 覆蓋關係（後者 wins）：
  //   Group 1 > Group 2 for search/state/**
  //   Group 3 > Group 1/2 for 非 state JS（Group 3 後，但 ignores state/**）
  //   Group 4 > Group 3 for animations.js（後，更具體）
  //   Group 5 > Group 3 for clip-lab/main.js（後，更具體）
  //   Group 6 > Group 3 for 其餘非 state/非 main/非 animations JS（最後）

  // Group 1: search/state/** — createElement + showModal + window.confirm + BreathingManager（最嚴）
  {
    files: ["web/static/js/pages/search/state/**/*.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_CREATE_ELEMENT,
        SEL_SHOW_MODAL,
        SEL_WINDOW_CONFIRM,
        SEL_BREATHING_MANAGER_NEW,
      ],
    },
  },

  // Group 2: 其他 state/** — createElement + window.confirm + BreathingManager（不含 showModal）
  {
    files: ["web/static/js/pages/**/state/**/*.js"],
    ignores: ["web/static/js/pages/search/state/**/*.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_CREATE_ELEMENT,
        SEL_WINDOW_CONFIRM,
        SEL_BREATHING_MANAGER_NEW,
      ],
    },
  },

  // Group 3: 非 state/ JS — 只禁 window.confirm
  // （此 group 作為 base，後面 Group 4/5/6 會對特定檔案 supersede）
  {
    files: ["web/static/js/**/*.js"],
    ignores: ["web/static/js/pages/**/state/**/*.js"],
    rules: {
      "no-restricted-syntax": ["error", SEL_WINDOW_CONFIRM],
    },
  },

  // Group 4: constellation/animations.js 完整規則集（supersedes Group 3）
  // 包含：window.confirm guard + x2 setAttribute guard（rail endpoint 必須經 rails.js）
  // + BreathingManager 實例化禁令（CD-56B-T2）
  // + starSettle caller ban（CD-T2FIX-1）：禁止 ease: 'starSettle' Property（caller 不可走回頭路）
  //   注意：CustomEase.create('starSettle', ...) 是 CallExpression Argument（Literal），
  //   不符合 Property[key.name='ease'] selector，自然白名單（register 保留供 56c 評估）
  {
    files: ["web/static/js/shared/constellation/animations.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_WINDOW_CONFIRM,
        SEL_BREATHING_MANAGER_NEW,
        {
          selector:
            "CallExpression[callee.property.name='setAttribute'][arguments.0.value='x2']",
          message:
            "SVG rail x2 屬性只能在 rails.js（setRailCoords）或 breathing.js（ticker follow）內設定，不在 animations.js 直接 setAttribute。",
        },
        {
          selector: "Property[key.name='ease'][value.value='starSettle']",
          message:
            "starSettle（CD-T2FIX-1）已退役，caller 禁止走回頭路。被點卡飛中央請改用 'fluent-decel'。CustomEase.create('starSettle', ...) 是 CallExpression Argument，自然不符合此 Property selector（允許保留 register）。",
        },
      ],
    },
  },

  // Group 5: clip-lab/main.js 完整規則集（supersedes Group 3）
  // 包含：window.confirm guard + drawSVG/railDrawIn thin-host guard（CD-56B-8）
  // + hover addEventListener guard + BreathingManager 不禁（main.js 是合法建立者）
  {
    files: ["web/static/js/pages/clip-lab/main.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_WINDOW_CONFIRM,
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
        {
          selector:
            "CallExpression[callee.property.name='addEventListener'][arguments.0.value=/^(mouseenter|mouseleave)$/]",
          message:
            "hover 互動走 Alpine x-on:mouseenter / x-on:mouseleave，禁止在 main.js 內使用 addEventListener('mouseenter'/'mouseleave')（CD-56B-T2 lint guard）。",
        },
      ],
    },
  },

  // Group 6: 其餘非 state/ 非 main.js 非 animations.js 非 breathing.js JS（supersedes Group 3）
  // 包含：window.confirm guard + BreathingManager 實例化禁令（CD-56B-T2）
  // + starSettle Literal ban（CD-T2FIX-1）：其他檔案完全不允許出現 'starSettle' 字串
  //   （animations.js 在 ignores 中，所以 CustomEase.create('starSettle') 不受此影響）
  {
    files: ["web/static/js/**/*.js"],
    ignores: [
      "web/static/js/pages/**/state/**/*.js",
      "web/static/js/pages/clip-lab/main.js",
      "web/static/js/shared/constellation/animations.js",
      "web/static/js/shared/constellation/breathing.js",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        SEL_WINDOW_CONFIRM,
        SEL_BREATHING_MANAGER_NEW,
        {
          selector: "Literal[value='starSettle']",
          message:
            "starSettle（CD-T2FIX-1）已退役。其他檔案禁止出現 'starSettle' 字串。register 保留在 animations.js（由 Group 4 白名單保護）。",
        },
      ],
    },
  },
];
