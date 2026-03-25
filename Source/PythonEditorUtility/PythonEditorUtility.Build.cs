using UnrealBuildTool;

public class PythonEditorUtility : ModuleRules
{
    public PythonEditorUtility(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new string[]
            {
                "Core",
                "CoreUObject",
                "Engine",
                "Slate",
                "SlateCore",
                "Json",
                "Projects",
                "ToolMenus",
                "PythonScriptPlugin"
            }
        );

        PrivateDependencyModuleNames.AddRange(
            new string[]
            {
                "ApplicationCore",
                "DesktopPlatform",
                "EditorStyle",
                "InputCore",
                "UnrealEd",
                "WorkspaceMenuStructure"
            }
        );
    }
}