# zfsdu

`zfsdu` is an `ncdu`-inspired terminal browser for ZFS datasets, volumes, and snapshots.
It uses `zfs list` metadata directly (no filesystem walking), so it stays fast on large installations.

## Features

- Interactive Textual TUI with keyboard-first workflow
- `ncdu`-style browser: move up/down in a list and enter/leave datasets with `→` / `←`
- Dataset browsing with usage metrics (`used`, `refer`, snapshot usage)
- Sorting by `used`, `refer`, snapshot usage, or name with configurable direction
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
uv run zfsdu --log-level INFO --log-file /tmp/zfsdu.log
uv run zfsdu --hide-legacy-mountpoints
```

### CLI options

- `root` positional dataset root (optional)
- `--types filesystem,volume,snapshot|all`
- `--sort used|refer|snapshot|name`
- `--sort-direction asc|desc` (default: desc)
- `-H, --human` IEC units (default)
- `-D, --human-decimal` decimal units
- `-p, --parsable` raw bytes
- `--color auto|always|never`
- `--show-snapshots` show snapshots initially
- `--hide-legacy-mountpoints` hide datasets where `mountpoint=legacy`
- `--log-level DEBUG|INFO|WARNING|ERROR`
- `--log-file PATH` optionally write logs to a file

### Keybindings

- `q` quit
- `r` refresh ZFS data
- `←` leave the current dataset
- `→` or `Enter` open the selected dataset
- `s` cycle sort metric
- `Shift+s` toggle sort direction (ascending/descending)
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

## System Testing with Vagrant

Vagrant provides a full virtual machine environment for:
- System-level testing
- Running code with kernel dependencies
- Simulating production-like environments

Workflow:
```bash
# Start the Vagrant VM
vagrant up

# Connect to the VM
vagrant ssh

# Inside the VM, navigate to the project
cd ~/zfsdu

# Run uv sync to install dependencies
uv sync
uv sync --extra dev

# Activate the virtual environment
source .venv/bin/activate

# Run tests
uv run pytest
```

### Keeping Files in Sync

Use these methods to keep your local files synchronized with the Vagrant VM:

### Manual Sync
```bash
# Sync files from local to Vagrant VM
vagrant rsync
```

###### Continuous Sync
```bash
# Automatically sync files as they change
vagrant rsync-auto
```
