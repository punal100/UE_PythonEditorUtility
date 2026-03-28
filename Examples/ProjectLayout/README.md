# PythonEditorUtility Project Layout Example

This folder is a downstream integration template for the standalone PythonEditorUtility plugin.

The plugin stays framework-only. This example shows the project-owned integration files that a downstream team customizes. The rule is simple: do not modify plugin source to add project workflows.

## What This Example Demonstrates

The example now follows the same four-tool breakdown used by a production-style `PEU/` and `Scripts/` integration.

- `BuildLightingTool.json` and `BuildLightingTool.py` show the lighting summary and precheck flow.
- `LightmapResolutionTool.json` and `LightmapResolutionTool.py` show filter bindings, row selection, and table-driven actions.
- `StaticMeshPipelineTool.json` and `StaticMeshPipelineTool.py` show path editing, browse buttons, audit-style rows, and export or import actions.
- `BlenderUvFixerPipelineTool.json` and `BlenderUvFixerPipelineTool.py` show the preset-aware external Blender batch pattern.
- `ProjectIntegration.py` demonstrates the adapter boundary between discovered controllers and project-owned scripts under `Scripts/`.

The example uses the same script filenames as the live project, but the script bodies are intentionally lightweight. Treat them as structure and API references, not as production replacements for the repo's real automation. The Blender example mirrors the live preset controls and external-launch state contract, and the import/reimport example mirrors the cleaner lightmap-state result without copying the full production logic.

## Example Tree

```text
ProjectLayout/
|-- Config/
|   `-- DefaultPythonEditorUtility.ini
|-- PEU/
|   `-- PythonEditorUtility/
|       |-- Python/
|       |   `-- PythonEditorUtility/
|       |       |-- BlenderUvFixerPipelineTool.py
|       |       |-- BuildLightingTool.py
|       |       |-- LightmapResolutionTool.py
|       |       |-- ProjectIntegration.py
|       |       |-- StaticMeshPipelineTool.py
|       |       `-- __init__.py
|       |-- State/
|       |   `-- README.md
|       `-- UI/
|           |-- BlenderUvFixerPipelineTool.json
|           |-- BuildLightingTool.json
|           |-- LightmapResolutionTool.json
|           `-- StaticMeshPipelineTool.json
`-- Scripts/
    |-- UE_Lightmap_UV_Fixer_Batch.py
    |-- audit_static_mesh_lightmaps.py
    |-- build_level_lighting.py
    |-- bulk_export_static_meshes.py
    |-- bulk_reimport_static_meshes.py
    `-- project_path_utils.py
```

## How To Use The Template

1. Copy `Config/DefaultPythonEditorUtility.ini` into your project's `Config/` folder.
2. Adjust the path values if your project keeps the integration files somewhere other than `PEU/PythonEditorUtility/`.
3. Replace or expand the example JSON files with your own tool definitions.
4. Replace the example controller modules with your own project-owned controller code.
5. Port the example script interfaces to your real project scripts under `Scripts/`.
6. Keep generated runtime state in `PEU/PythonEditorUtility/State/`.

## Binding Surface Covered Here

The example exercises the generic binding surface already supported by the plugin:

- `%Text%` for text-box commits
- `%Checked%` for check-box state
- `%Value%` for combo-box selection
- `%Widget:Name%` for reading values from other widgets in the same tab
- `StateFile` and `StateKey` for project-owned state rehydration
- `PEU:OpenTool:*` for cross-tool navigation
- `PEU:BrowseFolder:*` and `PEU:BrowseFile:*` for native path selection
- `SStateTable` for table-driven project-owned state

## Ownership Boundary

- Change the plugin only when the standalone framework contract must change for every downstream project.
- Change the example-derived project integration when you need different tools, scripts, or project policy.
- Keep the backend logic in project-owned Python and `Scripts/` files.
- Do not modify plugin source for project-specific workflows.

Treat this folder as a project-layout reference for a standalone integration, not as a second copy of any specific project's production automation.
