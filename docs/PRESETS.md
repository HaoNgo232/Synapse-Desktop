# Context Presets

Save selected files + instructions + output format as a preset. When you need to repeat the same task, select the preset instead of re-ticking each file.

## Features

- **Save current selection** as a named preset
- **Auto-load** preset when selected from dropdown
- **Update existing** presets with current selection
- **Duplicate** presets for variations
- **Rename** presets
- **Delete** presets with confirmation
- **Dirty state indicator** (`*`) shows when selection differs from loaded preset
- **Keyboard shortcuts** for quick access
- **Portable** - presets stored as relative paths in workspace

## Usage

### Creating a Preset

1. Select files in the file tree
2. (Optional) Add instructions and select output format
3. Click the 💾 Save button
4. Enter a name for the preset
5. Click OK

**Keyboard shortcut:** `Ctrl+Shift+S` (creates new or updates active preset)

### Loading a Preset

1. Click the preset dropdown
2. Select a preset from the list
3. Files are automatically selected and instructions restored

**Keyboard shortcut:** `Ctrl+Shift+L` (focus preset dropdown)

### Updating a Preset

**Method 1:** With preset active
1. Modify file selection or instructions
2. Click 💾 Save button
3. Confirm update

**Method 2:** Quick update
- Press `Ctrl+Shift+S` when a preset is active

### Renaming a Preset

1. Select preset from dropdown
2. Click ⋮ (more options) button
3. Select "Rename..."
4. Enter new name

### Duplicating a Preset

1. Select preset from dropdown
2. Click ⋮ (more options) button
3. Select "Duplicate"
4. A copy is created with " (Copy)" suffix

### Deleting a Preset

1. Select preset from dropdown
2. Click 🗑️ Delete button
3. Confirm deletion

## Storage

Presets are stored in `.synapse_presets.json` at the workspace root.

**File paths** are stored as **relative paths** to ensure portability:
- Share presets via git by committing `.synapse_presets.json`
- Or add to `.gitignore` to keep presets personal

## Dirty State Indicator

When you modify the file selection after loading a preset, an asterisk (`*`) appears before the preset name in the dropdown. This indicates the current selection differs from the saved preset.

## Missing Files

If files in a preset no longer exist:
- They are automatically filtered out when loading
- A status message shows how many files are missing
- If all files are missing, loading fails with an error

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+S` | Quick save (update active preset or create new) |
| `Ctrl+Shift+L` | Focus preset dropdown |

## Technical Details

### File Format

```json
{
  "version": 1,
  "presets": {
    "abc123": {
      "name": "Backend API",
      "selected_paths": ["src/api/routes.py", "src/models.py"],
      "instructions": "Refactor authentication",
      "output_format": "synapse_xml",
      "created_at": "2026-03-03T19:00:00",
      "updated_at": "2026-03-03T19:30:00"
    }
  }
}
```

### Architecture

- **PresetStore** (`services/preset_store.py`) - Data layer, CRUD operations
- **PresetController** (`views/context/preset_controller.py`) - Business logic
- **PresetWidget** (`components/preset_widget.py`) - UI component

### Thread Safety

All file I/O operations are protected by `threading.Lock` to prevent race conditions.

### Atomic Writes

Presets are saved using atomic write pattern (temp file + rename) to prevent corruption.

## Troubleshooting

**Preset not appearing after save**
- Check workspace root for `.synapse_presets.json`
- Verify file permissions

**Files not loading**
- Files may have been moved or deleted
- Check status message for missing file count

**Corrupt preset file**
- Synapse automatically backs up corrupt files to `.synapse_presets.json.bak`
- Delete corrupt file and restart


