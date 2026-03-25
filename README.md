# PythonEditorUtility

PythonEditorUtility is a standalone Unreal Editor plugin that provides source-controlled editor tooling for this project.

It owns the plugin module, native Unreal menu and tab integration, the project-backed Python tool layer, and the runtime state used by its editor widgets.

In this project, PythonEditorUtility currently owns three editor tools:

- Build Lighting
- Lightmap Resolution
- Static Mesh Pipeline

The plugin itself lives under `Plugins/PythonEditorUtility/`.
The project-owned content and Python modules that back the plugin live under `PEU/PythonEditorUtility/`.

## What PythonEditorUtility Owns

At a high level, PythonEditorUtility is split into three layers:

1. Native Unreal Editor plugin layer
2. Project-owned Python layer
3. Project-owned state and UI definition layer

### Native plugin layer

This is the Unreal Editor module that:

- registers the PEU tabs
- adds menu entries
- creates the native Slate widgets
- bridges widget actions to the project Python modules
- reads and writes the runtime state files used to refresh the widget UI

Relevant paths:

- `Plugins/PythonEditorUtility/PythonEditorUtility.uplugin`
- `Plugins/PythonEditorUtility/Source/PythonEditorUtility/`

### Project Python layer

This layer contains the Python modules that implement the widget logic.
These modules usually call into the repository's existing project scripts rather than duplicating the lower-level automation logic.

Relevant paths:

- `PEU/PythonEditorUtility/Python/PythonEditorUtility/BuildLightingTool.py`
- `PEU/PythonEditorUtility/Python/PythonEditorUtility/LightmapResolutionTool.py`
- `PEU/PythonEditorUtility/Python/PythonEditorUtility/StaticMeshPipelineTool.py`

### UI and state layer

This project keeps the PEU runtime data and JSON definitions under source control or generated project folders instead of hiding everything inside a binary-only plugin.

Relevant paths:

- `PEU/PythonEditorUtility/UI/`
- `PEU/PythonEditorUtility/State/`

## Requirements

Before using PythonEditorUtility, confirm the following:

- Unreal Engine 5.7 is available locally
- the project is opened from `UE_AutomationMCP.uproject`
- `PythonEditorUtility` is enabled
- `PythonScriptPlugin` is enabled
- `EditorScriptingUtilities` is enabled
- Unreal startup completes without Python import errors

The plugin manifest currently declares:

- Editor-only module loading
- Win64, Mac, and Linux platform support
- dependency on `PythonScriptPlugin`
- dependency on `EditorScriptingUtilities`

## Folder Layout

Use this map when you need to find the implementation for a PythonEditorUtility behavior.

### Plugin root

- `Plugins/PythonEditorUtility/PythonEditorUtility.uplugin`
- `Plugins/PythonEditorUtility/Source/PythonEditorUtility/`
- `Plugins/PythonEditorUtility/Examples/ProjectLayout/`

### Project-owned PEU content

- `PEU/PythonEditorUtility/UI/`
- `PEU/PythonEditorUtility/Python/PythonEditorUtility/`
- `PEU/PythonEditorUtility/State/`

### Downstream project scripts used by PEU

- `Scripts/build_level_lighting.py`
- `Scripts/bulk_export_static_meshes.py`
- `Scripts/bulk_reimport_static_meshes.py`
- `Scripts/audit_static_mesh_lightmaps.py`

## How To Open The Tools

PythonEditorUtility exposes the tools in two menu paths.

### Primary tools menu path

Open the tools from:

- `Tools > Python > Editor Utility Widget > Build Lighting`
- `Tools > Python > Editor Utility Widget > Lightmap Resolution`
- `Tools > Python > Editor Utility Widget > Static Mesh Pipeline`

### Alternate window menu path

The same tabs are also available from:

- `Window > Python Editor Utility > Build Lighting`
- `Window > Python Editor Utility > Lightmap Resolution`
- `Window > Python Editor Utility > Static Mesh Pipeline`

## Quick Start

If you only want the shortest path to using the plugin, do this:

1. Open `UE_AutomationMCP.uproject` in Unreal Engine 5.7.
2. Wait for the editor to finish loading.
3. Open `Tools > Python > Editor Utility Widget`.
4. Choose one of the PEU tools.
5. Use the tool's built-in actions instead of calling scripts manually where possible.

## Plugin-Local Project Layout Example

PythonEditorUtility now keeps a plugin-local project layout example here:

- `Plugins/PythonEditorUtility/Examples/ProjectLayout/`

This folder mirrors how PythonEditorUtility is normally organized in the repository.
It includes a copy of the relevant `PEU/PythonEditorUtility/` content and the related `Scripts/` files used by the plugin workflows.

