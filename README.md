# zfsdu

`zfsdu` is an `ncdu`-inspired terminal browser for ZFS datasets, volumes, and snapshots.
It uses `zfs list` metadata directly (no filesystem walking), so it stays fast on large installations.

## Features

- Interactive Textual TUI with keyboard-first workflow
- Dataset tree browsing with usage metrics (`used`, `refer`, snapshot usage)
- Sorting by `used`, `refer`, snapshot usage, or name
- Fast case-insensitive dataset search
- Snapshot visibility toggle
- IEC, decimal, and raw-byte size display modes
- Graceful command errors (missing `zfs`, invalid dataset root, permission failures)

## Install (uv)

```bash
uv sync
```

For development tools (`pytest`, `ruff`, `mypy`):

```bash
uv sync --extra dev
```

Optional pip fallback:

```bash
python -m pip install -e '.[dev]'
```

## Usage

```bash
uv run zfsdu
uv run zfsdu tank
uv run zfsdu tank/backups --types filesystem,volume --sort refer
uv run zfsdu --types all --show-snapshots -p
uv run zfsdu --color never
```

### CLI options

- `root` positional dataset root (optional)
- `--types filesystem,volume,snapshot|all`
- `--sort used|refer|snapshot|name`
- `-H, --human` IEC units (default)
- `-D, --human-decimal` decimal units
- `-p, --parsable` raw bytes
- `--color auto|always|never`
- `--show-snapshots` show snapshots initially

### Keybindings

- `q` quit
- `r` refresh ZFS data
- `s` cycle sort metric
- `m` cycle size display mode
- `t` toggle snapshot visibility
- `/` search datasets (Enter to jump)

## Architecture

- `src/zfsdu/cli.py`: argument parsing and app bootstrap
- `src/zfsdu/zfs.py`: ZFS command integration and parsing
- `src/zfsdu/models.py`: typed domain models and enums
- `src/zfsdu/tree.py`: index, tree relations, sorting, and search
- `src/zfsdu/formatters.py`: size and percentage formatting
- `src/zfsdu/ui/app.py`: Textual application

## Testing

```bash
uv run pytest
```

## Notes on performance

- Uses one `zfs list` invocation with machine-parsable output (`-H -p`).
- Builds an in-memory index (`name -> entry`, `parent -> children`) for O(1)-style lookups.
- Avoids filesystem scans and `du` entirely.
- Supports large trees with filtering and search over metadata.

