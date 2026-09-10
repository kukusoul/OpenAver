// empty-explainer.js — 搜尋頁空狀態四行說明（CD-146a-16，spec-146a §6.2）。
// mergeState 分片（CD-146a-19 決定不做獨立 Alpine 元件），本檔**不得定義 init()**
// （FE-ALPINE-05：後定義的 init() 會覆蓋先前的，state-browse-dir.js 同一條約束的先例）。
// 資料載入（formatVariables／favoriteScannerLinked 的 fetch）放在 search-flow.js 既有的
// loadAppConfig() 裡（CD-146a-17），本檔只放純讀取的 method，且一律回傳純文字（不組 HTML
// 字串、不餵 x-html——CD-146a-16 事實訂正：window.t() 的 {param} 插值不 escape，動態值只能
// 走 x-text）。

import { buildNamingPreview } from '@/shared/naming-preview.js';

export function searchStateEmptyExplainer() {
    return {
        favoriteConfigured() {
            const folder = (this.appConfig && this.appConfig.search && this.appConfig.search.favorite_folder) || '';
            return !!folder.trim();
        },

        favoritePathDisplay() {
            const folder = (this.appConfig && this.appConfig.search && this.appConfig.search.favorite_folder) || '';
            // search.favorite_folder 是使用者輸入框當初打的原生路徑字串（非 file:/// URI，
            // 見 CD-146a-14 settings_link.py 現況註解「favorite 從 query param 取得（input
            // 即時值）」），pathToDisplay 對已是原生格式（Windows 反斜線/UNC/POSIX）的輸入是
            // no-op（頭部 file:/// 前綴不存在時 .replace 不匹配，後續判斷原樣通過），故可直接
            // 傳入，不需要先包一層 to_file_uri 往返。
            return window.pathToDisplay ? window.pathToDisplay(folder) : folder;
        },

        namingPreviewExample() {
            const scraper = (this.appConfig && this.appConfig.scraper) || {};
            const tokens = {};
            for (const v of this.formatVariables || []) {
                const name = v.name.slice(1, -1);
                tokens[name] = window.t('settings.var.' + name);
            }
            return buildNamingPreview({
                filenameFormat: scraper.filename_format,
                createFolder: scraper.create_folder,
                folderLayerList: scraper.create_folder ? (scraper.folder_layers || []) : [],
                formatVariables: this.formatVariables,
                tokens,
            });
        },
    };
}
