#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

#include "Framework/Docking/TabManager.h"
#include "Framework/Application/SlateApplication.h"
#include "IPythonScriptPlugin.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "WorkspaceMenuStructure.h"
#include "WorkspaceMenuStructureModule.h"
#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Styling/AppStyle.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSplitter.h"
#include "Widgets/Layout/SUniformGridPanel.h"
#include "Widgets/Notifications/SProgressBar.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"

namespace PythonEditorUtility
{
    static const FName BuildLightingTabName(TEXT("PythonEditorUtility.BuildLighting"));
    static const FName LightmapResolutionTabName(TEXT("PythonEditorUtility.LightmapResolution"));
    static const FName StaticMeshPipelineTabName(TEXT("PythonEditorUtility.StaticMeshPipeline"));
    static TMap<FName, TSharedPtr<SMultiLineEditableTextBox>> ToolOutputTextBoxes;
    static bool bUpdatingLightmapSelection = false;
    static bool bUpdatingStaticMeshPipelineSelection = false;

    static const FName LevelColumnName(TEXT("Level"));
    static const FName ActorColumnName(TEXT("Actor"));
    static const FName ComponentColumnName(TEXT("Component"));
    static const FName MeshColumnName(TEXT("Mesh"));
    static const FName MobilityColumnName(TEXT("Mobility"));
    static const FName EffectiveColumnName(TEXT("Effective"));
    static const FName AssetColumnName(TEXT("Asset"));
    static const FName OverrideColumnName(TEXT("Override"));
    static const FName PipelineAssetColumnName(TEXT("Asset"));
    static const FName PipelineActionColumnName(TEXT("Action"));
    static const FName PipelineResultColumnName(TEXT("Result"));
    static const FName PipelineOverlapColumnName(TEXT("Overlap"));
    static const FName PipelineWrappingColumnName(TEXT("Wrapping"));
    static const FName LightmapResizeSpacerColumnName(TEXT("LightmapResizeSpacer"));
    static const FName PipelineResizeSpacerColumnName(TEXT("PipelineResizeSpacer"));

    struct FLightmapResolutionRowData
    {
        FString Key;
        FString Level;
        FString Actor;
        FString Component;
        FString Mesh;
        FString Mobility;
        FString Effective;
        FString Asset;
        FString Override;
    };

    using FLightmapResolutionRowPtr = TSharedPtr<FLightmapResolutionRowData>;

    struct FStaticMeshPipelineRowData
    {
        FString Key;
        FString Asset;
        FString Action;
        FString Result;
        FString Overlap;
        FString Wrapping;
    };

    using FStaticMeshPipelineRowPtr = TSharedPtr<FStaticMeshPipelineRowData>;

    struct FLightmapResolutionState
    {
        FString Resolution = TEXT("64");
        bool bOpenLevelOnly = false;
        bool bOverrideOnly = false;
        FString SortColumn = TEXT("Level");
        FString SortDirection = TEXT("Asc");
        FString ProgressText = TEXT("Idle");
        float ProgressPercent = 0.0f;
        FString StatusText = TEXT("Loading...");
        TArray<FLightmapResolutionRowPtr> Rows;
        TArray<FString> SelectedRowKeys;
        FString DetailText = TEXT("Select map assets in the Content Browser, or keep a level open, then click Refresh.");
    };

    struct FStaticMeshPipelineState
    {
        bool bRisksOnly = false;
        FString SortColumn = TEXT("Result");
        FString SortDirection = TEXT("Desc");
        FString ExportSource = TEXT("/Game");
        FString ExportDestination;
        FString ImportSource;
        FString ImportDestination = TEXT("/Game");
        FString ProgressText = TEXT("Idle");
        float ProgressPercent = 0.0f;
        FString StatusText = TEXT("Loading...");
        TArray<FStaticMeshPipelineRowPtr> Rows;
        TArray<FString> SelectedRowKeys;
        FString DetailText = TEXT("Use Export All or Import/Reimport All to populate the pipeline results.");
    };

    struct FLightmapResolutionWidgets
    {
        TSharedPtr<SEditableTextBox> ResolutionInput;
        TSharedPtr<SCheckBox> OpenLevelOnlyCheck;
        TSharedPtr<SCheckBox> OverrideOnlyCheck;
        TSharedPtr<SComboBox<TSharedPtr<FString>>> SortColumnCombo;
        TSharedPtr<SComboBox<TSharedPtr<FString>>> SortDirectionCombo;
        TSharedPtr<STextBlock> ProgressText;
        TSharedPtr<SProgressBar> ProgressBar;
        TSharedPtr<SMultiLineEditableTextBox> StatusOutput;
        TSharedPtr<SListView<FLightmapResolutionRowPtr>> RowsListView;
        TSharedPtr<SMultiLineEditableTextBox> DetailOutput;
        TArray<TSharedPtr<FString>> SortColumnOptions;
        TArray<TSharedPtr<FString>> SortDirectionOptions;
        TArray<FLightmapResolutionRowPtr> RowItems;
        TSharedPtr<FString> SelectedSortColumn;
        TSharedPtr<FString> SelectedSortDirection;
    };

    struct FStaticMeshPipelineWidgets
    {
        TSharedPtr<SEditableTextBox> ExportSourceInput;
        TSharedPtr<SEditableTextBox> ExportDestinationInput;
        TSharedPtr<SEditableTextBox> ImportSourceInput;
        TSharedPtr<SEditableTextBox> ImportDestinationInput;
        TSharedPtr<SCheckBox> RisksOnlyCheck;
        TSharedPtr<SComboBox<TSharedPtr<FString>>> SortColumnCombo;
        TSharedPtr<SComboBox<TSharedPtr<FString>>> SortDirectionCombo;
        TSharedPtr<STextBlock> ProgressText;
        TSharedPtr<SProgressBar> ProgressBar;
        TSharedPtr<SMultiLineEditableTextBox> StatusOutput;
        TSharedPtr<SListView<FStaticMeshPipelineRowPtr>> RowsListView;
        TSharedPtr<SMultiLineEditableTextBox> DetailOutput;
        TArray<TSharedPtr<FString>> SortColumnOptions;
        TArray<TSharedPtr<FString>> SortDirectionOptions;
        TArray<FStaticMeshPipelineRowPtr> RowItems;
        TSharedPtr<FString> SelectedSortColumn;
        TSharedPtr<FString> SelectedSortDirection;
    };

    static FLightmapResolutionWidgets LightmapResolutionWidgets;
    static FStaticMeshPipelineWidgets StaticMeshPipelineWidgets;

