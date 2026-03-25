# PythonEditorUtility Project Layout Example

This folder contains a plugin-local copy of the project layout that PythonEditorUtility normally works with.

It shows the expected structure and file relationships in one place under the plugin root.
The files here are snapshots of the real project-owned files used by PythonEditorUtility.

If you are new to PythonEditorUtility, this is the fastest way to understand how the plugin normally interacts with project-owned files outside the plugin itself.

Use this folder when you want to:

- see how `PEU/PythonEditorUtility/` is normally organized
- see which `Scripts/` files PythonEditorUtility depends on
- understand how the plugin, project Python layer, UI definitions, and scripts fit together
- share the expected layout without sending people through multiple top-level folders first

## Layout Overview

Included structure:

- `PEU/PythonEditorUtility/Python/PythonEditorUtility/`
- `PEU/PythonEditorUtility/UI/`
- `PEU/PythonEditorUtility/State/`
- `Scripts/`

Tree view:

```text
ProjectLayout/
|-- PEU/
|   `-- PythonEditorUtility/
|       |-- Python/
|       |   `-- PythonEditorUtility/
|       |       |-- BuildLightingTool.py
|       |       |-- LightmapResolutionTool.py
|       |       |-- StaticMeshPipelineTool.py
|       |       `-- __init__.py
|       |-- State/
|       |   `-- README.md
|       `-- UI/
|           |-- BuildLightingTool.json
|           `-- LightmapResolutionTool.json
`-- Scripts/
    |-- audit_static_mesh_lightmaps.py
    |-- build_level_lighting.py
    |-- bulk_export_static_meshes.py
    |-- bulk_reimport_static_meshes.py
    |-- project_path_utils.py
    |-- UE_Lightmap_UV_Fixer.py
    `-- UE_Lightmap_UV_Fixer_Batch.py
```

## What Each Area Represents

### `PEU/PythonEditorUtility/Python/PythonEditorUtility/`

This is the project-owned Python layer used by the plugin.
These files hold the tool behavior for:

- Build Lighting
- Lightmap Resolution
- Static Mesh Pipeline

When the plugin UI triggers actions, this is the layer that usually handles tool state, filtering, workflow orchestration, and calls into lower-level project scripts.

### `PEU/PythonEditorUtility/UI/`

This area contains the UI definition files used by the PEU workflows.
It is useful when you need to understand the shape of the tool UIs alongside the Python behavior layer.

### `PEU/PythonEditorUtility/State/`

In the real project, this folder is where runtime status files and JSON state snapshots are written while the tools are in use.

Inside this example layout, the folder contains a placeholder README only.
That is intentional because the real state files are generated during use and are not fixed source files.

### `Scripts/`

These are the project scripts that PythonEditorUtility commonly relies on.
They represent the backend layer that the PEU Python modules call into for actual work.

This is the most important place to inspect when you want to understand how a PEU tool reaches the lower-level project automation.

## Real Path Mapping

This example folder is a mirror of the real repository layout.
Use the table below to map example paths to the live project paths:

- Example: `Plugins/PythonEditorUtility/Examples/ProjectLayout/PEU/PythonEditorUtility/Python/PythonEditorUtility/BuildLightingTool.py`
  Real path: `PEU/PythonEditorUtility/Python/PythonEditorUtility/BuildLightingTool.py`
- Example: `Plugins/PythonEditorUtility/Examples/ProjectLayout/PEU/PythonEditorUtility/UI/BuildLightingTool.json`
  Real path: `PEU/PythonEditorUtility/UI/BuildLightingTool.json`
- Example: `Plugins/PythonEditorUtility/Examples/ProjectLayout/Scripts/build_level_lighting.py`
  Real path: `Scripts/build_level_lighting.py`

## How To Use This Folder

Use this layout copy for orientation, documentation, and code review prep.

Typical use cases:

- walk a new contributor through PythonEditorUtility without jumping across the repo first
- explain where the plugin stops and project-owned Python begins
- show which backend scripts are part of the normal tool flow
- compare the copied structure against the real project files while debugging or extending a tool

Recommended reading order:

1. Start with the plugin README.
2. Open the copied Python tool modules under `PEU/PythonEditorUtility/Python/PythonEditorUtility/`.
3. Open the related files under `Scripts/`.
4. Compare the copied files to the real repository paths when making actual code changes.

Important notes:

- This folder is a documentation-oriented project layout copy.
- PythonEditorUtility does not load files from this folder automatically.
- Runtime behavior still comes from the real project paths at the repository root.
- The empty `State/` folder is included only to show the expected structure because those files are normally generated at runtime.

## Updating The Copy

If the real PythonEditorUtility project layout changes, refresh this example folder so it continues to represent the normal structure accurately.

Treat this folder as documentation that mirrors the current project state, not as the live source of truth.
