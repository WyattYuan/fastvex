# fastvex

`fastvex` is a VEX V5/PROS helper for slot-oriented build and upload workflows.
It reads a robot-project-local `fastvex.yaml`, builds each requested profile, uploads it to
the selected V5 Brain slot, and stores local run state under `.fastvex/state.json`.

## Usage

From a robot project containing `fastvex.yaml`:

```powershell
fastvex validate
fastvex show
fastvex upload --slots 1,3 -y
fastvex route show
fastvex route set red r1
```

For local development of this package:

```powershell
uv sync
uv run pytest
uv run fastvex validate --config D:\path\to\robot\fastvex.yaml
```

The legacy config name `vex_upload_config.yaml` is still readable, but new projects should
use `fastvex.yaml`.
