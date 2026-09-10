#!/bin/bash
set -e

REPO="slive777/OpenAver"
INSTALL_DIR="$HOME/OpenAver"

# ============ 語言判定與訊息表（CD-145b-8b／CD-145b-17）============
detect_installer_lang() {
    # CD-145b-8b：環境變數覆寫優先於系統語言，值不合法就忽略、退回系統判定。
    # 先用 tr 正規化成小寫再比對（bash 3.2 相容，禁用 bash 4 大小寫展開），
    # 讓 EN／Zh-TW 等與 PowerShell -in（大小寫不敏感）行為一致；回傳訊息表用的正規大小寫。
    local _override
    _override=$(printf '%s' "${OPENAVER_INSTALL_LANG:-}" | tr '[:upper:]' '[:lower:]')
    case "$_override" in
        zh-tw) echo "zh-TW"; return ;;
        zh-cn) echo "zh-CN"; return ;;
        ja)    echo "ja"; return ;;
        en)    echo "en"; return ;;
    esac

    local _lc="${LC_ALL:-$LANG}"
    case "$_lc" in
        zh_TW*|zh_HK*|zh_MO*) echo "zh-TW" ;;
        zh_CN*|zh_SG*)        echo "zh-CN" ;;
        ja*)                   echo "ja" ;;
        *)                      echo "en" ;;
    esac
}

LANG_KEY="$(detect_installer_lang)"