Use it when you want to inspect the normal folder structure in one place under the plugin root.

Included example layout:

- `PEU/PythonEditorUtility/Python/PythonEditorUtility/`
- `PEU/PythonEditorUtility/UI/`
- `PEU/PythonEditorUtility/State/`
- `Scripts/`

Example tree:

```text
Plugins/PythonEditorUtility/Examples/ProjectLayout/
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

These files are documentation snapshots.
PythonEditorUtility still runs from the real project-level folders at the repository root.

## Tool Guide

## Build Lighting

Build Lighting is the main workflow entry point for the repository's lighting workflow.

It does not reimplement all lighting logic directly in the plugin.
Instead, it calls into the project script backend in `Scripts/build_level_lighting.py`.

### What Build Lighting is for

Use Build Lighting when you want to:

- inspect lighting-related project state
- run a precheck before building
- launch a build using the repository's backend logic
- open the Lightmap Resolution inspector from the PEU workflow
- apply density settings and switch editor view modes related to lighting workflows

### Build Lighting behavior summary

The Build Lighting Python module currently exposes actions such as:

- `refresh_status()`
- `run_precheck()`
- `build_lighting()`
- `audit_static_meshes()`
- `open_lightmap_resolution_inspector()`
- `open_options_file()`
- `apply_density_settings()`
- `activate_lightmap_density_view()`
- `activate_lighting_only_view()`
- `activate_lit_view()`
- `show_native_lighting_actions()`

### Typical Build Lighting workflow

A common sequence is:

1. Open Build Lighting.
2. Click Refresh if you want a clean status snapshot.
3. Run Precheck.
4. Review the results.
5. Open the options file if needed.
6. Switch view modes if you need lighting-density review.
7. Run Build Lighting.
8. Re-open or refresh the status after the build.

### Build Lighting example: menu-driven use

1. Open `Tools > Python > Editor Utility Widget > Build Lighting`.
2. Review the discovered levels and current open level.
3. Run Precheck.
4. Fix blockers if any appear.
5. Start the build.

### Build Lighting example: Unreal Python console

If you want to call the module from Unreal Python directly:

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.refresh_status()
tool.run_precheck()
```

Run a build:

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.build_lighting()
```

Open the Lightmap Resolution tool from the Build Lighting backend path:

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.open_lightmap_resolution_inspector()
```

Switch view modes from Python:

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.activate_lightmap_density_view()
tool.activate_lighting_only_view()
tool.activate_lit_view()
```

### Build Lighting example: status refresh only

Use this when you only want the latest status written to the PEU state file and Unreal log:

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.refresh_status()
```

### Build Lighting output files

Build Lighting writes status information into the PEU state area.

Common file:

- `PEU/PythonEditorUtility/State/BuildLightingStatus.txt`

## Lightmap Resolution

Lightmap Resolution is the PEU-owned inspector for static mesh lightmap values discovered from selected levels or the currently open level.

### What Lightmap Resolution is for

Use this tool when you need to:

- inspect static mesh lightmap rows across levels
- sort and filter the discovered rows
- focus on the currently open level only
- focus only on rows with override values
- inspect row details before changing resolutions
- apply per-instance or per-asset lightmap changes through the existing lighting backend workflow

### Lightmap Resolution behavior summary

The Lightmap Resolution Python module keeps state for:

- target resolution value
- open-level-only filter
- override-only filter
- sort column and sort direction
- selected row keys

### Typical Lightmap Resolution workflow

1. Open the Lightmap Resolution tab.
2. Choose whether to inspect selected levels or the current open level.
3. Use Refresh to load rows.
4. Sort by Level, Actor, Mesh, Effective, Asset, or Override.
5. Select one or more rows.
6. Inspect the detail pane.
7. Apply the needed resolution action.

### Lightmap Resolution example: Unreal Python refresh

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.refresh_status()
```

### Lightmap Resolution example: set filters and sort

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.set_open_level_only(True)
tool.set_override_only(False)
tool.set_sort("Effective", "Desc")
tool.refresh_status()
```

### Lightmap Resolution example: set a target resolution

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.set_resolution(128)
tool.refresh_status()
```

### Lightmap Resolution example: select rows programmatically

```python
import PythonEditorUtility.LightmapResolutionTool as tool