    static FString GetUiJsonPath(const FName &TabName)
    {
        const TCHAR *RelativePath = TabName == LightmapResolutionTabName
                                        ? TEXT("PEU/PythonEditorUtility/UI/LightmapResolutionTool.json")
                                        : TEXT("PEU/PythonEditorUtility/UI/BuildLightingTool.json");
        return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / RelativePath);
    }

    static FString GetPythonContentPath()
    {
        return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("PEU/PythonEditorUtility/Python"));
    }

    static FString GetStatusTextPath(const FName &TabName)
    {
        const TCHAR *RelativePath = TabName == LightmapResolutionTabName
                                        ? TEXT("PEU/PythonEditorUtility/State/LightmapResolutionStatus.txt")
                                        : (TabName == StaticMeshPipelineTabName
                                               ? TEXT("PEU/PythonEditorUtility/State/StaticMeshPipelineStatus.txt")
                                               : TEXT("PEU/PythonEditorUtility/State/BuildLightingStatus.txt"));
        return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / RelativePath);
    }

    static FString GetLightmapResolutionStatePath()
    {
        return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("PEU/PythonEditorUtility/State/LightmapResolutionState.json"));
    }

    static FString GetStaticMeshPipelineStatePath()
    {
        return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("PEU/PythonEditorUtility/State/StaticMeshPipelineState.json"));
    }

    static FString GetRefreshPythonCommand(const FName &TabName)
    {
        if (TabName == LightmapResolutionTabName)
        {
            return TEXT("import PythonEditorUtility.LightmapResolutionTool as tool; tool.refresh_status()");
        }

        if (TabName == StaticMeshPipelineTabName)
        {
            return TEXT("import PythonEditorUtility.StaticMeshPipelineTool as tool; tool.refresh_status()");
        }

        return TEXT("import PythonEditorUtility.BuildLightingTool as tool; tool.refresh_status()");
    }

    static FString LoadStatusText(const FName &TabName)
    {
        FString StatusText;
        if (FFileHelper::LoadFileToString(StatusText, *GetStatusTextPath(TabName)))
        {
            return StatusText;
        }

        return TEXT("Loading...");
    }

    static void RefreshOutputTextBox(const FName &TabName)
    {
        TSharedPtr<SMultiLineEditableTextBox> *OutputTextBox = ToolOutputTextBoxes.Find(TabName);
        if (OutputTextBox != nullptr && OutputTextBox->IsValid())
        {
            (*OutputTextBox)->SetText(FText::FromString(LoadStatusText(TabName)));
        }
    }

    static void EnsurePythonSearchPath()
    {
        if (IPythonScriptPlugin *PythonPlugin = IPythonScriptPlugin::Get())
        {
            const FString PythonContentPath = GetPythonContentPath().ReplaceCharWithEscapedChar();
            const FString PythonCommand = FString::Printf(
                TEXT("import sys; path = r'%s'; normalized = path.replace('\\\\', '/'); existing = [entry.replace('\\\\', '/') for entry in sys.path]; sys.path.append(path) if normalized not in existing else None"),
                *PythonContentPath);
            PythonPlugin->ExecPythonCommand(*PythonCommand);
        }
    }

    static bool LoadJsonObjectFromFile(const FString &FilePath, TSharedPtr<FJsonObject> &JsonObject)
    {
        FString JsonText;
        if (!FFileHelper::LoadFileToString(JsonText, *FilePath))
        {
            return false;
        }

        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
        return FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid();
    }

    static TSharedPtr<FString> FindOption(const TArray<TSharedPtr<FString>> &Options, const FString &Value)
    {
        for (const TSharedPtr<FString> &Option : Options)
        {
            if (Option.IsValid() && Option->Equals(Value, ESearchCase::CaseSensitive))
            {
                return Option;
            }
        }

        return Options.Num() > 0 ? Options[0] : nullptr;
    }

    static ECheckBoxState ToCheckBoxState(const bool bChecked)
    {
        return bChecked ? ECheckBoxState::Checked : ECheckBoxState::Unchecked;
    }

    static FString ToPythonBool(const bool bValue)
    {
        return bValue ? TEXT("True") : TEXT("False");
    }

    static FString EscapePythonString(const FString &Value)
    {
        FString Escaped = Value;
        Escaped.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
        Escaped.ReplaceInline(TEXT("'"), TEXT("\\'"));
        Escaped.ReplaceInline(TEXT("\r"), TEXT("\\r"));
        Escaped.ReplaceInline(TEXT("\n"), TEXT("\\n"));
        return Escaped;
    }

    static FString BuildPythonStringListLiteral(const TArray<FString> &Values)
    {
        FString Result = TEXT("[");
        for (int32 Index = 0; Index < Values.Num(); ++Index)
        {
            if (Index > 0)
            {
                Result += TEXT(", ");
            }

            Result += FString::Printf(TEXT("'%s'"), *EscapePythonString(Values[Index]));
        }
        Result += TEXT("]");
        return Result;
    }

    static FString BrowseForDirectory(const FString &Title, const FString &DefaultPath)
    {
        IDesktopPlatform *DesktopPlatform = FDesktopPlatformModule::Get();
        if (DesktopPlatform == nullptr)
        {
            return FString();
        }

        void *ParentWindowHandle = nullptr;
        if (FSlateApplication::IsInitialized())
        {
            const TSharedPtr<SWindow> ParentWindow = FSlateApplication::Get().FindBestParentWindowForDialogs(nullptr);
            if (ParentWindow.IsValid() && ParentWindow->GetNativeWindow().IsValid())
            {
                ParentWindowHandle = ParentWindow->GetNativeWindow()->GetOSWindowHandle();
            }
        }

        FString SelectedFolder;
        const bool bOpened = DesktopPlatform->OpenDirectoryDialog(ParentWindowHandle, Title, DefaultPath, SelectedFolder);
        return bOpened ? SelectedFolder : FString();
    }

    static FLightmapResolutionState LoadLightmapResolutionState()
    {
        FLightmapResolutionState State;
        TSharedPtr<FJsonObject> RootObject;
        if (!LoadJsonObjectFromFile(GetLightmapResolutionStatePath(), RootObject))
        {
            State.StatusText = LoadStatusText(LightmapResolutionTabName);
            return State;
        }

        RootObject->TryGetStringField(TEXT("resolution"), State.Resolution);
        RootObject->TryGetBoolField(TEXT("open_level_only"), State.bOpenLevelOnly);
        RootObject->TryGetBoolField(TEXT("override_only"), State.bOverrideOnly);
        RootObject->TryGetStringField(TEXT("sort_column"), State.SortColumn);
        RootObject->TryGetStringField(TEXT("sort_direction"), State.SortDirection);
        RootObject->TryGetStringField(TEXT("progress_text"), State.ProgressText);
        RootObject->TryGetStringField(TEXT("status_text"), State.StatusText);
        RootObject->TryGetStringField(TEXT("detail_text"), State.DetailText);

        const TArray<TSharedPtr<FJsonValue>> *SelectedRowKeys = nullptr;
        if (RootObject->TryGetArrayField(TEXT("selected_row_keys"), SelectedRowKeys) && SelectedRowKeys != nullptr)
        {
            for (const TSharedPtr<FJsonValue> &SelectedValue : *SelectedRowKeys)
            {
                State.SelectedRowKeys.Add(SelectedValue->AsString());
            }
        }

        const TArray<TSharedPtr<FJsonValue>> *Rows = nullptr;
        if (RootObject->TryGetArrayField(TEXT("rows"), Rows) && Rows != nullptr)
        {
            for (const TSharedPtr<FJsonValue> &RowValue : *Rows)
            {
                const TSharedPtr<FJsonObject> RowObject = RowValue->AsObject();
                if (!RowObject.IsValid())
                {
                    continue;
                }

                FLightmapResolutionRowPtr Row = MakeShared<FLightmapResolutionRowData>();
                RowObject->TryGetStringField(TEXT("key"), Row->Key);
                RowObject->TryGetStringField(TEXT("level"), Row->Level);
                RowObject->TryGetStringField(TEXT("actor"), Row->Actor);
                RowObject->TryGetStringField(TEXT("component"), Row->Component);
                RowObject->TryGetStringField(TEXT("mesh"), Row->Mesh);
                RowObject->TryGetStringField(TEXT("mobility"), Row->Mobility);
                RowObject->TryGetStringField(TEXT("effective"), Row->Effective);
                RowObject->TryGetStringField(TEXT("asset"), Row->Asset);
                RowObject->TryGetStringField(TEXT("override"), Row->Override);
                State.Rows.Add(Row);
            }
        }

        double ProgressPercent = 0.0;
        if (RootObject->TryGetNumberField(TEXT("progress_percent"), ProgressPercent))
        {
            State.ProgressPercent = (float)ProgressPercent;
        }

        return State;
    }

    static void RefreshLightmapResolutionWidgets()
    {
        const FLightmapResolutionState State = LoadLightmapResolutionState();

        if (LightmapResolutionWidgets.ResolutionInput.IsValid())
        {
            LightmapResolutionWidgets.ResolutionInput->SetText(FText::FromString(State.Resolution));
        }
        if (LightmapResolutionWidgets.OpenLevelOnlyCheck.IsValid())
        {
            LightmapResolutionWidgets.OpenLevelOnlyCheck->SetIsChecked(ToCheckBoxState(State.bOpenLevelOnly));
        }
        if (LightmapResolutionWidgets.OverrideOnlyCheck.IsValid())
        {
            LightmapResolutionWidgets.OverrideOnlyCheck->SetIsChecked(ToCheckBoxState(State.bOverrideOnly));
        }
        if (LightmapResolutionWidgets.SortColumnCombo.IsValid())
        {
            LightmapResolutionWidgets.SelectedSortColumn = FindOption(LightmapResolutionWidgets.SortColumnOptions, State.SortColumn);
            if (LightmapResolutionWidgets.SelectedSortColumn.IsValid())
            {
                LightmapResolutionWidgets.SortColumnCombo->SetSelectedItem(LightmapResolutionWidgets.SelectedSortColumn);
            }
        }
        if (LightmapResolutionWidgets.SortDirectionCombo.IsValid())
        {
            LightmapResolutionWidgets.SelectedSortDirection = FindOption(LightmapResolutionWidgets.SortDirectionOptions, State.SortDirection);
            if (LightmapResolutionWidgets.SelectedSortDirection.IsValid())
            {
                LightmapResolutionWidgets.SortDirectionCombo->SetSelectedItem(LightmapResolutionWidgets.SelectedSortDirection);
            }
        }
        if (LightmapResolutionWidgets.ProgressText.IsValid())
        {
            LightmapResolutionWidgets.ProgressText->SetText(FText::FromString(State.ProgressText));
        }
        if (LightmapResolutionWidgets.ProgressBar.IsValid())
        {
            LightmapResolutionWidgets.ProgressBar->SetPercent(FMath::Clamp(State.ProgressPercent, 0.0f, 1.0f));
        }
        if (LightmapResolutionWidgets.StatusOutput.IsValid())
        {
            LightmapResolutionWidgets.StatusOutput->SetText(FText::FromString(State.StatusText));
        }
        if (LightmapResolutionWidgets.DetailOutput.IsValid())
        {
            LightmapResolutionWidgets.DetailOutput->SetText(FText::FromString(State.DetailText));
        }

        LightmapResolutionWidgets.RowItems = State.Rows;
        if (LightmapResolutionWidgets.RowsListView.IsValid())
        {
            LightmapResolutionWidgets.RowsListView->RequestListRefresh();

            bUpdatingLightmapSelection = true;
            LightmapResolutionWidgets.RowsListView->ClearSelection();
            for (const FLightmapResolutionRowPtr &Row : LightmapResolutionWidgets.RowItems)
            {
                if (Row.IsValid() && State.SelectedRowKeys.Contains(Row->Key))
                {
                    LightmapResolutionWidgets.RowsListView->SetItemSelection(Row, true, ESelectInfo::Direct);
                }
            }
            bUpdatingLightmapSelection = false;
        }
    }

    static void ExecutePython(const FString &Command, const FName &TabName);

    static FStaticMeshPipelineState LoadStaticMeshPipelineState()
    {
        FStaticMeshPipelineState State;
        TSharedPtr<FJsonObject> RootObject;
        if (!LoadJsonObjectFromFile(GetStaticMeshPipelineStatePath(), RootObject))
        {
            State.StatusText = LoadStatusText(StaticMeshPipelineTabName);
            return State;
        }

        RootObject->TryGetBoolField(TEXT("risks_only"), State.bRisksOnly);
        RootObject->TryGetStringField(TEXT("sort_column"), State.SortColumn);
        RootObject->TryGetStringField(TEXT("sort_direction"), State.SortDirection);
        RootObject->TryGetStringField(TEXT("export_source"), State.ExportSource);
        RootObject->TryGetStringField(TEXT("export_destination"), State.ExportDestination);
        RootObject->TryGetStringField(TEXT("import_source"), State.ImportSource);
        RootObject->TryGetStringField(TEXT("import_destination"), State.ImportDestination);
        RootObject->TryGetStringField(TEXT("progress_text"), State.ProgressText);
        RootObject->TryGetStringField(TEXT("status_text"), State.StatusText);
        RootObject->TryGetStringField(TEXT("detail_text"), State.DetailText);

        const TArray<TSharedPtr<FJsonValue>> *SelectedRowKeys = nullptr;
        if (RootObject->TryGetArrayField(TEXT("selected_row_keys"), SelectedRowKeys) && SelectedRowKeys != nullptr)
        {
            for (const TSharedPtr<FJsonValue> &SelectedValue : *SelectedRowKeys)
            {
                State.SelectedRowKeys.Add(SelectedValue->AsString());
            }
        }

        const TArray<TSharedPtr<FJsonValue>> *Rows = nullptr;
        if (RootObject->TryGetArrayField(TEXT("rows"), Rows) && Rows != nullptr)
        {
            for (const TSharedPtr<FJsonValue> &RowValue : *Rows)
            {
                const TSharedPtr<FJsonObject> RowObject = RowValue->AsObject();
                if (!RowObject.IsValid())
                {
                    continue;
                }

                FStaticMeshPipelineRowPtr Row = MakeShared<FStaticMeshPipelineRowData>();
                RowObject->TryGetStringField(TEXT("key"), Row->Key);
                RowObject->TryGetStringField(TEXT("asset"), Row->Asset);
                RowObject->TryGetStringField(TEXT("action"), Row->Action);
                RowObject->TryGetStringField(TEXT("result"), Row->Result);
                RowObject->TryGetStringField(TEXT("overlap"), Row->Overlap);
                RowObject->TryGetStringField(TEXT("wrapping"), Row->Wrapping);
                State.Rows.Add(Row);
            }
        }

        double ProgressPercent = 0.0;
        if (RootObject->TryGetNumberField(TEXT("progress_percent"), ProgressPercent))
        {
            State.ProgressPercent = (float)ProgressPercent;
        }

        return State;
    }

    static void InitializeStaticMeshPipelineOptions()
    {
        if (StaticMeshPipelineWidgets.SortColumnOptions.Num() == 0)
        {
            StaticMeshPipelineWidgets.SortColumnOptions = {
                MakeShared<FString>(TEXT("Asset")),
                MakeShared<FString>(TEXT("Action")),
                MakeShared<FString>(TEXT("Result")),
                MakeShared<FString>(TEXT("Overlap")),
                MakeShared<FString>(TEXT("Wrapping"))};
        }

        if (StaticMeshPipelineWidgets.SortDirectionOptions.Num() == 0)
        {
            StaticMeshPipelineWidgets.SortDirectionOptions = {
                MakeShared<FString>(TEXT("Asc")),
                MakeShared<FString>(TEXT("Desc"))};
        }

        if (!StaticMeshPipelineWidgets.SelectedSortColumn.IsValid())
        {
            StaticMeshPipelineWidgets.SelectedSortColumn = FindOption(StaticMeshPipelineWidgets.SortColumnOptions, TEXT("Result"));
        }
        if (!StaticMeshPipelineWidgets.SelectedSortDirection.IsValid())
        {
            StaticMeshPipelineWidgets.SelectedSortDirection = FindOption(StaticMeshPipelineWidgets.SortDirectionOptions, TEXT("Desc"));
        }
    }

    static FString GetSelectedStaticMeshPipelineSortColumn()
    {
        return StaticMeshPipelineWidgets.SelectedSortColumn.IsValid() ? *StaticMeshPipelineWidgets.SelectedSortColumn : TEXT("Result");
    }

    static FString GetSelectedStaticMeshPipelineSortDirection()
    {
        return StaticMeshPipelineWidgets.SelectedSortDirection.IsValid() ? *StaticMeshPipelineWidgets.SelectedSortDirection : TEXT("Desc");
    }

    static FString GetStaticMeshPipelineExportSource()
    {
        return StaticMeshPipelineWidgets.ExportSourceInput.IsValid() ? StaticMeshPipelineWidgets.ExportSourceInput->GetText().ToString().TrimStartAndEnd() : TEXT("/Game");
    }

    static FString GetStaticMeshPipelineExportDestination()
    {
        return StaticMeshPipelineWidgets.ExportDestinationInput.IsValid() ? StaticMeshPipelineWidgets.ExportDestinationInput->GetText().ToString().TrimStartAndEnd() : FPaths::ProjectDir();
    }

    static FString GetStaticMeshPipelineImportSource()
    {
        return StaticMeshPipelineWidgets.ImportSourceInput.IsValid() ? StaticMeshPipelineWidgets.ImportSourceInput->GetText().ToString().TrimStartAndEnd() : FPaths::ProjectDir();
    }

    static FString GetStaticMeshPipelineImportDestination()
    {
        return StaticMeshPipelineWidgets.ImportDestinationInput.IsValid() ? StaticMeshPipelineWidgets.ImportDestinationInput->GetText().ToString().TrimStartAndEnd() : TEXT("/Game");
    }

    static bool IsStaticMeshPipelineRisksOnlyChecked()
    {
        return StaticMeshPipelineWidgets.RisksOnlyCheck.IsValid() && StaticMeshPipelineWidgets.RisksOnlyCheck->IsChecked();
    }

    static FString BuildStaticMeshPipelinePythonCommand(const FString &ActionSuffix)
    {
        return FString::Printf(
            TEXT("import PythonEditorUtility.StaticMeshPipelineTool as tool; tool.set_paths('%s', '%s', '%s', '%s'); tool.set_risks_only(%s); tool.set_sort('%s', '%s'); %s"),
            *EscapePythonString(GetStaticMeshPipelineExportSource()),
            *EscapePythonString(GetStaticMeshPipelineExportDestination()),
            *EscapePythonString(GetStaticMeshPipelineImportSource()),
            *EscapePythonString(GetStaticMeshPipelineImportDestination()),
            *ToPythonBool(IsStaticMeshPipelineRisksOnlyChecked()),
            *GetSelectedStaticMeshPipelineSortColumn(),
            *GetSelectedStaticMeshPipelineSortDirection(),
            *ActionSuffix);
    }

    static void RefreshStaticMeshPipelineWidgets()
    {
        const FStaticMeshPipelineState State = LoadStaticMeshPipelineState();

        if (StaticMeshPipelineWidgets.ExportSourceInput.IsValid())
        {
            StaticMeshPipelineWidgets.ExportSourceInput->SetText(FText::FromString(State.ExportSource));
        }
        if (StaticMeshPipelineWidgets.ExportDestinationInput.IsValid())
        {
            StaticMeshPipelineWidgets.ExportDestinationInput->SetText(FText::FromString(State.ExportDestination));
        }
        if (StaticMeshPipelineWidgets.ImportSourceInput.IsValid())
        {
            StaticMeshPipelineWidgets.ImportSourceInput->SetText(FText::FromString(State.ImportSource));
        }
        if (StaticMeshPipelineWidgets.ImportDestinationInput.IsValid())
        {
            StaticMeshPipelineWidgets.ImportDestinationInput->SetText(FText::FromString(State.ImportDestination));
        }
        if (StaticMeshPipelineWidgets.RisksOnlyCheck.IsValid())
        {
            StaticMeshPipelineWidgets.RisksOnlyCheck->SetIsChecked(ToCheckBoxState(State.bRisksOnly));
        }
        if (StaticMeshPipelineWidgets.SortColumnCombo.IsValid())
        {
            StaticMeshPipelineWidgets.SelectedSortColumn = FindOption(StaticMeshPipelineWidgets.SortColumnOptions, State.SortColumn);
            if (StaticMeshPipelineWidgets.SelectedSortColumn.IsValid())
            {
                StaticMeshPipelineWidgets.SortColumnCombo->SetSelectedItem(StaticMeshPipelineWidgets.SelectedSortColumn);
            }
        }
        if (StaticMeshPipelineWidgets.SortDirectionCombo.IsValid())
        {
            StaticMeshPipelineWidgets.SelectedSortDirection = FindOption(StaticMeshPipelineWidgets.SortDirectionOptions, State.SortDirection);
            if (StaticMeshPipelineWidgets.SelectedSortDirection.IsValid())
            {
                StaticMeshPipelineWidgets.SortDirectionCombo->SetSelectedItem(StaticMeshPipelineWidgets.SelectedSortDirection);
            }
        }
        if (StaticMeshPipelineWidgets.ProgressText.IsValid())
        {
            StaticMeshPipelineWidgets.ProgressText->SetText(FText::FromString(State.ProgressText));
        }
        if (StaticMeshPipelineWidgets.ProgressBar.IsValid())
        {
            StaticMeshPipelineWidgets.ProgressBar->SetPercent(FMath::Clamp(State.ProgressPercent, 0.0f, 1.0f));
        }
        if (StaticMeshPipelineWidgets.StatusOutput.IsValid())
        {
            StaticMeshPipelineWidgets.StatusOutput->SetText(FText::FromString(State.StatusText));
        }
        if (StaticMeshPipelineWidgets.DetailOutput.IsValid())
        {
            StaticMeshPipelineWidgets.DetailOutput->SetText(FText::FromString(State.DetailText));
        }

        StaticMeshPipelineWidgets.RowItems = State.Rows;
        if (StaticMeshPipelineWidgets.RowsListView.IsValid())
        {
            StaticMeshPipelineWidgets.RowsListView->RequestListRefresh();

            bUpdatingStaticMeshPipelineSelection = true;
            StaticMeshPipelineWidgets.RowsListView->ClearSelection();
            for (const FStaticMeshPipelineRowPtr &Row : StaticMeshPipelineWidgets.RowItems)
            {
                if (Row.IsValid() && State.SelectedRowKeys.Contains(Row->Key))
                {
                    StaticMeshPipelineWidgets.RowsListView->SetItemSelection(Row, true, ESelectInfo::Direct);
                }
            }
            bUpdatingStaticMeshPipelineSelection = false;
        }
    }

    static void SyncSelectedStaticMeshPipelineRowsToPython()
    {
        if (!StaticMeshPipelineWidgets.RowsListView.IsValid() || bUpdatingStaticMeshPipelineSelection)
        {
            return;
        }

        TArray<FStaticMeshPipelineRowPtr> SelectedItems = StaticMeshPipelineWidgets.RowsListView->GetSelectedItems();
        TArray<FString> SelectedKeys;
        for (const FStaticMeshPipelineRowPtr &Item : SelectedItems)
        {
            if (Item.IsValid() && !Item->Key.IsEmpty())
            {
                SelectedKeys.Add(Item->Key);
            }
        }

        ExecutePython(
            FString::Printf(
                TEXT("import PythonEditorUtility.StaticMeshPipelineTool as tool; tool.set_selected_rows(%s)"),
                *BuildPythonStringListLiteral(SelectedKeys)),
            StaticMeshPipelineTabName);
    }

    static void ExecutePython(const FString &Command, const FName &TabName);

    static void SyncSelectedLightmapRowsToPython()
    {
        if (!LightmapResolutionWidgets.RowsListView.IsValid() || bUpdatingLightmapSelection)
        {
            return;
        }

        TArray<FLightmapResolutionRowPtr> SelectedItems = LightmapResolutionWidgets.RowsListView->GetSelectedItems();
        TArray<FString> SelectedKeys;
        for (const FLightmapResolutionRowPtr &Item : SelectedItems)
        {
            if (Item.IsValid() && !Item->Key.IsEmpty())
            {
                SelectedKeys.Add(Item->Key);
            }
        }

        ExecutePython(
            FString::Printf(
                TEXT("import PythonEditorUtility.LightmapResolutionTool as tool; tool.set_selected_rows(%s)"),
                *BuildPythonStringListLiteral(SelectedKeys)),
            LightmapResolutionTabName);
    }

    static void ExecuteRawPythonCommand(const FString &Command)
    {
        if (Command.IsEmpty())
        {
            return;
        }

        EnsurePythonSearchPath();

        if (IPythonScriptPlugin *PythonPlugin = IPythonScriptPlugin::Get())
        {
            PythonPlugin->ExecPythonCommand(*Command);
        }
    }

    static void SyncWidgetStateFromPython(const FName &TabName)
    {
        ExecuteRawPythonCommand(GetRefreshPythonCommand(TabName));

        if (TabName == LightmapResolutionTabName)
        {
            RefreshLightmapResolutionWidgets();
        }
        else if (TabName == StaticMeshPipelineTabName)
        {
            RefreshStaticMeshPipelineWidgets();
        }
        else
        {
            RefreshOutputTextBox(TabName);
        }
    }

    static FMargin ParsePadding(const TArray<TSharedPtr<FJsonValue>> *PaddingValues)
    {
        if (PaddingValues == nullptr)
        {
            return FMargin(0.0f);
        }

        if (PaddingValues->Num() == 2)
        {
            return FMargin((float)(*PaddingValues)[0]->AsNumber(), (float)(*PaddingValues)[1]->AsNumber());
        }

        if (PaddingValues->Num() != 4)
        {
            return FMargin(0.0f);
        }

        return FMargin(
            (float)(*PaddingValues)[0]->AsNumber(),
            (float)(*PaddingValues)[1]->AsNumber(),
            (float)(*PaddingValues)[2]->AsNumber(),
            (float)(*PaddingValues)[3]->AsNumber());
    }

    static TSharedPtr<FJsonObject> GetFirstChildObject(const TSharedPtr<FJsonObject> &Object, const TSet<FString> &ExcludedFields)
    {
        for (const TPair<FString, TSharedPtr<FJsonValue>> &Pair : Object->Values)
        {
            if (ExcludedFields.Contains(Pair.Key))
            {
                continue;
            }

            if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Object)
            {
                return Pair.Value->AsObject();
            }
        }

        return nullptr;
    }

    static FString GetFirstChildWidgetType(const TSharedPtr<FJsonObject> &Object, const TSet<FString> &ExcludedFields)
    {
        for (const TPair<FString, TSharedPtr<FJsonValue>> &Pair : Object->Values)
        {
            if (ExcludedFields.Contains(Pair.Key))
            {
                continue;
            }

            if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Object)
            {
                return Pair.Key;
            }
        }

        return FString();
    }

    static bool HandlePeuCommand(const FString &Command)
    {
        if (Command.Equals(TEXT("PEU:OpenBuildLighting"), ESearchCase::CaseSensitive))
        {
            FGlobalTabmanager::Get()->TryInvokeTab(BuildLightingTabName);
            SyncWidgetStateFromPython(BuildLightingTabName);
            return true;
        }

        if (Command.Equals(TEXT("PEU:OpenLightmapResolution"), ESearchCase::CaseSensitive))
        {
            FGlobalTabmanager::Get()->TryInvokeTab(LightmapResolutionTabName);
            SyncWidgetStateFromPython(LightmapResolutionTabName);
            return true;
        }

        if (Command.Equals(TEXT("PEU:OpenStaticMeshPipeline"), ESearchCase::CaseSensitive))
        {
            FGlobalTabmanager::Get()->TryInvokeTab(StaticMeshPipelineTabName);
            SyncWidgetStateFromPython(StaticMeshPipelineTabName);
            return true;
        }

        return false;
    }

    static void ExecutePython(const FString &Command, const FName &TabName)
    {
        if (Command.IsEmpty())
        {
            return;
        }

        if (HandlePeuCommand(Command))
        {
            return;
        }

        ExecuteRawPythonCommand(Command);

        if (TabName == LightmapResolutionTabName)
        {
            RefreshLightmapResolutionWidgets();
        }
        else if (TabName == StaticMeshPipelineTabName)
        {
            RefreshStaticMeshPipelineWidgets();
        }
        else
        {
            RefreshOutputTextBox(TabName);
        }
    }

    static TSharedRef<SWidget> BuildWidgetFromDefinition(const FString &WidgetType, const TSharedPtr<FJsonObject> &Definition, const FName &TabName);

    static TSharedRef<SWidget> BuildSlotWidget(const TSharedPtr<FJsonObject> &SlotObject, const FName &TabName)
    {
        const TSet<FString> ExcludedFields = {TEXT("AutoHeight"), TEXT("FillHeight"), TEXT("Column_Row")};
        const FString ChildType = GetFirstChildWidgetType(SlotObject, ExcludedFields);
        const TSharedPtr<FJsonObject> ChildObject = GetFirstChildObject(SlotObject, ExcludedFields);
        if (!ChildObject.IsValid() || ChildType.IsEmpty())
        {
            return SNew(STextBlock).Text(FText::FromString(TEXT("Unsupported slot")));
        }

        return BuildWidgetFromDefinition(ChildType, ChildObject, TabName);
    }

    static TSharedRef<SWidget> BuildVerticalBox(const TSharedPtr<FJsonObject> &Definition, const FName &TabName)
    {
        TSharedRef<SVerticalBox> VerticalBox = SNew(SVerticalBox);
        const TArray<TSharedPtr<FJsonValue>> *Slots = nullptr;
        if (!Definition->TryGetArrayField(TEXT("Slots"), Slots) || Slots == nullptr)
        {
            return VerticalBox;
        }

        for (const TSharedPtr<FJsonValue> &SlotValue : *Slots)
        {
            const TSharedPtr<FJsonObject> SlotObject = SlotValue->AsObject();
            if (!SlotObject.IsValid())
            {
                continue;
            }

            TSharedRef<SWidget> ChildWidget = BuildSlotWidget(SlotObject, TabName);
            if (SlotObject->HasField(TEXT("AutoHeight")))
            {
                VerticalBox->AddSlot()
                    .AutoHeight()
                        [ChildWidget];
            }
            else
            {
                double FillHeight = 0.0;
                if (SlotObject->TryGetNumberField(TEXT("FillHeight"), FillHeight))
                {
                    VerticalBox->AddSlot()
                        .FillHeight((float)FillHeight)
                            [ChildWidget];
                }
                else
                {
                    VerticalBox->AddSlot()
                        .AutoHeight()
                            [ChildWidget];
                }
            }
        }

        return VerticalBox;
    }

    static TSharedRef<SWidget> BuildBorder(const TSharedPtr<FJsonObject> &Definition, const FName &TabName)
    {
        const TArray<TSharedPtr<FJsonValue>> *PaddingValues = nullptr;
        FMargin Padding(0.0f);
        if (Definition->TryGetArrayField(TEXT("Padding"), PaddingValues))
        {
            Padding = ParsePadding(PaddingValues);
        }

        TSharedPtr<FJsonObject> ChildContainer;
        const TSharedPtr<FJsonObject> *ContentObject = nullptr;
        if (Definition->TryGetObjectField(TEXT("Content"), ContentObject) && ContentObject != nullptr)
        {
            ChildContainer = *ContentObject;
        }

        if (!ChildContainer.IsValid())
        {
            const TSet<FString> ExcludedFields = {TEXT("Padding")};
            ChildContainer = GetFirstChildObject(Definition, ExcludedFields);
        }

        const FString ChildType = ChildContainer.IsValid() ? GetFirstChildWidgetType(ChildContainer, {}) : FString();
        const TSharedPtr<FJsonObject> ChildObject = ChildContainer.IsValid() ? GetFirstChildObject(ChildContainer, {}) : nullptr;

        return SNew(SBorder)
            .Padding(Padding)
                [ChildObject.IsValid() ? BuildWidgetFromDefinition(ChildType, ChildObject, TabName) : SNew(STextBlock).Text(FText::FromString(TEXT("Empty border")))];
    }

    static TSharedRef<SWidget> BuildUniformGrid(const TSharedPtr<FJsonObject> &Definition, const FName &TabName)
    {
        TSharedRef<SUniformGridPanel> Grid = SNew(SUniformGridPanel);
        const TArray<TSharedPtr<FJsonValue>> *SlotPaddingValues = nullptr;
        if (Definition->TryGetArrayField(TEXT("SlotPadding"), SlotPaddingValues))
        {
            Grid->SetSlotPadding(ParsePadding(SlotPaddingValues));
        }

        const TArray<TSharedPtr<FJsonValue>> *Slots = nullptr;
        if (!Definition->TryGetArrayField(TEXT("Slots"), Slots) || Slots == nullptr)
        {
            return Grid;
        }

        for (const TSharedPtr<FJsonValue> &SlotValue : *Slots)
        {
            const TSharedPtr<FJsonObject> SlotObject = SlotValue->AsObject();
            if (!SlotObject.IsValid())
            {
                continue;
            }

            const TArray<TSharedPtr<FJsonValue>> *ColumnRow = nullptr;
            int32 Column = 0;
            int32 Row = 0;
            if (SlotObject->TryGetArrayField(TEXT("Column_Row"), ColumnRow) && ColumnRow != nullptr && ColumnRow->Num() == 2)
            {
                Column = (int32)(*ColumnRow)[0]->AsNumber();
                Row = (int32)(*ColumnRow)[1]->AsNumber();
            }

            Grid->AddSlot(Column, Row)
                [BuildSlotWidget(SlotObject, TabName)];
        }

        return Grid;
    }

    static TSharedRef<SWidget> BuildWidgetFromDefinition(const FString &WidgetType, const TSharedPtr<FJsonObject> &Definition, const FName &TabName)
    {
        if (WidgetType == TEXT("SVerticalBox"))
        {
            return BuildVerticalBox(Definition, TabName);
        }
        if (WidgetType == TEXT("SBorder"))
        {
            return BuildBorder(Definition, TabName);
        }
        if (WidgetType == TEXT("STextBlock"))
        {
            return SNew(STextBlock).Text(FText::FromString(Definition->GetStringField(TEXT("Text")))).AutoWrapText(true);
        }
        if (WidgetType == TEXT("SButton"))
        {
            const FString ButtonText = Definition->GetStringField(TEXT("Text"));
            const FString OnClick = Definition->GetStringField(TEXT("OnClick"));
            return SNew(SButton)
                .Text(FText::FromString(ButtonText))
                .OnClicked_Lambda([OnClick, TabName]()
                                  {
                                      ExecutePython(OnClick, TabName);
                                      return FReply::Handled(); });
        }
        if (WidgetType == TEXT("SMultiLineEditableTextBox"))
        {
            bool bReadOnly = false;
            Definition->TryGetBoolField(TEXT("IsReadOnly"), bReadOnly);
            TSharedPtr<SMultiLineEditableTextBox> &OutputTextBox = ToolOutputTextBoxes.FindOrAdd(TabName);
            SAssignNew(OutputTextBox, SMultiLineEditableTextBox)
                .IsReadOnly(bReadOnly)
                .AlwaysShowScrollbars(true)
                .Text(FText::FromString(LoadStatusText(TabName)));
            return OutputTextBox.ToSharedRef();
        }
        if (WidgetType == TEXT("SUniformGridPanel"))
        {
            return BuildUniformGrid(Definition, TabName);
        }

        return SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("Unsupported widget type: %s"), *WidgetType)));
    }

    static TSharedRef<SWidget> BuildWidgetTreeFromJson(const FName &TabName)
    {
        TSharedPtr<FJsonObject> RootObject;
        const FString JsonPath = GetUiJsonPath(TabName);
        if (!LoadJsonObjectFromFile(JsonPath, RootObject))
        {
            return SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("Could not load JSON: %s"), *JsonPath)));
        }

        const TSharedPtr<FJsonObject> *RootDefinition = nullptr;
        if (!RootObject->TryGetObjectField(TEXT("Root"), RootDefinition) || RootDefinition == nullptr || !RootDefinition->IsValid())
        {
            return SNew(STextBlock).Text(FText::FromString(TEXT("Missing Root object in UI definition.")));
        }

        for (const TPair<FString, TSharedPtr<FJsonValue>> &Pair : (*RootDefinition)->Values)
        {
            if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Object)
            {
                return BuildWidgetFromDefinition(Pair.Key, Pair.Value->AsObject(), TabName);
            }
        }

        return SNew(STextBlock).Text(FText::FromString(TEXT("No root widget found in UI definition.")));
    }

    static void InitializeLightmapResolutionOptions()
    {
        if (LightmapResolutionWidgets.SortColumnOptions.Num() == 0)
        {
            LightmapResolutionWidgets.SortColumnOptions = {
                MakeShared<FString>(TEXT("Level")),
                MakeShared<FString>(TEXT("Actor")),
                MakeShared<FString>(TEXT("Component")),
                MakeShared<FString>(TEXT("Mesh")),
                MakeShared<FString>(TEXT("Mobility")),
                MakeShared<FString>(TEXT("Effective")),
                MakeShared<FString>(TEXT("Asset")),
                MakeShared<FString>(TEXT("Override"))};
        }

        if (LightmapResolutionWidgets.SortDirectionOptions.Num() == 0)
        {
            LightmapResolutionWidgets.SortDirectionOptions = {
                MakeShared<FString>(TEXT("Asc")),
                MakeShared<FString>(TEXT("Desc"))};
        }

        if (!LightmapResolutionWidgets.SelectedSortColumn.IsValid())
        {
            LightmapResolutionWidgets.SelectedSortColumn = LightmapResolutionWidgets.SortColumnOptions[0];
        }
        if (!LightmapResolutionWidgets.SelectedSortDirection.IsValid())
        {
            LightmapResolutionWidgets.SelectedSortDirection = LightmapResolutionWidgets.SortDirectionOptions[0];
        }
    }

    static int32 GetLightmapResolutionValue()
    {
        int32 Resolution = 64;
        if (LightmapResolutionWidgets.ResolutionInput.IsValid())
        {
            const FString RawValue = LightmapResolutionWidgets.ResolutionInput->GetText().ToString().TrimStartAndEnd();
            if (!RawValue.IsEmpty())
            {
                Resolution = FMath::Max(1, FCString::Atoi(*RawValue));
            }
        }

        return Resolution;
    }

    static FString GetSelectedSortColumn()
    {
        return LightmapResolutionWidgets.SelectedSortColumn.IsValid() ? *LightmapResolutionWidgets.SelectedSortColumn : TEXT("Level");
    }

    static FString GetSelectedSortDirection()
    {
        return LightmapResolutionWidgets.SelectedSortDirection.IsValid() ? *LightmapResolutionWidgets.SelectedSortDirection : TEXT("Asc");
    }

    static bool IsOpenLevelOnlyChecked()
    {
        return LightmapResolutionWidgets.OpenLevelOnlyCheck.IsValid() && LightmapResolutionWidgets.OpenLevelOnlyCheck->IsChecked();
    }

    static bool IsOverrideOnlyChecked()
    {
        return LightmapResolutionWidgets.OverrideOnlyCheck.IsValid() && LightmapResolutionWidgets.OverrideOnlyCheck->IsChecked();
    }

    static FString BuildLightmapResolutionPythonCommand(const FString &ActionSuffix)
    {
        return FString::Printf(
            TEXT("import PythonEditorUtility.LightmapResolutionTool as tool; tool.set_resolution(%d); tool.set_open_level_only(%s); tool.set_override_only(%s); tool.set_sort('%s', '%s'); %s"),
            GetLightmapResolutionValue(),
            *ToPythonBool(IsOpenLevelOnlyChecked()),
            *ToPythonBool(IsOverrideOnlyChecked()),
            *GetSelectedSortColumn(),
            *GetSelectedSortDirection(),
            *ActionSuffix);
    }

    static TSharedRef<SWidget> BuildLightmapResolutionToolbar()
    {
        InitializeLightmapResolutionOptions();

        return SNew(SBorder)
            .Padding(FMargin(8.0f, 6.0f, 8.0f, 6.0f))
                [SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SButton).Text(FText::FromString(TEXT("Refresh"))).OnClicked_Lambda([]()
                                                                                                                                                                                   {
                                                        ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.refresh_status()")), LightmapResolutionTabName);
                                                        return FReply::Handled(); })] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SBox)
                              .WidthOverride(56.0f)
                                  [SAssignNew(LightmapResolutionWidgets.ResolutionInput, SEditableTextBox)
                                       .Text(FText::FromString(TEXT("64")))
                                       .OnTextCommitted_Lambda([](const FText &, ETextCommit::Type)
                                                               { ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.refresh_status()")), LightmapResolutionTabName); })]] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SAssignNew(LightmapResolutionWidgets.OpenLevelOnlyCheck, SCheckBox)
                              .OnCheckStateChanged_Lambda([](ECheckBoxState)
                                                          { ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.refresh_status()")), LightmapResolutionTabName); })
                                  [SNew(STextBlock).Text(FText::FromString(TEXT("Open Level Only")))]] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SAssignNew(LightmapResolutionWidgets.OverrideOnlyCheck, SCheckBox)
                              .OnCheckStateChanged_Lambda([](ECheckBoxState)
                                                          { ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.refresh_status()")), LightmapResolutionTabName); })
                                  [SNew(STextBlock).Text(FText::FromString(TEXT("Override Only")))]] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SBox)
                              .WidthOverride(130.0f)
                                  [SAssignNew(LightmapResolutionWidgets.SortColumnCombo, SComboBox<TSharedPtr<FString>>)
                                       .OptionsSource(&LightmapResolutionWidgets.SortColumnOptions)
                                       .InitiallySelectedItem(LightmapResolutionWidgets.SelectedSortColumn)
                                       .OnGenerateWidget_Lambda([](TSharedPtr<FString> Item)
                                                                { return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : TEXT(""))); })
                                       .OnSelectionChanged_Lambda([](TSharedPtr<FString> Item, ESelectInfo::Type)
                                                                  {
                                                                          LightmapResolutionWidgets.SelectedSortColumn = Item;
                                                                          ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.refresh_status()")), LightmapResolutionTabName); })
                                           [SNew(STextBlock)
                                                .Text_Lambda([]()
                                                             { return FText::FromString(GetSelectedSortColumn()); })]]] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SBox)
                              .WidthOverride(80.0f)
                                  [SAssignNew(LightmapResolutionWidgets.SortDirectionCombo, SComboBox<TSharedPtr<FString>>)
                                       .OptionsSource(&LightmapResolutionWidgets.SortDirectionOptions)
                                       .InitiallySelectedItem(LightmapResolutionWidgets.SelectedSortDirection)
                                       .OnGenerateWidget_Lambda([](TSharedPtr<FString> Item)
                                                                { return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : TEXT(""))); })
                                       .OnSelectionChanged_Lambda([](TSharedPtr<FString> Item, ESelectInfo::Type)
                                                                  {
                                                                          LightmapResolutionWidgets.SelectedSortDirection = Item;
                                                                          ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.refresh_status()")), LightmapResolutionTabName); })
                                           [SNew(STextBlock)
                                                .Text_Lambda([]()
                                                             { return FText::FromString(GetSelectedSortDirection()); })]]] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SButton)
                              .Text(FText::FromString(TEXT("Apply To Instance")))
                              .OnClicked_Lambda([]()
                                                {
                                                        ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.apply_to_instance()")), LightmapResolutionTabName);
                                                        return FReply::Handled(); })] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SButton)
                              .Text(FText::FromString(TEXT("Clear Instance Override")))
                              .OnClicked_Lambda([]()
                                                {
                                                        ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.clear_instance_override()")), LightmapResolutionTabName);
                                                        return FReply::Handled(); })] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SButton)
                              .Text(FText::FromString(TEXT("Apply To Asset")))
                              .OnClicked_Lambda([]()
                                                {
                                                        ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.apply_to_asset()")), LightmapResolutionTabName);
                                                        return FReply::Handled(); })] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                     .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                         [SNew(SButton)
                              .Text(FText::FromString(TEXT("Open Selected Actor")))
                              .OnClicked_Lambda([]()
                                                {
                                                        ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.open_selected_actor()")), LightmapResolutionTabName);
                                                        return FReply::Handled(); })] +
                 SHorizontalBox::Slot()
                     .AutoWidth()
                         [SNew(SButton)
                              .Text(FText::FromString(TEXT("Sync Selected Asset")))
                              .OnClicked_Lambda([]()
                                                {
                                                        ExecutePython(BuildLightmapResolutionPythonCommand(TEXT("tool.sync_selected_asset()")), LightmapResolutionTabName);
                                                        return FReply::Handled(); })]];
    }

    static TSharedRef<SWidget> BuildStaticMeshPipelineToolbar()
    {
        InitializeStaticMeshPipelineOptions();

        return SNew(SBorder)
            .Padding(FMargin(8.0f, 6.0f, 8.0f, 6.0f))
                [SNew(SVerticalBox) + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 6.0f)[SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SButton).Text(FText::FromString(TEXT("Refresh"))).OnClicked_Lambda([]()
                                                                                                                                                                                                                                                                          {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })] +
                                                                                                        SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SButton).Text(FText::FromString(TEXT("Export All"))).OnClicked_Lambda([]()
                                                                                                                                                                                                                                                      {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.run_export()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })] +
                                                                                                        SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SButton).Text(FText::FromString(TEXT("Import/Reimport All"))).OnClicked_Lambda([]()
                                                                                                                                                                                                                                                               {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.run_import_reimport()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })] +
                                                                                                        SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SButton).Text(FText::FromString(TEXT("Open Audit Report"))).OnClicked_Lambda([]()
                                                                                                                                                                                                                                                             {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.open_last_audit_report()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })] +
                                                                                                        SHorizontalBox::Slot().FillWidth(1.0f)[SNullWidget::NullWidget]] +
                 SVerticalBox::Slot()
                     .AutoHeight()
                     .Padding(0.0f, 0.0f, 0.0f, 6.0f)
                         [SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SBox).WidthOverride(120.0f)[SNew(STextBlock).Text(FText::FromString(TEXT("Export Source")))]] + SHorizontalBox::Slot().FillWidth(1.0f).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SAssignNew(StaticMeshPipelineWidgets.ExportSourceInput, SEditableTextBox).HintText(FText::FromString(TEXT("/Game or /Game/Subfolder"))).OnTextCommitted_Lambda([](const FText &, ETextCommit::Type)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     { ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                                  [SNew(SButton)
                                       .Text(FText::FromString(TEXT("Open Export Folder")))
                                       .OnClicked_Lambda([]()
                                                         {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.open_export_folder()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })]] +
                 SVerticalBox::Slot()
                     .AutoHeight()
                     .Padding(0.0f, 0.0f, 0.0f, 6.0f)
                         [SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SBox).WidthOverride(120.0f)[SNew(STextBlock).Text(FText::FromString(TEXT("Export Destination")))]] + SHorizontalBox::Slot().FillWidth(1.0f).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SAssignNew(StaticMeshPipelineWidgets.ExportDestinationInput, SEditableTextBox).HintText(FText::FromString(TEXT("Filesystem folder"))).OnTextCommitted_Lambda([](const FText &, ETextCommit::Type)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        { ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                              .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                                  [SNew(SButton)
                                       .Text(FText::FromString(TEXT("Browse")))
                                       .OnClicked_Lambda([]()
                                                         {
                                                                     const FString SelectedFolder = BrowseForDirectory(TEXT("Choose Export Destination"), GetStaticMeshPipelineExportDestination());
                                                                     if (!SelectedFolder.IsEmpty() && StaticMeshPipelineWidgets.ExportDestinationInput.IsValid())
                                                                     {
                                                                         StaticMeshPipelineWidgets.ExportDestinationInput->SetText(FText::FromString(SelectedFolder));
                                                                         ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName);
                                                                     }
                                                                     return FReply::Handled(); })] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                                  [SNew(SButton)
                                       .Text(FText::FromString(TEXT("Open Export Folder")))
                                       .OnClicked_Lambda([]()
                                                         {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.open_export_folder()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })]] +
                 SVerticalBox::Slot()
                     .AutoHeight()
                     .Padding(0.0f, 0.0f, 0.0f, 6.0f)
                         [SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SBox).WidthOverride(120.0f)[SNew(STextBlock).Text(FText::FromString(TEXT("Import Source")))]] + SHorizontalBox::Slot().FillWidth(1.0f).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SAssignNew(StaticMeshPipelineWidgets.ImportSourceInput, SEditableTextBox).HintText(FText::FromString(TEXT("Filesystem folder"))).OnTextCommitted_Lambda([](const FText &, ETextCommit::Type)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                              { ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                              .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                                  [SNew(SButton)
                                       .Text(FText::FromString(TEXT("Browse")))
                                       .OnClicked_Lambda([]()
                                                         {
                                                                     const FString SelectedFolder = BrowseForDirectory(TEXT("Choose Import Source"), GetStaticMeshPipelineImportSource());
                                                                     if (!SelectedFolder.IsEmpty() && StaticMeshPipelineWidgets.ImportSourceInput.IsValid())
                                                                     {
                                                                         StaticMeshPipelineWidgets.ImportSourceInput->SetText(FText::FromString(SelectedFolder));
                                                                         ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName);
                                                                     }
                                                                     return FReply::Handled(); })] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                                  [SNew(SButton)
                                       .Text(FText::FromString(TEXT("Open Import Folder")))
                                       .OnClicked_Lambda([]()
                                                         {
                                                                     ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.open_import_source_folder()")), StaticMeshPipelineTabName);
                                                                     return FReply::Handled(); })]] +
                 SVerticalBox::Slot()
                     .AutoHeight()
                     .Padding(0.0f, 0.0f, 0.0f, 6.0f)
                         [SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 6.0f, 0.0f)[SNew(SBox).WidthOverride(120.0f)[SNew(STextBlock).Text(FText::FromString(TEXT("Import Destination")))]] + SHorizontalBox::Slot().FillWidth(1.0f)[SAssignNew(StaticMeshPipelineWidgets.ImportDestinationInput, SEditableTextBox).HintText(FText::FromString(TEXT("/Game or /Game/Subfolder"))).OnTextCommitted_Lambda([](const FText &, ETextCommit::Type)
                                                                                                                                                                                                                                                                                                                                                                                                                                                               { ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })]] +
                 SVerticalBox::Slot()
                     .AutoHeight()
                     .Padding(0.0f, 0.0f, 0.0f, 0.0f)
                         [SNew(SHorizontalBox) + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 12.0f, 0.0f)[SAssignNew(StaticMeshPipelineWidgets.RisksOnlyCheck, SCheckBox).OnCheckStateChanged_Lambda([](ECheckBoxState)
                                                                                                                                                                                                                { ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })[SNew(STextBlock).Text(FText::FromString(TEXT("Risks Only")))]] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                              .VAlign(VAlign_Center)
                              .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                                  [SNew(STextBlock).Text(FText::FromString(TEXT("Sort")))] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                              .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                                  [SNew(SBox)
                                       .WidthOverride(110.0f)
                                           [SAssignNew(StaticMeshPipelineWidgets.SortColumnCombo, SComboBox<TSharedPtr<FString>>)
                                                .OptionsSource(&StaticMeshPipelineWidgets.SortColumnOptions)
                                                .InitiallySelectedItem(StaticMeshPipelineWidgets.SelectedSortColumn)
                                                .OnGenerateWidget_Lambda([](TSharedPtr<FString> Item)
                                                                         { return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : TEXT(""))); })
                                                .OnSelectionChanged_Lambda([](TSharedPtr<FString> Item, ESelectInfo::Type)
                                                                           {
                                                                                       StaticMeshPipelineWidgets.SelectedSortColumn = Item;
                                                                                       ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })
                                                    [SNew(STextBlock)
                                                         .Text_Lambda([]()
                                                                      { return FText::FromString(GetSelectedStaticMeshPipelineSortColumn()); })]]] +
                          SHorizontalBox::Slot()
                              .AutoWidth()
                              .Padding(0.0f, 0.0f, 6.0f, 0.0f)
                                  [SNew(SBox)
                                       .WidthOverride(80.0f)
                                           [SAssignNew(StaticMeshPipelineWidgets.SortDirectionCombo, SComboBox<TSharedPtr<FString>>)
                                                .OptionsSource(&StaticMeshPipelineWidgets.SortDirectionOptions)
                                                .InitiallySelectedItem(StaticMeshPipelineWidgets.SelectedSortDirection)
                                                .OnGenerateWidget_Lambda([](TSharedPtr<FString> Item)
                                                                         { return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : TEXT(""))); })
                                                .OnSelectionChanged_Lambda([](TSharedPtr<FString> Item, ESelectInfo::Type)
                                                                           {
                                                                                       StaticMeshPipelineWidgets.SelectedSortDirection = Item;
                                                                                       ExecutePython(BuildStaticMeshPipelinePythonCommand(TEXT("tool.refresh_status()")), StaticMeshPipelineTabName); })
                                                    [SNew(STextBlock)
                                                         .Text_Lambda([]()
                                                                      { return FText::FromString(GetSelectedStaticMeshPipelineSortDirection()); })]]] +
                          SHorizontalBox::Slot()
                              .FillWidth(1.0f)
                                  [SNullWidget::NullWidget]]];
    }

    static FString GetLightmapResolutionColumnValue(const FLightmapResolutionRowPtr &Item, const FName &ColumnName)
    {
        if (!Item.IsValid())
        {
            return FString();
        }

        if (ColumnName == LevelColumnName)
        {
            return Item->Level;
        }
        if (ColumnName == ActorColumnName)
        {
            return Item->Actor;
        }
        if (ColumnName == ComponentColumnName)
        {
            return Item->Component;
        }
        if (ColumnName == MeshColumnName)
        {
            return Item->Mesh;
        }
        if (ColumnName == MobilityColumnName)
        {
            return Item->Mobility;
        }
        if (ColumnName == EffectiveColumnName)
        {
            return Item->Effective;
        }
        if (ColumnName == AssetColumnName)
        {
            return Item->Asset;
        }
        if (ColumnName == OverrideColumnName)
        {
            return Item->Override;
        }

        return FString();
    }

    static FString GetStaticMeshPipelineColumnValue(const FStaticMeshPipelineRowPtr &Item, const FName &ColumnName)
    {
        if (!Item.IsValid())
        {
            return FString();
        }

        if (ColumnName == PipelineAssetColumnName)
        {
            return Item->Asset;
        }
        if (ColumnName == PipelineActionColumnName)
        {
            return Item->Action;
        }
        if (ColumnName == PipelineResultColumnName)
        {
            return Item->Result;
        }
        if (ColumnName == PipelineOverlapColumnName)
        {
            return Item->Overlap;
        }
        if (ColumnName == PipelineWrappingColumnName)
        {
            return Item->Wrapping;
        }

        return FString();
    }

    class SLightmapResolutionTableRow final : public SMultiColumnTableRow<FLightmapResolutionRowPtr>
    {
    public:
        SLATE_BEGIN_ARGS(SLightmapResolutionTableRow) {}
        SLATE_ARGUMENT(FLightmapResolutionRowPtr, Item)
        SLATE_END_ARGS()

        void Construct(const FArguments &InArgs, const TSharedRef<STableViewBase> &OwnerTableView)
        {
            Item = InArgs._Item;

            SMultiColumnTableRow<FLightmapResolutionRowPtr>::Construct(
                FSuperRowType::FArguments()
                    .Padding(FMargin(0.0f, 1.0f)),
                OwnerTableView);
        }

    protected:
        virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName &ColumnName) override
        {
            return SNew(STextBlock)
                .Text(FText::FromString(GetLightmapResolutionColumnValue(Item, ColumnName)))
                .OverflowPolicy(ETextOverflowPolicy::Ellipsis)
                .Margin(FMargin(6.0f, 2.0f));
        }

    private:
        FLightmapResolutionRowPtr Item;
    };

    class SStaticMeshPipelineTableRow final : public SMultiColumnTableRow<FStaticMeshPipelineRowPtr>
    {
    public:
        SLATE_BEGIN_ARGS(SStaticMeshPipelineTableRow) {}
        SLATE_ARGUMENT(FStaticMeshPipelineRowPtr, Item)
        SLATE_END_ARGS()

        void Construct(const FArguments &InArgs, const TSharedRef<STableViewBase> &OwnerTableView)
        {
            Item = InArgs._Item;

            SMultiColumnTableRow<FStaticMeshPipelineRowPtr>::Construct(
                FSuperRowType::FArguments()
                    .Padding(FMargin(0.0f, 1.0f)),
                OwnerTableView);
        }

    protected:
        virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName &ColumnName) override
        {
            return SNew(STextBlock)
                .Text(FText::FromString(GetStaticMeshPipelineColumnValue(Item, ColumnName)))
                .OverflowPolicy(ETextOverflowPolicy::Ellipsis)
                .Margin(FMargin(6.0f, 2.0f));
        }

    private:
        FStaticMeshPipelineRowPtr Item;
    };

    static TSharedRef<SHeaderRow> BuildLightmapResolutionHeaderRow()
    {
        return SNew(SHeaderRow) + SHeaderRow::Column(LevelColumnName).DefaultLabel(FText::FromString(TEXT("Level"))).ManualWidth(180.0f).MinSize(120.0f) + SHeaderRow::Column(ActorColumnName).DefaultLabel(FText::FromString(TEXT("Actor"))).ManualWidth(360.0f).MinSize(160.0f) + SHeaderRow::Column(ComponentColumnName).DefaultLabel(FText::FromString(TEXT("Component"))).ManualWidth(320.0f).MinSize(160.0f) + SHeaderRow::Column(MeshColumnName).DefaultLabel(FText::FromString(TEXT("Mesh"))).ManualWidth(250.0f).MinSize(150.0f) + SHeaderRow::Column(MobilityColumnName).DefaultLabel(FText::FromString(TEXT("Mobility"))).ManualWidth(120.0f).MinSize(90.0f) + SHeaderRow::Column(EffectiveColumnName).DefaultLabel(FText::FromString(TEXT("Effective"))).ManualWidth(95.0f).MinSize(85.0f) + SHeaderRow::Column(AssetColumnName).DefaultLabel(FText::FromString(TEXT("Asset"))).ManualWidth(95.0f).MinSize(85.0f) + SHeaderRow::Column(OverrideColumnName).DefaultLabel(FText::FromString(TEXT("Override"))).ManualWidth(95.0f).MinSize(85.0f) + SHeaderRow::Column(LightmapResizeSpacerColumnName).FixedWidth(16.0f).ShouldGenerateWidget(false).ShouldGenerateEmptyWidgetForSpacing(true).HeaderComboVisibility(EHeaderComboVisibility::Never);
    }

    static TSharedRef<SHeaderRow> BuildStaticMeshPipelineHeaderRow()
    {
        return SNew(SHeaderRow) + SHeaderRow::Column(PipelineAssetColumnName).DefaultLabel(FText::FromString(TEXT("Asset"))).ManualWidth(280.0f).MinSize(160.0f) + SHeaderRow::Column(PipelineActionColumnName).DefaultLabel(FText::FromString(TEXT("Action"))).ManualWidth(120.0f).MinSize(90.0f) + SHeaderRow::Column(PipelineResultColumnName).DefaultLabel(FText::FromString(TEXT("Result"))).ManualWidth(120.0f).MinSize(90.0f) + SHeaderRow::Column(PipelineOverlapColumnName).DefaultLabel(FText::FromString(TEXT("Overlap"))).ManualWidth(100.0f).MinSize(85.0f) + SHeaderRow::Column(PipelineWrappingColumnName).DefaultLabel(FText::FromString(TEXT("Wrapping"))).ManualWidth(100.0f).MinSize(85.0f) + SHeaderRow::Column(PipelineResizeSpacerColumnName).FixedWidth(16.0f).ShouldGenerateWidget(false).ShouldGenerateEmptyWidgetForSpacing(true).HeaderComboVisibility(EHeaderComboVisibility::Never);
    }

    static TSharedRef<ITableRow> GenerateLightmapResolutionRow(const FLightmapResolutionRowPtr Item, const TSharedRef<STableViewBase> &OwnerTable)
    {
        return SNew(SLightmapResolutionTableRow, OwnerTable)
            .Item(Item);
    }

    static TSharedRef<ITableRow> GenerateStaticMeshPipelineRow(const FStaticMeshPipelineRowPtr Item, const TSharedRef<STableViewBase> &OwnerTable)
    {
        return SNew(SStaticMeshPipelineTableRow, OwnerTable)
            .Item(Item);
    }

    static TSharedRef<SWidget> BuildLightmapResolutionWidget()
    {
        InitializeLightmapResolutionOptions();

        return SNew(SScrollBox) + SScrollBox::Slot()[SNew(SVerticalBox) + SVerticalBox::Slot().AutoHeight()[SNew(SBorder).Padding(FMargin(10.0f))[SNew(STextBlock).Text(FText::FromString(TEXT("Inspect static mesh lightmap resolution across the selected levels. Use Apply To Instance for a per-level override, or Apply To Asset to change the static mesh default."))).AutoWrapText(true)]] + SVerticalBox::Slot().AutoHeight()[BuildLightmapResolutionToolbar()] + SVerticalBox::Slot().AutoHeight()[SNew(SBox).MinDesiredHeight(700.0f)[SNew(SSplitter).Orientation(Orient_Vertical) + SSplitter::Slot().Value(0.12f)[SNew(SBorder).Padding(FMargin(8.0f, 6.0f, 8.0f, 6.0f))[SNew(SVerticalBox) + SVerticalBox::Slot().AutoHeight()[SAssignNew(LightmapResolutionWidgets.ProgressText, STextBlock).Text(FText::FromString(TEXT("Idle")))] + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 0.0f)[SAssignNew(LightmapResolutionWidgets.ProgressBar, SProgressBar).Percent(0.0f)]]] + SSplitter::Slot().Value(0.23f)[SNew(SBorder).Padding(FMargin(8.0f))[SAssignNew(LightmapResolutionWidgets.StatusOutput, SMultiLineEditableTextBox).IsReadOnly(true).AlwaysShowScrollbars(true).Text(FText::FromString(TEXT("Loading...")))]] + SSplitter::Slot().Value(0.43f)[SNew(SBorder).Padding(FMargin(8.0f))[SAssignNew(LightmapResolutionWidgets.RowsListView, SListView<FLightmapResolutionRowPtr>).ListItemsSource(&LightmapResolutionWidgets.RowItems).SelectionMode(ESelectionMode::Multi).HeaderRow(BuildLightmapResolutionHeaderRow()).OnGenerateRow_Static(&GenerateLightmapResolutionRow).OnSelectionChanged_Lambda([](FLightmapResolutionRowPtr, ESelectInfo::Type)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           { SyncSelectedLightmapRowsToPython(); })]] +
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                SSplitter::Slot().Value(0.22f)[SNew(SBorder).Padding(FMargin(8.0f))[SAssignNew(LightmapResolutionWidgets.DetailOutput, SMultiLineEditableTextBox).IsReadOnly(true).AlwaysShowScrollbars(true).Text(FText::FromString(TEXT("Select a row to inspect or edit it.")))]]]]];
    }

    static TSharedRef<SWidget> BuildStaticMeshPipelineWidget()
    {
        InitializeStaticMeshPipelineOptions();

        return SNew(SScrollBox) + SScrollBox::Slot()[SNew(SVerticalBox) + SVerticalBox::Slot().AutoHeight()[SNew(SBorder).Padding(FMargin(10.0f))[SNew(STextBlock).Text(FText::FromString(TEXT("Export project static meshes to the exchange folder, then import or reimport FBX/OBJ files back into Unreal with the lightmap audit summary surfaced below."))).AutoWrapText(true)]] + SVerticalBox::Slot().AutoHeight()[BuildStaticMeshPipelineToolbar()] + SVerticalBox::Slot().AutoHeight()[SNew(SBox).MinDesiredHeight(700.0f)[SNew(SSplitter).Orientation(Orient_Vertical) + SSplitter::Slot().Value(0.12f)[SNew(SBorder).Padding(FMargin(8.0f, 6.0f, 8.0f, 6.0f))[SNew(SVerticalBox) + SVerticalBox::Slot().AutoHeight()[SAssignNew(StaticMeshPipelineWidgets.ProgressText, STextBlock).Text(FText::FromString(TEXT("Idle")))] + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 0.0f)[SAssignNew(StaticMeshPipelineWidgets.ProgressBar, SProgressBar).Percent(0.0f)]]] + SSplitter::Slot().Value(0.25f)[SNew(SBorder).Padding(FMargin(8.0f))[SAssignNew(StaticMeshPipelineWidgets.StatusOutput, SMultiLineEditableTextBox).IsReadOnly(true).AlwaysShowScrollbars(true).Text(FText::FromString(TEXT("Loading...")))]] + SSplitter::Slot().Value(0.38f)[SNew(SBorder).Padding(FMargin(8.0f))[SAssignNew(StaticMeshPipelineWidgets.RowsListView, SListView<FStaticMeshPipelineRowPtr>).ListItemsSource(&StaticMeshPipelineWidgets.RowItems).SelectionMode(ESelectionMode::Multi).HeaderRow(BuildStaticMeshPipelineHeaderRow()).OnGenerateRow_Static(&GenerateStaticMeshPipelineRow).OnSelectionChanged_Lambda([](FStaticMeshPipelineRowPtr, ESelectInfo::Type)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              { SyncSelectedStaticMeshPipelineRowsToPython(); })]] +
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   SSplitter::Slot().Value(0.25f)[SNew(SBorder).Padding(FMargin(8.0f))[SAssignNew(StaticMeshPipelineWidgets.DetailOutput, SMultiLineEditableTextBox).IsReadOnly(true).AlwaysShowScrollbars(true).Text(FText::FromString(TEXT("Select a pipeline row to inspect the export/import result details.")))]]]]];
    }
}

class FPythonEditorUtilityModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        if (IPythonScriptPlugin *PythonPlugin = IPythonScriptPlugin::Get())
        {
            PythonPlugin->RegisterOnPythonInitialized(FSimpleDelegate::CreateStatic(&PythonEditorUtility::EnsurePythonSearchPath));
        }

        PythonEditorUtilityGroup = WorkspaceMenu::GetMenuStructure().GetToolsCategory()->AddGroup(
            FText::FromString(TEXT("Python Editor Utility")),
            FText::FromString(TEXT("Project-owned PythonEditorUtility tabs.")),
            FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("WorkspaceMenu.AdditionalUI")),
            true);

        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(PythonEditorUtility::BuildLightingTabName,
                                                          FOnSpawnTab::CreateRaw(this, &FPythonEditorUtilityModule::SpawnBuildLightingTab))
            .SetDisplayName(FText::FromString(TEXT("Build Lighting")))
            .SetTooltipText(FText::FromString(TEXT("Open the PythonEditorUtility Build Lighting tab.")))
            .SetGroup(PythonEditorUtilityGroup.ToSharedRef());

        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(PythonEditorUtility::LightmapResolutionTabName,
                                                          FOnSpawnTab::CreateRaw(this, &FPythonEditorUtilityModule::SpawnLightmapResolutionTab))
            .SetDisplayName(FText::FromString(TEXT("Lightmap Resolution")))
            .SetTooltipText(FText::FromString(TEXT("Open the PythonEditorUtility Lightmap Resolution tab.")))
            .SetGroup(PythonEditorUtilityGroup.ToSharedRef());

        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(PythonEditorUtility::StaticMeshPipelineTabName,
                                                          FOnSpawnTab::CreateRaw(this, &FPythonEditorUtilityModule::SpawnStaticMeshPipelineTab))
            .SetDisplayName(FText::FromString(TEXT("Static Mesh Pipeline")))
            .SetTooltipText(FText::FromString(TEXT("Open the PythonEditorUtility Static Mesh Pipeline tab.")))
            .SetGroup(PythonEditorUtilityGroup.ToSharedRef());

        UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FPythonEditorUtilityModule::RegisterMenus));
    }

    virtual void ShutdownModule() override
    {
        PythonEditorUtility::ToolOutputTextBoxes.Empty();
        PythonEditorUtility::LightmapResolutionWidgets = PythonEditorUtility::FLightmapResolutionWidgets();
        PythonEditorUtility::StaticMeshPipelineWidgets = PythonEditorUtility::FStaticMeshPipelineWidgets();
        UToolMenus::UnRegisterStartupCallback(this);
        UToolMenus::UnregisterOwner(this);
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(PythonEditorUtility::BuildLightingTabName);
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(PythonEditorUtility::LightmapResolutionTabName);
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(PythonEditorUtility::StaticMeshPipelineTabName);
    }