t() {
    case "${LANG_KEY}:$1" in
        zh-TW:title_banner) echo "   OpenAver 安裝程式" ;;
        zh-CN:title_banner) echo "   OpenAver 安装程序" ;;
        ja:title_banner) echo "   OpenAver インストーラー" ;;
        en:title_banner) echo "   OpenAver Installer" ;;

        zh-TW:macos_only_error) echo "❌ 此腳本僅支援 macOS" ;;
        zh-CN:macos_only_error) echo "❌ 此脚本仅支持 macOS" ;;
        ja:macos_only_error) echo "❌ このスクリプトは macOS にのみ対応しています" ;;
        en:macos_only_error) echo "❌ This script only supports macOS" ;;

        zh-TW:linux_not_packaged) echo "   Linux 目前沒有打包版本" ;;
        zh-CN:linux_not_packaged) echo "   目前没有 Linux 打包版本" ;;
        ja:linux_not_packaged) echo "   Linux 版のパッケージは現在提供されていません" ;;
        en:linux_not_packaged) echo "   No packaged version is available for Linux yet" ;;

        zh-TW:apple_silicon_only) echo "❌ 目前僅支援 Apple Silicon (M1/M2/M3/M4)" ;;
        zh-CN:apple_silicon_only) echo "❌ 目前仅支持 Apple Silicon (M1/M2/M3/M4)" ;;
        ja:apple_silicon_only) echo "❌ 現在は Apple Silicon (M1/M2/M3/M4) のみ対応しています" ;;
        en:apple_silicon_only) echo "❌ Currently only Apple Silicon (M1/M2/M3/M4) is supported" ;;

        zh-TW:detected_arch_fmt) echo "   偵測到架構: %s" ;;
        zh-CN:detected_arch_fmt) echo "   检测到的架构: %s" ;;
        ja:detected_arch_fmt) echo "   検出したアーキテクチャ: %s" ;;
        en:detected_arch_fmt) echo "   Detected architecture: %s" ;;

        zh-TW:app_running_warning) echo "⚠️  OpenAver 目前正在執行，無法覆蓋安裝。" ;;
        zh-CN:app_running_warning) echo "⚠️  OpenAver 当前正在运行，无法覆盖安装。" ;;
        ja:app_running_warning) echo "⚠️  OpenAver が実行中のため、上書きインストールできません。" ;;
        en:app_running_warning) echo "⚠️  OpenAver is currently running, cannot overwrite the installation." ;;

        zh-TW:app_running_close_continue_prompt) echo "   請關閉 OpenAver 後，按 Enter 繼續（或輸入 q 取消）" ;;
        zh-CN:app_running_close_continue_prompt) echo "   请关闭 OpenAver 后，按 Enter 继续（或输入 q 取消）" ;;
        ja:app_running_close_continue_prompt) echo "   OpenAver を終了してから Enter キーを押して続行してください（キャンセルする場合は q を入力）" ;;
        en:app_running_close_continue_prompt) echo "   Please close OpenAver, then press Enter to continue (or type q to cancel)" ;;

        zh-TW:install_cancelled) echo "取消安裝" ;;
        zh-CN:install_cancelled) echo "取消安装" ;;
        ja:install_cancelled) echo "インストールをキャンセルしました" ;;
        en:install_cancelled) echo "Installation cancelled" ;;

        zh-TW:checking_latest_version) echo "🔍 查詢最新版本..." ;;
        zh-CN:checking_latest_version) echo "🔍 正在查询最新版本..." ;;
        ja:checking_latest_version) echo "🔍 最新バージョンを確認中..." ;;
        en:checking_latest_version) echo "🔍 Checking for the latest version..." ;;

        zh-TW:github_connect_failed) echo "❌ 無法連線到 GitHub，請檢查網路" ;;
        zh-CN:github_connect_failed) echo "❌ 无法连接到 GitHub，请检查网络" ;;
        ja:github_connect_failed) echo "❌ GitHub に接続できません。ネットワークを確認してください" ;;
        en:github_connect_failed) echo "❌ Could not connect to GitHub, please check your network connection" ;;

        zh-TW:download_link_not_found) echo "❌ 找不到 macOS 下載連結" ;;
        zh-CN:download_link_not_found) echo "❌ 找不到 macOS 下载链接" ;;
        ja:download_link_not_found) echo "❌ macOS 用のダウンロードリンクが見つかりません" ;;
        en:download_link_not_found) echo "❌ Could not find the macOS download link" ;;

        zh-TW:latest_version_fmt) echo "   最新版本: %s" ;;
        zh-CN:latest_version_fmt) echo "   最新版本: %s" ;;
        ja:latest_version_fmt) echo "   最新バージョン: %s" ;;
        en:latest_version_fmt) echo "   Latest version: %s" ;;

        zh-TW:existing_install_detected_fmt) echo "⚠️  已偵測到現有安裝: %s" ;;
        zh-CN:existing_install_detected_fmt) echo "⚠️  检测到已存在的安装: %s" ;;
        ja:existing_install_detected_fmt) echo "⚠️  既存のインストールを検出しました: %s" ;;
        en:existing_install_detected_fmt) echo "⚠️  Existing installation detected: %s" ;;

        zh-TW:overwrite_confirm_prompt) echo "   是否覆蓋安裝？(y/N) " ;;
        zh-CN:overwrite_confirm_prompt) echo "   是否覆盖安装？(y/N) " ;;
        ja:overwrite_confirm_prompt) echo "   上書きインストールしますか？(y/N) " ;;
        en:overwrite_confirm_prompt) echo "   Overwrite the existing installation? (y/N) " ;;

        zh-TW:downloading_fmt) echo "📦 下載 %s..." ;;
        zh-CN:downloading_fmt) echo "📦 正在下载 %s..." ;;
        ja:downloading_fmt) echo "📦 %s をダウンロード中..." ;;
        en:downloading_fmt) echo "📦 Downloading %s..." ;;

        zh-TW:cleaning_old_python) echo "🧹 清除舊版 Python runtime..." ;;
        zh-CN:cleaning_old_python) echo "🧹 正在清除旧版 Python 运行时..." ;;
        ja:cleaning_old_python) echo "🧹 古いバージョンの Python ランタイムを削除中..." ;;
        en:cleaning_old_python) echo "🧹 Removing old Python runtime..." ;;

        zh-TW:installing_to_fmt) echo "📂 安裝到 %s..." ;;
        zh-CN:installing_to_fmt) echo "📂 正在安装到 %s..." ;;
        ja:installing_to_fmt) echo "📂 %s にインストール中..." ;;
        en:installing_to_fmt) echo "📂 Installing to %s..." ;;

        zh-TW:removing_security_restrictions) echo "🔓 移除 macOS 安全限制..." ;;
        zh-CN:removing_security_restrictions) echo "🔓 正在移除 macOS 安全限制..." ;;
        ja:removing_security_restrictions) echo "🔓 macOS のセキュリティ制限を解除中..." ;;
        en:removing_security_restrictions) echo "🔓 Removing macOS security restrictions..." ;;

        zh-TW:install_complete) echo "✅ 安裝完成！" ;;
        zh-CN:install_complete) echo "✅ 安装完成！" ;;
        ja:install_complete) echo "✅ インストールが完了しました！" ;;
        en:install_complete) echo "✅ Installation complete!" ;;

        zh-TW:launch_instructions_header) echo "   啟動方式：" ;;
        zh-CN:launch_instructions_header) echo "   启动方式：" ;;
        ja:launch_instructions_header) echo "   起動方法：" ;;
        en:launch_instructions_header) echo "   How to launch:" ;;

        zh-TW:launch_instruction_1) echo "   1. 雙擊 ~/OpenAver/OpenAver.command" ;;
        zh-CN:launch_instruction_1) echo "   1. 双击 ~/OpenAver/OpenAver.command" ;;
        ja:launch_instruction_1) echo "   1. ~/OpenAver/OpenAver.command をダブルクリック" ;;
        en:launch_instruction_1) echo "   1. Double-click ~/OpenAver/OpenAver.command" ;;

        zh-TW:launch_instruction_2) echo "   2. 或在 Terminal 執行: ~/OpenAver/OpenAver.command" ;;
        zh-CN:launch_instruction_2) echo "   2. 或在 Terminal 中运行: ~/OpenAver/OpenAver.command" ;;
        ja:launch_instruction_2) echo "   2. または Terminal で実行: ~/OpenAver/OpenAver.command" ;;
        en:launch_instruction_2) echo "   2. Or run it from Terminal: ~/OpenAver/OpenAver.command" ;;

        *) echo "[missing:$1]" ;;
    esac
}

