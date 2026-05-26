# fastvex schema v2 design

This document records the agreed design for `fastvex.yaml` schema v2 and the
matching CLI behavior. It is a design target, not a statement that the current
implementation already supports every item.

## Goals

- Make `fastvex.yaml` a shared deployment plan that can be reviewed in Git.
- Keep local runtime state and tool preferences out of the shared YAML.
- Make every V5 Brain slot explicit.
- Make `deploy` choose only slots or slot groups; profile and route are defined
  in YAML.
- Prefer predictable, inspectable behavior over implicit defaults.

## File Layout

```text
fastvex.yaml              # shared deployment plan, committed
.fastvex/.gitignore       # committed
.fastvex/state.json       # local runtime state, ignored
.fastvex/settings.json    # local tool preferences, ignored
```

`.fastvex/.gitignore` should contain:

```gitignore
*
!.gitignore
```

`fastvex init` creates all four files. Existing files are not overwritten unless
`--force` is passed. With `--force`, the old file is backed up first using a
timestamped name such as `fastvex.backup.20260526-143000.yaml`.

## Example

```yaml
schemaVersion: 2

robot:
  name: Amethyst
  team: HITSZ1

programName:
  template: "{profile}-{route}-{robot}"

alliances:
  red:
    routes:
      left:
        buildArgs:
          ROUTE: 1
      right:
        buildArgs:
          ROUTE: 2

  blue:
    routes:
      left:
        buildArgs:
          ROUTE: 1
      right:
        buildArgs:
          ROUTE: 2

  skill:
    routes:
      main:
        buildArgs:
          ROUTE: 0

profiles:
  redComp:
    alliance: red
    buildArgs:
      MODE: RED_COMP

  blueComp:
    alliance: blue
    buildArgs:
      MODE: BLUE_COMP

  skillComp:
    alliance: skill
    buildArgs:
      MODE: SKILL_COMP

  redDebug:
    alliance: red
    buildArgs:
      MODE: RED_DEBUG

  blueDebug:
    alliance: blue
    buildArgs:
      MODE: BLUE_DEBUG

slots:
  1:
    profile: redComp
    route: left
  2:
    profile: blueComp
    route: right
  3:
    profile: skillComp
    route: main
  4:
    profile: redDebug
    route: left
  5:
    profile: blueDebug
    route: right
  6: empty
  7: empty
  8: empty

slotGroups:
  all: [1, 2, 3, 4, 5, 6, 7, 8]
```

## Naming Rules

fastvex-owned YAML fields and reference keys use lower camel case.

Keys under `alliances`, `routes`, `profiles`, and `slotGroups` must match:

```text
[a-z][A-Za-z0-9]*
```

`red`, `blue`, and `skill` are built-in preferred alliance names. `skill` is
allowed under `alliances` even though it is not literally an alliance. Custom
alliances and custom profiles are allowed.

`buildArgs` keys must match make-variable style:

```text
[A-Za-z_][A-Za-z0-9_]*
```

`buildArgs` values may be strings or numbers. They are normalized to strings.
Booleans, lists, and objects are invalid.

`robot.name` is required. `robot.team` is optional. They are normal strings and
do not use the key naming rule.

## Schema Rules

Top-level `schemaVersion: 2` is required.

`alliances` defines route sets. Each route may have `buildArgs`. Empty route
`buildArgs` are allowed but should produce a warning.

`profiles` defines buildable program types. Each profile must have an explicit
`alliance`. `buildArgs` are optional, but an empty profile `buildArgs` should
produce a warning. `MODE` is not a special schema field; it is just a normal
build arg used by the default template.

`slots` must define all slots `1..8`. A slot is either:

```yaml
1: empty
```

or:

```yaml
1:
  profile: redComp
  route: left
```

Non-empty slots must contain both `profile` and `route`. No shorthand form such
as `1: redComp:left` is allowed.

The slot route is resolved through the selected profile:

```text
slot.profile -> profiles[profile].alliance -> alliances[alliance].routes[slot.route]
```