keys = [
    "/Game/Maps/ExampleMap||/Game/Maps/ExampleMap.ExampleActor||StaticMeshComponent0||/Game/Meshes/SM_Example"
]
tool.set_selected_rows(keys)
```

### Lightmap Resolution state files

Typical files:

- `PEU/PythonEditorUtility/State/LightmapResolutionStatus.txt`
- `PEU/PythonEditorUtility/State/LightmapResolutionState.json`

## Static Mesh Pipeline

Static Mesh Pipeline combines export and import or reimport workflows into one PEU tab.

It is meant to surface the workflow state, the audit summary, and a structured results table without requiring the user to manually inspect the Output Log for every run.

### What Static Mesh Pipeline is for

Use this tool when you want to:

- export project static meshes to the exchange folder
- import or reimport FBX and OBJ files back into Unreal
- review overlap and wrapping indicators
- filter to risky rows only
- sort by asset, action, result, overlap, or wrapping
- inspect result details per row

### Static Mesh Pipeline behavior summary

The Static Mesh Pipeline Python module maintains state for:

- export source path
- export destination path
- import source path
- import destination path
- risks-only filter
- sort column and sort direction
- selected result rows

### Typical Static Mesh Pipeline workflow

1. Open Static Mesh Pipeline.
2. Review or edit the export and import paths.
3. Click Refresh if you want a clean passive status snapshot.
4. Run Export All.
5. Modify meshes externally if needed.
6. Run Import/Reimport All.
7. Review the status pane, result table, and detail pane.
8. Open the audit report if one was generated.

### Static Mesh Pipeline example: refresh only

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.refresh_status()
```

### Static Mesh Pipeline example: export all

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.run_export()
```

### Static Mesh Pipeline example: import or reimport all

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.run_import_reimport()
```

### Static Mesh Pipeline example: configure paths before export

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.set_paths(
    export_source="/Game",
    export_destination=r"D:\Projects\UE_Assets\Mesh\UE_Import_Export\UE_AutomationMCP",
    import_source=r"D:\Projects\UE_Assets\Mesh\UE_Import_Export\UE_AutomationMCP",
    import_destination="/Game",
)

tool.refresh_status()
```

### Static Mesh Pipeline example: filter risky rows only

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.set_risks_only(True)
tool.set_sort("Result", "Desc")
tool.refresh_status()
```

### Static Mesh Pipeline example: inspect a selected row

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

keys = ["/Game/Environment/BackgroundCube"]
tool.set_selected_rows(keys)
```

### Static Mesh Pipeline state files

Typical files:

- `PEU/PythonEditorUtility/State/StaticMeshPipelineStatus.txt`
- `PEU/PythonEditorUtility/State/StaticMeshPipelineState.json`

## Direct Script Examples

PythonEditorUtility is intentionally thin in places. Several PEU modules call into the project scripts under `Scripts/`.

That means you can still run the underlying scripts directly when needed.

The related project scripts are also mirrored under `Plugins/PythonEditorUtility/Examples/ProjectLayout/Scripts/` so the plugin keeps a local example of the normal project wiring next to the plugin source.

### Example: open the PEU Build Lighting flow through the backend script

```python
from Scripts import build_level_lighting

success, message = build_level_lighting.launch_python_editor_utility_build_lighting_tool()
print(success, message)
```

### Example: open the PEU Lightmap Resolution flow through the backend script

```python
from Scripts import build_level_lighting

success, message = build_level_lighting.launch_python_editor_utility_lightmap_resolution_tool()
print(success, message)
```

### Example: headless Blender UV fixer single-file mode

```powershell
python Scripts/UE_Lightmap_UV_Fixer.py --headless --blender-exe "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --input-fbx "D:\Path\Input.fbx" --output-fbx "D:\Path\Output.fbx"
```

### Example: headless Blender UV fixer batch mode

```powershell
python Scripts/UE_Lightmap_UV_Fixer_Batch.py --headless --blender-exe "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --source-dir "D:\Path\Export_From_UE" --destination-dir "D:\Path\Export_From_Blender_For_Export_From_UE"
```

## UI Behavior Notes

The current PEU widgets support the following quality-of-life behavior that matters during use:

- The tools can be opened from both the Tools menu and the Window menu path.
- The widgets keep project-owned runtime state under `PEU/PythonEditorUtility/State/`.
- Static Mesh Pipeline passive refresh now resets the active progress banner to idle instead of replaying stale export or import counts.
- The major content sections in Static Mesh Pipeline and Lightmap Resolution now use movable horizontal splitters.
- Both of those widgets now support vertical scrolling for smaller editor panes.

## Examples By Scenario

## Scenario: I only want to inspect current status

Build Lighting:

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.refresh_status()
```

Lightmap Resolution:

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.refresh_status()
```

Static Mesh Pipeline:

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.refresh_status()
```

## Scenario: I want to run the normal lighting workflow

