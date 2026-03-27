# PythonEditorUtility

PythonEditorUtility is a standalone Unreal Editor framework plugin. It hosts project-owned tabs and Python callbacks, but it does not own a project's workflow policy.

The rule for downstream teams is strict: configure project-owned integration content and do not modify plugin source just to add or change project behavior.

## Standalone Contract

The plugin reads four integration settings:

- `PythonRoot`: project-owned Python root added to Unreal's Python search path
- `UiRoot`: project-owned folder scanned for discovered tool JSON files
- `StateRoot`: project-owned folder used for runtime state and status files
- `PythonPackage`: package prefix imported by the discovered controllers

The default contract ships in `Plugins/PythonEditorUtility/Config/DefaultPythonEditorUtility.ini`. A downstream project can keep those defaults or add `Config/DefaultPythonEditorUtility.ini` to point the plugin at a different integration layout.

## What The Plugin Owns

- native editor tab registration and menu registration
- config-driven discovery of tool definitions from `UiRoot`
- generic Slate widget hosting for JSON-defined layouts
- Python execution for callback strings and `InitPyCmd`
- state rehydration for `StateFile`, `StateKey`, and status text
- package-prefix rewriting when a project changes `PythonPackage`
- generic cross-tool navigation through `PEU:OpenTool:*`
- native folder and file picker routing through `PEU:BrowseFolder:*` and `PEU:BrowseFile:*`
- slot-level `Padding` support for `SVerticalBox` and `SHorizontalBox`

## What A Project Owns

A project that uses the plugin owns the integration layer that the plugin points at. A typical integration layout looks like this:

```text
Project/
|-- Config/
|   `-- DefaultPythonEditorUtility.ini
|-- PEU/
|   `-- PythonEditorUtility/
|       |-- Python/
|       |   `-- PythonEditorUtility/
|       |       |-- ProjectIntegration.py
|       |       `-- StarterActionsTool.py
|       |-- State/
|       `-- UI/
`-- Scripts/
```

In that layout, the plugin stays standalone while the project owns the tool JSON, controller modules, and backend scripts.

## Generic Host Features

The standalone host discovers each `*.json` file under `UiRoot` and registers one tab plus one menu entry for it. A tool definition can set `TabLabel`, `StatusFile`, `StateFile`, `Tooltip`, and `InitPyCmd` without changing native code.

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

## Example Starter

`Plugins/PythonEditorUtility/Examples/ProjectLayout/` now ships a neutral starter integration instead of a repository-specific workflow mirror.

The example demonstrates:

- dynamic discovery from project-owned `UI/*.json`
- `InitPyCmd` bootstrapping through project-owned controllers
- `StateFile` and `StateKey` rehydration
- `%Widget:*%` placeholders passed into project-owned Python functions
- adapter calls from `ProjectIntegration.py` into project-owned scripts under `Scripts/`

Use that example as a template for your own integration layer. Replace the project-owned files with your project's workflows and keep the plugin unchanged.

The starter actions example now includes a browse-enabled filesystem row so downstream projects have a concrete reference for `SHorizontalBox` label/input/button layouts. For a compact pattern catalog, see `Plugins/PythonEditorUtility/Docs/UI-PATTERNS.md`.

## Usage

1. Enable `PythonEditorUtility`, `PythonScriptPlugin`, and `EditorScriptingUtilities`.
2. Point the plugin at your project-owned integration files through `Config/DefaultPythonEditorUtility.ini` if needed.
3. Add or remove tool definitions by editing your project's `UiRoot`.
4. Implement controller behavior in your project's Python package and backend scripts.
5. Do not modify plugin source unless the framework contract itself needs to change for every downstream project.

## Python Package Notes

The default package name is `PythonEditorUtility`. If a downstream project uses a different `PythonPackage`, the native module rewrites `PythonEditorUtility.` callback prefixes at runtime so the JSON action strings can stay stable while the integration package changes.
