# Local `blink1-tool`

Put the [`blink1-tool`](https://github.com/todbot/blink1) executable here as `blink1-tool` (this path is gitignored), or install system-wide:

```bash
brew install blink1
```

To use the copy in this folder without installing globally, add to your shell profile:

```bash
export PATH="/path/to/livewebcam/bin:$PATH"
```

Or symlink into `~/bin`:

```bash
ln -sf /path/to/livewebcam/bin/blink1-tool ~/bin/blink1-tool
```