echo ""
echo "=============================="
echo "$(t title_banner)"
echo "=============================="
echo ""

# --- 偵測 OS ---
if [[ "$(uname)" != "Darwin" ]]; then
    echo "$(t macos_only_error)"
    echo "$(t linux_not_packaged)"
    exit 1
fi

# --- 偵測架構 ---
ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    echo "$(t apple_silicon_only)"
    printf "$(t detected_arch_fmt)\n" "$ARCH"
    exit 1
fi

# --- OpenAver 執行中偵測 ---
# macOS rm 對 advisory lock 不會 fail，故 rm 成敗不是權威信號，pgrep 才是。
is_openaver_running() {
    # 權威信號：app 一律以 python3 -c "...from windows.standalone import main..." 啟動。
    # 不能靠 OpenAver.command（wrapper 用 nohup & 後即 exit、不在 process list），
    # 也不能靠絕對路徑 python（argv[0] 是相對的 ./python/bin/python3 → false negative）。
    # 改抓 -c 內這串 OpenAver 獨有、與安裝位置無關的字串。
    pgrep -f "from windows.standalone import main" > /dev/null 2>&1 || \
    pgrep -f "$INSTALL_DIR/python/bin" > /dev/null 2>&1
}

# 提醒關閉並等待（Enter 重試 / q 取消），不強殺；不必重跑整條指令
wait_openaver_closed() {
    while is_openaver_running; do
        echo ""
        echo "$(t app_running_warning)"
        echo "$(t app_running_close_continue_prompt)"
        local REPLY
        read -r REPLY < /dev/tty
        if [[ "$REPLY" == "q" || "$REPLY" == "Q" ]]; then
            echo "$(t install_cancelled)"
            exit 0
        fi
    done
}

# --- 查詢最新版本 ---
echo "$(t checking_latest_version)"
RELEASE_JSON=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest") || {
    echo "$(t github_connect_failed)"
    exit 1
}

VERSION=$(echo "$RELEASE_JSON" | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)
DOWNLOAD_URL=$(echo "$RELEASE_JSON" | grep -o '"browser_download_url": *"[^"]*macOS-arm64[^"]*\.zip"' | head -1 | cut -d'"' -f4)

if [[ -z "$DOWNLOAD_URL" ]]; then
    echo "$(t download_link_not_found)"
    exit 1
fi

printf "$(t latest_version_fmt)\n" "$VERSION"

# --- 檢查現有安裝 ---
if [[ -d "$INSTALL_DIR" ]]; then
    echo ""
    printf "$(t existing_install_detected_fmt)\n" "$INSTALL_DIR"
    read -p "$(t overwrite_confirm_prompt)" -n 1 -r REPLY < /dev/tty
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "$(t install_cancelled)"
        exit 0
    fi

    # 下載前提早偵測：OpenAver 在跑就先擋，省得白下載才被卡
    wait_openaver_closed
fi

# --- 下載 ---
echo ""
printf "$(t downloading_fmt)\n" "$VERSION"
TMP_DIR=$(mktemp -d)
TMP_ZIP="$TMP_DIR/OpenAver.zip"
curl -fSL --progress-bar "$DOWNLOAD_URL" -o "$TMP_ZIP"

# --- 清除舊版 embedded Python（避免套件混版）---
# macOS rm 對 advisory lock 不會 fail，必須事前用 pgrep 攔截，否則會悄悄混版。
# 權威信號＝pgrep；仍在跑就提醒關閉並等待（不重跑指令、不強殺）後再 rm。
if [[ -d "$INSTALL_DIR/python" ]]; then
    wait_openaver_closed
    echo "$(t cleaning_old_python)"
    rm -rf "$INSTALL_DIR/python"
fi

# --- 解壓安裝（覆蓋程式檔案，保留用戶資料）---
printf "$(t installing_to_fmt)\n" "$INSTALL_DIR"
unzip -o -q "$TMP_ZIP" -d "$HOME"

# --- 移除 macOS 安全限制 ---
echo "$(t removing_security_restrictions)"
xattr -dr com.apple.quarantine "$INSTALL_DIR" 2>/dev/null || true
chmod +x "$INSTALL_DIR/OpenAver.command"

# --- 清理暫存 ---
rm -rf "$TMP_DIR"

# --- 完成 ---
echo ""
echo "$(t install_complete)"
echo ""
echo "$(t launch_instructions_header)"
echo "$(t launch_instruction_1)"
echo "$(t launch_instruction_2)"
echo ""
