# OpenAver macOS Troubleshooting

> 💡 If you used the recommended **one-line install**, most issues below do not apply. This document is for manual ZIP installs only.

---

## Upgrading (ZIP Manual Install)

Overlaying a new ZIP can leave stale Python packages behind, causing startup failures. **Before upgrading, delete the `python` folder**:

- **macOS**: Delete `~/OpenAver/python/`

After deleting, extract the new ZIP and run `./OpenAver.command` to launch.

---

## macOS — App Blocked by Gatekeeper

**Cause**: macOS Gatekeeper blocks unsigned applications.

Run in Terminal:
```bash
cd ~/Downloads/OpenAver
xattr -dr com.apple.quarantine .
./OpenAver.command
```

After initial setup, you can double-click `OpenAver.command` directly.

**Startup scripts**:
- `OpenAver.command` — Normal launch
- `OpenAver_Debug.command` — Debug launch, log file: `~/OpenAver/logs/debug.log`

---

## Reporting Issues

**When reporting**: include a description, steps to reproduce, macOS version, and log file (run `OpenAver_Debug.command` to generate one).

| Channel | Best For |
|---------|----------|
| [GitHub Issues](https://github.com/slive777/OpenAver/issues) | Bug reports, feature requests |
| [Telegram group](https://t.me/+J-U2l96gv0FjZTBl) | Privacy-sensitive issues, direct screenshot/video uploads |
