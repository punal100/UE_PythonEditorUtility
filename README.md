# PythonEditorUtility

PythonEditorUtility is a standalone Unreal Editor framework plugin. It owns tab discovery, widget hosting, Python callback execution, and generic editor helpers, while the project owns the actual workflows under `PEU/` and `Scripts/`.

The rule for downstream teams is unchanged: configure project-owned integration content and do not modify plugin source just to add or change project behavior.

## Standalone Contract

The plugin reads four integration settings:

- `PythonRoot`: project-owned Python root added to Unreal's Python search path
- `UiRoot`: project-owned folder scanned for discovered tool JSON files
- `StateRoot`: project-owned folder used for runtime state and status files
- `PythonPackage`: package prefix imported by the discovered controllers

The default contract ships in `Plugins/PythonEditorUtility/Config/DefaultPythonEditorUtility.ini`. A downstream project can keep those defaults or add `Config/DefaultPythonEditorUtility.ini` to point the plugin at a different integration layout.

## What The Plugin Owns

- native editor tab registration and the single `Tools > Python > Editor Utility Widget` submenu
- config-driven discovery of tool definitions from `UiRoot`
- generic Slate widget hosting for JSON-defined layouts
- Python execution for callback strings and `InitPyCmd`
- state rehydration for `StateFile`, `StateKey`, and status text
- package-prefix rewriting when a project changes `PythonPackage`
- generic cross-tool navigation through `PEU:OpenTool:*`
- native folder and file picker routing through `PEU:BrowseFolder:*` and `PEU:BrowseFile:*`
- slot-level `Padding` support for `SVerticalBox` and `SHorizontalBox`

## What A Project Owns

A project that uses the plugin owns the integration layer that the plugin points at. A typical project-owned layout can look like this:

```text
Project/
|-- Config/
|   `-- DefaultPythonEditorUtility.ini
|-- PEU/
|   `-- PythonEditorUtility/
|       |-- Python/
|       |   `-- PythonEditorUtility/
|       |       |-- ProjectIntegration.py
|       |       |-- BuildLightingTool.py
|       |       |-- LightmapResolutionTool.py
|       |       |-- StaticMeshPipelineTool.py
|       |       `-- BlenderUvFixerPipelineTool.py
|       |-- State/
|       `-- UI/
|           |-- BuildLightingTool.json
|           |-- LightmapResolutionTool.json
|           |-- StaticMeshPipelineTool.json
|           `-- BlenderUvFixerPipelineTool.json
`-- Scripts/
	|-- build_level_lighting.py
	|-- audit_static_mesh_lightmaps.py
	|-- bulk_export_static_meshes.py
	|-- bulk_reimport_static_meshes.py
	|-- project_path_utils.py
	`-- UE_Lightmap_UV_Fixer_Batch.py
```

In that layout, the plugin stays standalone while the project owns the tool JSON, controller modules, and backend scripts.

## Current Tool Surface

A common four-tool setup can use these PythonEditorUtility tabs:

- `Build Lighting`: precheck, build-lighting, and linked lighting actions
- `Lightmap Resolution`: resolution filters, selection table, and asset or instance actions
- `Static Mesh Pipeline`: export and import paths, audit summaries, and risk filtering
- `Blender UV Fixer Pipeline`: preset-aware external Blender batch execution with configurable folders and optional UCX collision exclusion during UV-only runs

The shipped example under `Examples/ProjectLayout/` follows that same four-tool structure. It is intentionally trimmed: the filenames, tab names, controller boundaries, and script mapping mirror a realistic project-owned integration, but the example backends stay lightweight so the plugin does not embed several thousand lines of project-specific production logic. The Blender example now mirrors the preset-discovery surface and the external-launch contract, while the import/reimport example mirrors the cleaner post-reimport lightmap-state contract without shipping the full production implementation.

## Generic Host Features

The standalone host discovers each `*.json` file under `UiRoot` and registers one tab plus one submenu entry without native code changes. A tool definition can set `TabLabel`, `StatusFile`, `StateFile`, `Tooltip`, and `InitPyCmd`.

The current JSON widget surface includes:

- `SVerticalBox`
- `SHorizontalBox`
- `SBorder`
- `SScrollBox`
- `SSplitter`
- `SUniformGridPanel`
- `STextBlock`
- `SButton`
- `SMultiLineEditableTextBox`
- `SEditableTextBox`
- `SCheckBox`
- `SComboBox`
- `SProgressBar`
- `SStateTable`

Callback strings can use these placeholders:

- `%Text%`
- `%Checked%`
- `%Value%`
- `%Widget:Name%`

Generic `PEU:` actions are also available from JSON button callbacks:

- `PEU:OpenTool:ToolName` opens another discovered tool tab
- `PEU:BrowseFolder:WidgetAka` opens a native directory picker, writes the selected path into the widget binding, and then runs the widget's `OnTextCommitted` command
- `PEU:BrowseFile:WidgetAka` does the same for file picks

State-backed bindings are also project-owned:

- `Aka` publishes widget values for `%Widget:Name%`
- `StateKey` maps widget values to JSON state fields
- `InitPyCmd` can bootstrap a tab before the user clicks anything

## Example Project Layout

`Plugins/PythonEditorUtility/Examples/ProjectLayout/` is the shipped reference integration for teams starting from the same architecture shown by this plugin.

The example demonstrates:

- one JSON file per discovered tool under `PEU/PythonEditorUtility/UI/`
- one controller module per tool under `PEU/PythonEditorUtility/Python/PythonEditorUtility/`
- an adapter boundary in `ProjectIntegration.py`
- lightweight example scripts that use the same filenames and responsibilities as a project-owned production integration
- runtime state written under `PEU/PythonEditorUtility/State/`

Use that example as a template for your own integration layer. Replace the project-owned files with your project's workflows and keep the plugin unchanged.

For a compact widget pattern catalog, see `Plugins/PythonEditorUtility/Docs/UI-PATTERNS.md`.

## Usage

1. Enable `PythonEditorUtility`, `PythonScriptPlugin`, and `EditorScriptingUtilities`.
2. Point the plugin at your project-owned integration files through `Config/DefaultPythonEditorUtility.ini` if needed.
3. Add or remove tool definitions by editing your project's `UiRoot`.
4. Implement controller behavior in your project's Python package and backend scripts.
5. Do not modify plugin source unless the framework contract itself needs to change for every downstream project.

## Python Package Notes

The default package name is `PythonEditorUtility`. If a downstream project uses a different `PythonPackage`, the native module rewrites `PythonEditorUtility.` callback prefixes at runtime so the JSON action strings can stay stable while the integration package changes.
