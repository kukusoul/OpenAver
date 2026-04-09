/**
 * Path Display Utilities (T7d)
 * 將 file:/// URI 轉換為人類可讀的顯示路徑
 *
 * 規則：
 * - Windows 路徑（drive letter）：去除前綴，/ → \
 * - UNC 路徑（//server/share）：去除前綴，/ → \
 * - Linux/其他路徑：去除前綴，保留 /
 */
window.pathToDisplay = function(fileUri) {
    if (!fileUri) return '';
    const stripped = fileUri.replace(/^file:\/\/\//, '');
    if (/^[A-Za-z]:/.test(stripped)) return stripped.replace(/\//g, '\\');
    if (stripped.startsWith('//')) return stripped.replace(/\//g, '\\');
    return stripped;
};

/**
 * 將原生 FS 路徑轉換為 file:/// URI（Zone 1 → Zone 2）(41b-T3)
 *
 * 規則：
 * - 空值 → 回傳 ''
 * - 已是 file:/// → 原樣回傳（idempotent）
 * - Windows 路徑（C:\... 或 C:/...）→ 反斜線換正斜線，加 file:///
 * - UNC 路徑（\\server\share）→ 換正斜線，加 file://（不加第三個 /）
 * - Linux 路徑（/home/...）→ 加 file:// （ file:// + /home = file:///home ）
 */
window.pathToFileUri = function(nativePath) {
    if (!nativePath) return '';
    if (nativePath.startsWith('file://')) return nativePath;
    // Windows UNC: \\server\share\...
    if (nativePath.startsWith('\\\\')) {
        return 'file://' + nativePath.replace(/\\/g, '/').slice(2);
    }
    // Windows drive: C:\... or C:/...
    if (/^[A-Za-z]:[/\\]/.test(nativePath)) {
        return 'file:///' + nativePath.replace(/\\/g, '/');
    }
    // Linux / macOS: /home/...
    if (nativePath.startsWith('/')) {
        return 'file://' + nativePath;
    }
    // Fallback: return as-is
    return nativePath;
};