Slots may not define `buildArgs`, `programName`, `enabled`, or other behavior.
Profile inheritance such as `extends` is not supported. YAML anchors are not
documented or encouraged, but parsed YAML that resolves to a valid schema is
accepted. Environment variable expansion is not supported; `${NAME}` is an
ordinary string.

`slotGroups` is optional in the schema but the default generated config includes:

```yaml
slotGroups:
  all: [1, 2, 3, 4, 5, 6, 7, 8]
```

Slot groups contain only numeric slot lists. Nested group references are not
allowed. `slotGroups.all` may be edited; if it is missing or not complete
`1..8`, `validate` warns but does not fail.

## Build Args

The final build args for a slot are:

```text
profile buildArgs < route buildArgs
```

Route args override profile args with the same key. Such overrides are warnings,
not errors.

The final command arg order is stable:

```text
profile buildArgs in YAML order, then route buildArgs in YAML order
```

If a later source overrides an earlier key, the final output contains that key
only once in its later position.

CLI build arg overrides are not supported in v2.

## Program Name

The default program name template is:

```yaml
programName:
  template: "{profile}-{route}-{robot}"
```

The same default is built in, but `fastvex init` writes it explicitly.

Allowed placeholders are:

```text
{robot}
{team}
{profile}
{alliance}
{route}
{slot}
```

Only simple `{name}` placeholders are supported. Unknown placeholders are errors.
Known placeholders with missing values are errors, for example `{team}` when
`robot.team` is not set. `{slot}` expands to the slot number as a plain string.

Program names are generated by replacing placeholders first, then cleaning the
entire result:

- trim leading and trailing whitespace
- convert whitespace to `-`
- convert unusual characters to `-`
- collapse repeated `-`
- keep only letters, numbers, `-`, `_`, and `.`

If the cleaned name is empty, that is an error. If it exceeds 32 characters,
`validate` warns and `deploy` shows the warning before confirmation. `show` and
`deploy --dry-run` display the cleaned final program name.

No profile, route, or slot-level program name alias is supported in v2.

## CLI

The v2 command set is:

```text
fastvex                 # interactive deploy flow
fastvex init
fastvex validate
fastvex show
fastvex deploy
fastvex status
fastvex history
fastvex migrate
fastvex toolchain
```

`upload` is removed. `route set` is removed. Route information is shown as part
of `show`; there is no standalone `route` subcommand.

`show` displays the parsed deployment plan as a slot table:

```text
Slot  Profile    Alliance  Route  ProgramName
1     redComp    red       left   redComp-left-Amethyst
2     blueComp   blue      right  blueComp-right-Amethyst
6     empty
```

`status` displays local recorded slot status from `.fastvex/state.json` as a
slot table and must state that it is not read live from the Brain.

`history` displays prior executions.

`validate` prints only problems. With no errors or warnings it may print `OK`.
Warnings do not affect the exit code; errors do.

## Deploy

`deploy` chooses only target slots. It does not choose routes.

Valid target forms:

```powershell
fastvex deploy --slots 1,2,3
fastvex deploy --slots "1 2 3"
fastvex deploy --group all
```

`--slots` and `--group` are mutually exclusive. Only one `--group` is allowed.
There is no `--all`; use `--group all`.

If no target is specified, `deploy` errors.

Slot order follows user input:

- `--slots 3,1` deploys slot 3 before slot 1
- `--group comp` follows the order in `slotGroups.comp`
- duplicate slots are de-duplicated, preserving the first occurrence, with a
  warning

If `--slots` explicitly names an `empty` slot, that is an error. If a group
includes `empty` slots, they are skipped with a message. If all selected slots
are skipped, deploy errors.

`deploy` runs validation before executing. Errors block deploy. Warnings are
shown before confirmation and do not block.

Deploy normally asks for confirmation. `-y` / `--yes` skips confirmation.

Before confirmation, deploy displays the plan grouped as build -> slots:

```text
Build redComp:left
  args: MODE=RED_COMP ROUTE=1
  upload:
    slot 1 -> redComp-left-Amethyst
    slot 4 -> redComp-left-Amethyst
```

`--dry-run` displays the same plan, does not ask for confirmation, does not run
build/upload commands, and does not write state.

The interactive command `fastvex` displays the configuration overview, asks for
slots or a group name, then confirms before deploying. Empty input cancels. In
interactive confirmation prompts, Enter defaults to yes, and typing `y` or `n`
confirms immediately without requiring Enter.

## Build and Upload Execution

The build signature is:

```text
profile key + route key + normalized ordered buildArgs
```

The normalized state form is structured and ordered:

```json
{
  "profile": "redComp",
  "route": "left",
  "buildArgs": [
    {"name": "MODE", "value": "RED_COMP"},
    {"name": "ROUTE", "value": "1"}
  ]
}
```

Within one deploy, identical build signatures are built once and uploaded to all
selected slots that need them. If two different profiles happen to have the same
build args, they are not reused unless the profile key and route key also match.

Touch invalidation is based on the local previous build, not only the current
deploy plan:

```text
if current buildSignature != state.lastBuildSignature:
    touch compile-time dependent sources
else:
    do not touch
```

After a successful build, update `state.lastBuildSignature`.

If `--clean` is passed, run clean before each actual build. Reused signatures
that are not rebuilt do not run clean again.

If a build fails, planned uploads for that build are recorded as skipped with
reason `buildFailed`. Other independent builds and uploads continue. If one
upload fails, later uploads continue. The final exit code is non-zero when any
requested build/upload fails or is skipped due to failure.

Execution history should model actual reuse:

```json
{
  "builds": [
    {
      "id": "build-1",
      "signature": {},
      "command": ["pros", "make", "MODE=RED_COMP", "ROUTE=1"],
      "ok": true
    }
  ],
  "uploads": [
    {
      "slot": 1,
      "buildId": "build-1",
      "programName": "redComp-left-Amethyst",
      "status": "success"
    },
    {
      "slot": 4,
      "buildId": "build-1",
      "programName": "redComp-left-Amethyst",
      "status": "success"
    }
  ]
}
```

## Local Settings and State

`.fastvex/settings.json` defaults to:

```json
{
  "historyRetentionCount": 10
}
```

If settings are missing, use defaults and recreate when appropriate. If settings
JSON is corrupt, error. Unknown settings fields produce warnings.

`.fastvex/state.json` stores local runtime data such as history, recorded slot
status, `lastPort`, and `lastBuildSignature`. If state JSON is corrupt, back it
up and recreate it:

```text
.fastvex/state.corrupt.20260526-143000.json
```

`--port` is retained as a local connection option:

```text
CLI --port > state.lastPort > PROS auto-detection
```

If the user explicitly passes `--port`, write it to `state.lastPort` whether the
deploy succeeds or fails. `robot.name` cannot be overridden from CLI.

## Migration

Legacy `vex_upload_config.yaml` is used only by `fastvex migrate`, not by v2
`deploy`, `show`, or `validate`.

If normal commands find schema v1, they error with a migration hint:

```text
fastvex.yaml uses schemaVersion 1. Run: fastvex migrate
```

`fastvex migrate` can read v1 `fastvex.yaml` or legacy
`vex_upload_config.yaml`. It does not perform silent in-place migration.

Default behavior:

```powershell
fastvex migrate
```

creates:

```text
fastvex.v2.yaml
```

and does not overwrite the original file.

Other forms:

```powershell
fastvex migrate --output fastvex.new.yaml
fastvex migrate --write
```

`--write` replaces `fastvex.yaml` only after creating a timestamped v1 backup,
such as:

```text
fastvex.v1.backup.20260526-143000.yaml
```

Migration always writes:

```yaml
slotGroups:
  all: [1, 2, 3, 4, 5, 6, 7, 8]
```

The generated v2 file should be treated as a draft for user review because the
schema change is conceptual, especially around explicit `profile + route` slots.