private:
    TSharedPtr<FWorkspaceItem> PythonEditorUtilityGroup;

    void AddBuildLightingEntry(FToolMenuSection &Section)
    {
        if (Section.FindEntry(TEXT("OpenPythonEditorUtilityBuildLighting")) == nullptr)
        {
            Section.AddMenuEntry(
                TEXT("OpenPythonEditorUtilityBuildLighting"),
                FText::FromString(TEXT("Build Lighting")),
                FText::FromString(TEXT("Open the native PythonEditorUtility Build Lighting widget.")),
                FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("Icons.Tool")),
                FUIAction(FExecuteAction::CreateRaw(this, &FPythonEditorUtilityModule::OpenBuildLightingTab)));
        }
    }

    void AddLightmapResolutionEntry(FToolMenuSection &Section)
    {
        if (Section.FindEntry(TEXT("OpenPythonEditorUtilityLightmapResolution")) == nullptr)
        {
            Section.AddMenuEntry(
                TEXT("OpenPythonEditorUtilityLightmapResolution"),
                FText::FromString(TEXT("Lightmap Resolution")),
                FText::FromString(TEXT("Open the native PythonEditorUtility Lightmap Resolution widget.")),
                FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("Icons.Tool")),
                FUIAction(FExecuteAction::CreateRaw(this, &FPythonEditorUtilityModule::OpenLightmapResolutionTab)));
        }
    }

    void AddStaticMeshPipelineEntry(FToolMenuSection &Section)
    {
        if (Section.FindEntry(TEXT("OpenPythonEditorUtilityStaticMeshPipeline")) == nullptr)
        {
            Section.AddMenuEntry(
                TEXT("OpenPythonEditorUtilityStaticMeshPipeline"),
                FText::FromString(TEXT("Static Mesh Pipeline")),
                FText::FromString(TEXT("Open the combined PythonEditorUtility static mesh export/import widget.")),
                FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("Icons.Tool")),
                FUIAction(FExecuteAction::CreateRaw(this, &FPythonEditorUtilityModule::OpenStaticMeshPipelineTab)));
        }
    }

    void RegisterMenus()
    {
        if (UToolMenu *ToolsMenu = UToolMenus::Get()->ExtendMenu(TEXT("LevelEditor.MainMenu.Tools")))
        {
            FToolMenuSection &Section = ToolsMenu->FindOrAddSection(TEXT("Python"));
            UToolMenu *SubMenu = ToolsMenu->AddSubMenu(
                FToolMenuOwner(this),
                TEXT("Python"),
                TEXT("PythonEditorUtilitySubMenu"),
                FText::FromString(TEXT("Editor Utility Widget")),
                FText::FromString(TEXT("Open PythonEditorUtility widgets.")));

            if (SubMenu != nullptr)
            {
                FToolMenuSection &SubMenuSection = SubMenu->FindOrAddSection(TEXT("PythonEditorUtilityTools"));
                AddBuildLightingEntry(SubMenuSection);
                AddLightmapResolutionEntry(SubMenuSection);
                AddStaticMeshPipelineEntry(SubMenuSection);
                UToolMenus::Get()->RefreshMenuWidget(SubMenu->GetMenuName());
            }
        }

        UToolMenus::Get()->RefreshMenuWidget(TEXT("LevelEditor.MainMenu.Tools"));
    }

    void OpenBuildLightingTab()
    {
        FGlobalTabmanager::Get()->TryInvokeTab(PythonEditorUtility::BuildLightingTabName);
        PythonEditorUtility::SyncWidgetStateFromPython(PythonEditorUtility::BuildLightingTabName);
    }

    void OpenLightmapResolutionTab()
    {
        FGlobalTabmanager::Get()->TryInvokeTab(PythonEditorUtility::LightmapResolutionTabName);
        PythonEditorUtility::SyncWidgetStateFromPython(PythonEditorUtility::LightmapResolutionTabName);
    }

    void OpenStaticMeshPipelineTab()
    {
        FGlobalTabmanager::Get()->TryInvokeTab(PythonEditorUtility::StaticMeshPipelineTabName);
        PythonEditorUtility::SyncWidgetStateFromPython(PythonEditorUtility::StaticMeshPipelineTabName);
    }

    TSharedRef<SDockTab> SpawnBuildLightingTab(const FSpawnTabArgs &Args)
    {
        PythonEditorUtility::EnsurePythonSearchPath();
        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
                [PythonEditorUtility::BuildWidgetTreeFromJson(PythonEditorUtility::BuildLightingTabName)];
    }

    TSharedRef<SDockTab> SpawnLightmapResolutionTab(const FSpawnTabArgs &Args)
    {
        PythonEditorUtility::EnsurePythonSearchPath();
        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
                [PythonEditorUtility::BuildLightmapResolutionWidget()];
    }

    TSharedRef<SDockTab> SpawnStaticMeshPipelineTab(const FSpawnTabArgs &Args)
    {
        PythonEditorUtility::EnsurePythonSearchPath();
        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
                [PythonEditorUtility::BuildStaticMeshPipelineWidget()];
    }
};

IMPLEMENT_MODULE(FPythonEditorUtilityModule, PythonEditorUtility)