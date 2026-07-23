# `hotirjam` launcher

Single-command macOS start for HOTIRJAM AI 5 (no menu).

```bash
cd HOTIRJAM_AI_5
./bin/hotirjam
```

Optional PATH alias:

```bash
sudo ln -sf "$(pwd)/bin/hotirjam" /usr/local/bin/hotirjam
hotirjam
```

Starts Bridge Receiver → waits for `:8765/health` → starts Live Validator.  
Exits `0` on success, non-zero on failure.

> On macOS the script cannot be named `HOTIRJAM_AI_5/hotirjam` because that path
> collides with the `HOTIRJAM/` journal folder (case-insensitive disk).
