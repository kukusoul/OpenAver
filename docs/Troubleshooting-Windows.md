# OpenAver Windows Troubleshooting

> 💡 If you used the recommended **one-line install**, most issues below do not apply. This document is for manual ZIP installs only.

---

## Upgrading (ZIP Manual Install)

Overlaying a new ZIP can leave stale Python packages behind, causing startup failures. **Before upgrading, delete the `python` folder**:

- **Windows**: Delete `%USERPROFILE%\OpenAver\python\`

After deleting, extract the new ZIP and run `OpenAver.bat` to launch.

---

## Windows — App Won't Start / Crashes

**Cause**: Windows Mark of the Web blocks downloaded executables.

**Fix**:
1. Right-click the downloaded ZIP → **Properties**
2. Check **Unblock** → OK
3. Re-extract and run `OpenAver.bat`

*Alternatively, extract with 7-Zip to bypass this restriction.*

**Startup scripts**:
- `OpenAver.bat` — Normal launch
- `OpenAver_Debug.bat` — Debug launch (verbose logging), log file: `%USERPROFILE%\OpenAver\logs\debug.log`

---

## Blank UI / Missing Effects

**Cause**: Missing WebView2 Runtime (common on Windows 10 and VMs).

**Fix**: Download and install the [Microsoft Edge WebView2 Runtime](https://go.microsoft.com/fwlink/p/?LinkId=2124703).

---

## Reporting Issues

**When reporting**: include a description, steps to reproduce, OS version, and log file (run `OpenAver_Debug.bat` to generate one).

| Channel | Best For |
|---------|----------|
| [GitHub Issues](https://github.com/slive777/OpenAver/issues) | Bug reports, feature requests |
| [Telegram group](https://t.me/+J-U2l96gv0FjZTBl) | Privacy-sensitive issues, direct screenshot/video uploads |
