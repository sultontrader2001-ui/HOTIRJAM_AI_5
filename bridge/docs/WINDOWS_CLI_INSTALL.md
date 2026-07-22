# Windows CLI install — Bridge Sender / Receiver

## Symptom

```text
CommandNotFoundException: bridge_sender
CommandNotFoundException: hotirjam-bridge-sender
```

## Root causes (most common first)

1. **`pip install -e .` run from wrong directory**  
   `HOTIRJAM_AI_5/` installs **hotirjam-ai5** only — it does **not** register `bridge_sender`.  
   Correct directory: **`HOTIRJAM_AI_5/bridge/`** (package name `hotirjam-bridge`).

2. **Scripts folder not on PATH**  
   After install, Windows creates:
   `...\Python3x\Scripts\bridge_sender.exe`  
   `...\Python3x\Scripts\hotirjam-bridge-sender.exe`  
   (or `.venv\Scripts\` if using a venv).  
   PowerShell only finds them if that folder is on `PATH` / venv is activated.

3. **Wrong Python**  
   Installed into Python A, but PowerShell uses Python B.

## Fix (recommended)

In PowerShell:

```powershell
cd C:\path\to\HOTIRJAM_AI_5\bridge
.\install_windows.ps1
```

Or manually:

```powershell
cd C:\path\to\HOTIRJAM_AI_5\bridge
python -m pip install -e .
python -m hotirjam_bridge.sender --help
```

### Always-works invocations (no Scripts PATH needed)

```powershell
python -m hotirjam_bridge.sender --help
python -m hotirjam_bridge sender --help
.\hotirjam-bridge-sender.cmd --help
.\bridge_sender.cmd --help
```

### After Scripts are on PATH

```powershell
hotirjam-bridge-sender --help
bridge_sender --help
```

Find Scripts dir:

```powershell
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```

Add that path to user PATH, or activate the venv that owns it.

## Verify entry points exist

```powershell
python -c "import importlib.metadata as m; print([e.name for e in m.entry_points().select(group='console_scripts') if 'bridge' in e.name])"
```

Expected names:

- `bridge_sender`
- `hotirjam-bridge-sender`
- `bridge_receiver`
- `hotirjam-bridge-receiver`

If the list is empty, you are not using the environment where `hotirjam-bridge` was installed.