```python
import PythonEditorUtility.BuildLightingTool as tool

tool.run_precheck()
tool.build_lighting()
```

## Scenario: I want to inspect only risky static mesh pipeline results

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.set_risks_only(True)
tool.set_sort("Result", "Desc")
tool.refresh_status()
```

## Scenario: I want to focus on the currently open level in Lightmap Resolution

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.set_open_level_only(True)
tool.refresh_status()
```

## Scenario: I want to review only rows with instance overrides in Lightmap Resolution

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.set_override_only(True)
tool.refresh_status()
```

## Scenario: I want to drive PEU from the Unreal Python console during debugging

```python
import PythonEditorUtility.BuildLightingTool as build_tool
import PythonEditorUtility.LightmapResolutionTool as lightmap_tool
import PythonEditorUtility.StaticMeshPipelineTool as pipeline_tool

build_tool.refresh_status()
lightmap_tool.refresh_status()
pipeline_tool.refresh_status()
```

## Troubleshooting

## The tab does not open

Check the following:

1. `PythonEditorUtility` is enabled.
2. `PythonScriptPlugin` is enabled.
3. `EditorScriptingUtilities` is enabled.
4. The project still contains the `PEU/PythonEditorUtility/` folder tree.
5. Unreal startup finished without Python import failures.

## Build Lighting falls back to another path

The backend is intentionally defensive.
If the PEU console-command path is not available, the script layer may fall back to other supported paths.

## Static Mesh Pipeline opens but shows no rows

Check:

- export and import paths
- whether the target asset folder contains exportable meshes
- whether the import source folder contains files expected by the reimport flow
- whether the risks-only filter is hiding all rows

A good reset sequence is:

```python
import PythonEditorUtility.StaticMeshPipelineTool as tool

tool.set_risks_only(False)
tool.set_sort("Result", "Desc")
tool.refresh_status()
```

## Lightmap Resolution shows no rows

Check:

- selected map assets in the Content Browser
- the currently open level
- the `Open Level Only` setting
- the `Override Only` setting

A good reset sequence is:

```python
import PythonEditorUtility.LightmapResolutionTool as tool

tool.set_open_level_only(False)
tool.set_override_only(False)
tool.set_sort("Level", "Asc")
tool.refresh_status()
```

## I cannot find the runtime output

Look in:

- `PEU/PythonEditorUtility/State/`

This folder contains generated runtime status and JSON state files.
It is expected to change while the tools are in use.

## Developer Notes

If you are extending PythonEditorUtility, start with these rules:

1. Keep project-specific behavior in project-owned Python or scripts where practical.
2. Keep the Unreal plugin focused on tab ownership, native widget construction, and bridging.
3. Prefer updating project-owned files under `PEU/PythonEditorUtility/` instead of hiding logic in the plugin where a repository-controlled Python module is sufficient.
4. Keep state files under `PEU/PythonEditorUtility/State/` consistent with the widget fields the C++ layer expects.
5. When adding a new PEU tool, update both the menu registration layer and the project documentation.

## Suggested Starting Points For Contributors

If you want to change a PEU feature, begin from the layer that most likely owns the behavior.

### Change menu entries or the native widget layout

Start here:

- `Plugins/PythonEditorUtility/Source/PythonEditorUtility/Private/PythonEditorUtilityModule.cpp`

### Change Build Lighting tool behavior

Start here:

- `PEU/PythonEditorUtility/Python/PythonEditorUtility/BuildLightingTool.py`
- `Scripts/build_level_lighting.py`

### Change Lightmap Resolution behavior

Start here:

- `PEU/PythonEditorUtility/Python/PythonEditorUtility/LightmapResolutionTool.py`
- `Scripts/build_level_lighting.py`

### Change Static Mesh Pipeline behavior

Start here:

- `PEU/PythonEditorUtility/Python/PythonEditorUtility/StaticMeshPipelineTool.py`
- `Scripts/bulk_export_static_meshes.py`
- `Scripts/bulk_reimport_static_meshes.py`

## License

PythonEditorUtility is distributed under the MIT License.

Repository:

- `https://github.com/punal100/UE_PythonEditorUtility.git`

See:

- `Plugins/PythonEditorUtility/LICENSE`

## Summary

PythonEditorUtility is the project's standalone editor utility plugin.

Use it when you want:

- source-controlled editor widgets
- Unreal-native menu and tab ownership
- project-owned Python tool behavior
- cross-platform editor utility workflows

If you are new to the repository, start with Build Lighting, then Lightmap Resolution, then Static Mesh Pipeline.
That sequence matches the current project workflow surface and the way the tools build on each other.
