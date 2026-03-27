# PythonEditorUtility Project Layout Example

This folder is a downstream integration template for the standalone PythonEditorUtility plugin.

The plugin stays framework-only. This example shows the project-owned integration files that a downstream team customizes. The rule is simple: do not modify plugin source to add project workflows.

## What The Starter Demonstrates

The neutral starter is intentionally small. It demonstrates the framework contract without mirroring this repository's production tools.

- `Config/DefaultPythonEditorUtility.ini` maps the plugin to project-owned integration folders.
- `PEU/PythonEditorUtility/UI/*.json` demonstrates dynamic discovery of editor tabs.
- `StarterOverviewTool.json` demonstrates `InitPyCmd`, `StateFile`, and read-only status rendering.
- `StarterActionsTool.json` demonstrates `%Text%`, `%Checked%`, `%Value%`, `%Widget:*%`, slot-level row padding, and the native `PEU:BrowseFolder:*` pattern.
- `ProjectIntegration.py` demonstrates the adapter boundary between the discovered controllers and project-owned scripts under `Scripts/`.

## Example Tree

```text
ProjectLayout/
|-- Config/
|   `-- DefaultPythonEditorUtility.ini
|-- PEU/
|   `-- PythonEditorUtility/
|       |-- Python/
|       |   `-- PythonEditorUtility/
|       |       |-- ProjectIntegration.py
|       |       |-- StarterActionsTool.py
|       |       |-- StarterOverviewTool.py
|       |       `-- __init__.py
|       |-- State/
|       |   `-- README.md
|       `-- UI/
|           |-- StarterActionsTool.json
|           `-- StarterOverviewTool.json
`-- Scripts/
    |-- starter_catalog.py
    `-- starter_workflow.py
```

## How To Use The Template

1. Copy `Config/DefaultPythonEditorUtility.ini` into your project's `Config/` folder.
2. Adjust the path values if your project keeps the integration files somewhere other than `PEU/PythonEditorUtility/`.
3. Replace the starter JSON files with your own tool definitions.
4. Replace the starter controllers with your own project-owned controller modules.
5. Point `ProjectIntegration.py` at your real project-owned scripts under `Scripts/`.
6. Keep generated runtime state in `PEU/PythonEditorUtility/State/`.

## Binding Surface

The starter uses the generic binding surface already supported by the plugin:

- `%Text%` for text-box commits
- `%Checked%` for check-box state
- `%Value%` for combo-box selection
- `%Widget:Name%` for reading values from other widgets in the same tab
- `StateFile` and `StateKey` for project-owned state rehydration
- `InitPyCmd` for project-owned bootstrap logic
- `PEU:BrowseFolder:WidgetAka` for native directory selection that flows back through `OnTextCommitted`

`StarterActionsTool.json` is the concrete reference for a label + text box + browse + action row in the example integration.

## Ownership Boundary

- Change the plugin only when the standalone framework contract must change for every downstream project.
- Change the example-derived project integration when you need different tools, scripts, or project policy.
- Keep the backend logic in project-owned Python and `Scripts/` files.
- Do not modify plugin source for project-specific workflows.

Treat this folder as a neutral starter and integration reference, not as a second copy of UE_AutomationMCP's live tooling.
