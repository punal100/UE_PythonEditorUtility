# State Folder Placeholder

The real PythonEditorUtility state files are generated at runtime under:

- `PEU/PythonEditorUtility/State/`

This placeholder keeps the expected folder structure visible inside the plugin-local project layout example.

The example controllers in this folder write the same style of artifacts as the live project:

- `BuildLightingState.json` and `BuildLightingStatus.txt`
- `LightmapResolutionState.json` and `LightmapResolutionStatus.txt`
- `StaticMeshPipelineState.json` and `StaticMeshPipelineStatus.txt`
- `BlenderUvFixerPipelineState.json` and `BlenderUvFixerPipelineStatus.txt`

Treat these files as runtime scratch data owned by the project integration, not by the plugin itself.
