#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Docking/TabManager.h"
#include "HAL/FileManager.h"
#include "Interfaces/IPluginManager.h"
#include "IPythonScriptPlugin.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
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
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSplitter.h"
#include "Widgets/Layout/SUniformGridPanel.h"
#include "Widgets/Notifications/SProgressBar.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "WorkspaceMenuStructure.h"
#include "WorkspaceMenuStructureModule.h"

namespace PythonEditorUtility
{
    struct FPythonEditorUtilityIntegrationSettings
    {
        FString PythonRoot = TEXT("PEU/PythonEditorUtility/Python");
        FString UiRoot = TEXT("PEU/PythonEditorUtility/UI");
        FString StateRoot = TEXT("PEU/PythonEditorUtility/State");
        FString PythonPackage = TEXT("PythonEditorUtility");
    };

    struct FDiscoveredToolDefinition
    {
        FString ToolName;
        FString TabLabel;
        FString JsonPath;
        FString StatusFileName;
        FString StateFileName;
        FString Tooltip;
        FString InitPyCmd;
        FName TabId;
        FName MenuEntryName;
    };

    using FStringComboBox = SComboBox<TSharedPtr<FString>>;

    struct FEditableTextWidgetBinding
    {
        FString BindingKey;
        FString StateKey;
        FString OnTextCommittedCmd;
        TWeakPtr<SEditableTextBox> Widget;
    };

    struct FCheckBoxWidgetBinding
    {
        FString BindingKey;
        FString StateKey;
        TWeakPtr<SCheckBox> Widget;
    };

    struct FComboBoxWidgetBinding
    {
        FString BindingKey;
        FString StateKey;
        TWeakPtr<FStringComboBox> Widget;
        TSharedPtr<TArray<TSharedPtr<FString>>> Options;
        TSharedPtr<FString> CurrentValue;
    };

    struct FTextBlockWidgetBinding
    {
        FString StateKey;
        FString Format;
        TWeakPtr<STextBlock> Widget;
    };

    struct FMultiLineTextWidgetBinding
    {
        FString StateKey;
        TWeakPtr<SMultiLineEditableTextBox> Widget;
    };

    struct FProgressBarWidgetBinding
    {
        FString StateKey;
        TWeakPtr<SProgressBar> Widget;
    };

    struct FStateTableColumnDefinition
    {
        FString Id;
        FString Title;
        FString Field;
        float FillWidth = 1.0f;
    };

    struct FStateTableRowData
    {
        FString Key;
        TMap<FString, FString> Cells;
    };

    using FStateTableRowPtr = TSharedPtr<FStateTableRowData>;
    using FStateTableListView = SListView<FStateTableRowPtr>;
    using FStateTableColumnFieldMap = TMap<FName, FString>;

    struct FStateTableWidgetBinding
    {
        FString RowsStateKey;
        FString SelectedKeysStateKey;
        FString OnSelectionChanged;
        bool bAllowMultiSelect = false;
        TArray<FStateTableColumnDefinition> Columns;
        TArray<FStateTableRowPtr> RowItems;
        TWeakPtr<FStateTableListView> Widget;
    };

    class SStateTableRow final : public SMultiColumnTableRow<FStateTableRowPtr>
    {
    public:
        SLATE_BEGIN_ARGS(SStateTableRow) {}
        SLATE_ARGUMENT(FStateTableRowPtr, RowItem)
        SLATE_ARGUMENT(TSharedPtr<FStateTableColumnFieldMap>, ColumnToField)
        SLATE_END_ARGS()

        void Construct(const FArguments &InArgs, const TSharedRef<STableViewBase> &OwnerTableView)
        {
            RowItem = InArgs._RowItem;
            ColumnToField = InArgs._ColumnToField;
            SMultiColumnTableRow<FStateTableRowPtr>::Construct(
                SMultiColumnTableRow<FStateTableRowPtr>::FArguments().Padding(2.0f),
                OwnerTableView);
        }

        virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName &ColumnName) override
        {
            FString CellText;
            if (RowItem.IsValid() && ColumnToField.IsValid())
            {
                if (const FString *FieldName = ColumnToField->Find(ColumnName))
                {
                    if (const FString *Value = RowItem->Cells.Find(*FieldName))
                    {
                        CellText = *Value;
                    }
                }
            }

            return SNew(STextBlock)
                .Text(FText::FromString(CellText))
                .AutoWrapText(false);
        }

    private:
        FStateTableRowPtr RowItem;
        TSharedPtr<FStateTableColumnFieldMap> ColumnToField;
    };

    static TArray<FDiscoveredToolDefinition> DiscoveredTools;
    static TMap<FName, FDiscoveredToolDefinition> ToolsByTabId;
    static TMap<FName, TMap<FString, FString>> ToolStringBindings;
    static TMap<FName, TMap<FString, bool>> ToolBoolBindings;
    static TMap<FName, TMap<FString, TSharedPtr<FJsonValue>>> ToolStateValues;
    static TMap<FName, TArray<FEditableTextWidgetBinding>> ToolEditableTextWidgets;
    static TMap<FName, TArray<FCheckBoxWidgetBinding>> ToolCheckBoxWidgets;
    static TMap<FName, TArray<FComboBoxWidgetBinding>> ToolComboBoxWidgets;
    static TMap<FName, TArray<FTextBlockWidgetBinding>> ToolTextBlockWidgets;
    static TMap<FName, TArray<FMultiLineTextWidgetBinding>> ToolMultiLineTextWidgets;
    static TMap<FName, TArray<FProgressBarWidgetBinding>> ToolProgressBarWidgets;
    static TMap<FName, TArray<TSharedPtr<FStateTableWidgetBinding>>> ToolStateTableWidgets;
    static TMap<FName, TSet<FString>> ToolPendingClearedEditableCommits;
    static TSet<FName> TabsRefreshingBindings;

    static void ExecutePython(const FString &Command, const FName &TabId);
    static FString BrowseForDirectory(const FString &Title, const FString &DefaultPath);
    static FString BrowseForFile(const FString &Title, const FString &DefaultPath, const FString &DefaultFile, const FString &FileTypes);

    static FString NormalizeSettingValue(const FString &Value, const FString &Fallback)
    {
        const FString Trimmed = Value.TrimStartAndEnd();
        return Trimmed.IsEmpty() ? Fallback : Trimmed;
    }

    static FString EscapePythonString(const FString &Value)
    {
        FString Result = Value;
        Result.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
        Result.ReplaceInline(TEXT("'"), TEXT("\\'"));
        Result.ReplaceInline(TEXT("\r"), TEXT("\\r"));
        Result.ReplaceInline(TEXT("\n"), TEXT("\\n"));
        return Result;
    }

    static FString QuotePythonStringLiteral(const FString &Value)
    {
        return FString::Printf(TEXT("'%s'"), *EscapePythonString(Value));
    }

    static FString NormalizeToolLookupKey(const FString &Value)
    {
        FString Result;
        Result.Reserve(Value.Len());
        for (const TCHAR Character : Value)
        {
            if (FChar::IsAlnum(Character))
            {
                Result.AppendChar(FChar::ToLower(Character));
            }
        }
        return Result;
    }

    static FString NormalizeStateLookupKey(const FString &Value)
    {
        return NormalizeToolLookupKey(Value);
    }

    static void SetToolStringBinding(const FName &TabId, const FString &Key, const FString &Value)
    {
        if (!Key.IsEmpty())
        {
            ToolStringBindings.FindOrAdd(TabId).Add(NormalizeStateLookupKey(Key), Value);
        }
    }

    static FString GetToolStringBinding(const FName &TabId, const FString &Key, const FString &Fallback = FString())
    {
        if (const TMap<FString, FString> *Bindings = ToolStringBindings.Find(TabId))
        {
            if (const FString *Value = Bindings->Find(NormalizeStateLookupKey(Key)))
            {
                return *Value;
            }
        }
        return Fallback;
    }

    static void SyncEditableTextWidgetBinding(const FName &TabId, const FString &BindingKey, const FString &Value)
    {
        if (TArray<FEditableTextWidgetBinding> *Widgets = ToolEditableTextWidgets.Find(TabId))
        {
            const FString NormalizedBindingKey = NormalizeStateLookupKey(BindingKey);
            for (const FEditableTextWidgetBinding &Binding : *Widgets)
            {
                if (Binding.BindingKey == NormalizedBindingKey)
                {
                    if (const TSharedPtr<SEditableTextBox> Widget = Binding.Widget.Pin())
                    {
                        Widget->SetText(FText::FromString(Value));
                    }
                }
            }
        }
    }

    static FString TextCommitTypeToString(ETextCommit::Type CommitType)
    {
        switch (CommitType)
        {
        case ETextCommit::Default:
            return TEXT("Default");
        case ETextCommit::OnEnter:
            return TEXT("OnEnter");
        case ETextCommit::OnUserMovedFocus:
            return TEXT("OnUserMovedFocus");
        case ETextCommit::OnCleared:
            return TEXT("OnCleared");
        default:
            return TEXT("Unknown");
        }
    }

    static void SetToolBoolBinding(const FName &TabId, const FString &Key, bool bValue)
    {
        if (!Key.IsEmpty())
        {
            ToolBoolBindings.FindOrAdd(TabId).Add(NormalizeStateLookupKey(Key), bValue);
        }
    }

    static bool GetToolBoolBinding(const FName &TabId, const FString &Key, bool bFallback = false)
    {
        if (const TMap<FString, bool> *Bindings = ToolBoolBindings.Find(TabId))
        {
            if (const bool *Value = Bindings->Find(NormalizeStateLookupKey(Key)))
            {
                return *Value;
            }
        }
        return bFallback;
    }

    static FString ToPythonBool(bool bValue)
    {
        return bValue ? TEXT("True") : TEXT("False");
    }

    static FString ToPythonStringListLiteral(const TArray<FString> &Values)
    {
        TArray<FString> QuotedValues;
        QuotedValues.Reserve(Values.Num());
        for (const FString &Value : Values)
        {
            QuotedValues.Add(QuotePythonStringLiteral(Value));
        }
        return FString::Printf(TEXT("[%s]"), *FString::Join(QuotedValues, TEXT(", ")));
    }

    static void AppendUniqueString(TArray<FString> &Values, const FString &Value)
    {
        if (!Value.IsEmpty())
        {
            Values.AddUnique(Value);
        }
    }

    static FString JsonValueToString(const TSharedPtr<FJsonValue> &Value, const FString &Fallback = FString());

    static TArray<FString> GetJsonStringArray(const TSharedPtr<FJsonValue> &Value)
    {
        TArray<FString> Values;
        if (Value.IsValid() && Value->Type == EJson::Array)
        {
            for (const TSharedPtr<FJsonValue> &Entry : Value->AsArray())
            {
                AppendUniqueString(Values, JsonValueToString(Entry));
            }
        }
        return Values;
    }

    static bool AreStringArraysEquivalent(const TArray<FString> &Left, const TArray<FString> &Right)
    {
        if (Left.Num() != Right.Num())
        {
            return false;
        }

        TSet<FString> LeftSet;
        TSet<FString> RightSet;
        for (const FString &Value : Left)
        {
            LeftSet.Add(Value);
        }
        for (const FString &Value : Right)
        {
            RightSet.Add(Value);
        }
        return LeftSet.Includes(RightSet) && RightSet.Includes(LeftSet);
    }

    static FString ResolveCommandTemplate(const FString &CommandTemplate, const FName &TabId, const FString *CurrentTextValue = nullptr, const bool *CurrentBoolValue = nullptr, const TArray<FString> *CurrentSelectedKeys = nullptr, const FString *CurrentSelectedKey = nullptr)
    {
        FString Resolved = CommandTemplate;
        if (CurrentTextValue != nullptr)
        {
            Resolved.ReplaceInline(TEXT("%Text%"), *QuotePythonStringLiteral(*CurrentTextValue));
            Resolved.ReplaceInline(TEXT("%Value%"), *QuotePythonStringLiteral(*CurrentTextValue));
        }
        if (CurrentBoolValue != nullptr)
        {
            Resolved.ReplaceInline(TEXT("%Checked%"), *ToPythonBool(*CurrentBoolValue));
            Resolved.ReplaceInline(TEXT("%Value%"), *ToPythonBool(*CurrentBoolValue));
        }
        if (CurrentSelectedKey != nullptr)
        {
            Resolved.ReplaceInline(TEXT("%SelectedKey%"), *QuotePythonStringLiteral(*CurrentSelectedKey));
        }
        if (CurrentSelectedKeys != nullptr)
        {
            Resolved.ReplaceInline(TEXT("%SelectedKeys%"), *ToPythonStringListLiteral(*CurrentSelectedKeys));
        }

        if (const TMap<FString, FString> *StringBindings = ToolStringBindings.Find(TabId))
        {
            for (const TPair<FString, FString> &Binding : *StringBindings)
            {
                Resolved.ReplaceInline(*FString::Printf(TEXT("%%Widget:%s%%"), *Binding.Key), *QuotePythonStringLiteral(Binding.Value));
            }
        }
        if (const TMap<FString, bool> *BoolBindings = ToolBoolBindings.Find(TabId))
        {
            for (const TPair<FString, bool> &Binding : *BoolBindings)
            {
                Resolved.ReplaceInline(*FString::Printf(TEXT("%%Widget:%s%%"), *Binding.Key), *ToPythonBool(Binding.Value));
            }
        }

        return Resolved;
    }

    static FString GetPluginDefaultConfigPath()
    {
        const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("PythonEditorUtility"));
        return Plugin.IsValid() ? FPaths::Combine(Plugin->GetBaseDir(), TEXT("Config/DefaultPythonEditorUtility.ini")) : FString();
    }

    static FString GetPluginIdentifier()
    {
        const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("PythonEditorUtility"));
        return Plugin.IsValid() ? Plugin->GetName() : TEXT("PythonEditorUtility");
    }

    static FString GetProjectOverrideConfigPath()
    {
        return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("DefaultPythonEditorUtility.ini"));
    }

    static void ApplyIntegrationSettingsFromFile(const FString &ConfigPath, FPythonEditorUtilityIntegrationSettings &Settings)
    {
        if (ConfigPath.IsEmpty() || !FPaths::FileExists(ConfigPath))
        {
            return;
        }

        FConfigFile ConfigFile;
        ConfigFile.Read(ConfigPath);

        FString Value;
        static const TCHAR *Section = TEXT("PythonEditorUtility.Integration");

        if (ConfigFile.GetString(Section, TEXT("PythonRoot"), Value))
        {
            Settings.PythonRoot = NormalizeSettingValue(Value, Settings.PythonRoot);
        }
        if (ConfigFile.GetString(Section, TEXT("UiRoot"), Value))
        {
            Settings.UiRoot = NormalizeSettingValue(Value, Settings.UiRoot);
        }
        if (ConfigFile.GetString(Section, TEXT("StateRoot"), Value))
        {
            Settings.StateRoot = NormalizeSettingValue(Value, Settings.StateRoot);
        }
        if (ConfigFile.GetString(Section, TEXT("PythonPackage"), Value))
        {
            Settings.PythonPackage = NormalizeSettingValue(Value, Settings.PythonPackage);
        }
    }

    static const FPythonEditorUtilityIntegrationSettings &GetIntegrationSettings()
    {
        static bool bInitialized = false;
        static FPythonEditorUtilityIntegrationSettings Settings;
        if (!bInitialized)
        {
            ApplyIntegrationSettingsFromFile(GetPluginDefaultConfigPath(), Settings);
            ApplyIntegrationSettingsFromFile(GetProjectOverrideConfigPath(), Settings);
            bInitialized = true;
        }
        return Settings;
    }

    static FString ResolveProjectPath(const FString &RelativePath)
    {
        const FString Normalized = RelativePath.TrimStartAndEnd();
        if (Normalized.IsEmpty())
        {
            return FPaths::ProjectDir();
        }
        if (FPaths::IsRelative(Normalized))
        {
            return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), Normalized));
        }
        return FPaths::ConvertRelativePathToFull(Normalized);
    }

    static FString GetPythonPackageName()
    {
        return GetIntegrationSettings().PythonPackage;
    }

    static FString GetToolModuleImportPath(const FString &ToolName)
    {
        return FString::Printf(TEXT("%s.%s"), *GetPythonPackageName(), *ToolName);
    }

    static FString RewriteConfiguredPythonPackage(const FString &Command)
    {
        const FString PackageName = GetPythonPackageName();
        if (PackageName.IsEmpty() || PackageName == TEXT("PythonEditorUtility"))
        {
            return Command;
        }

        FString Rewritten = Command;
        Rewritten.ReplaceInline(TEXT("PythonEditorUtility."), *(PackageName + TEXT(".")));
        Rewritten.ReplaceInline(TEXT("import PythonEditorUtility"), *(TEXT("import ") + PackageName));
        Rewritten.ReplaceInline(TEXT("from PythonEditorUtility"), *(TEXT("from ") + PackageName));
        return Rewritten;
    }

    static bool LoadJsonObjectFromFile(const FString &FilePath, TSharedPtr<FJsonObject> &OutObject)
    {
        FString JsonText;
        if (!FFileHelper::LoadFileToString(JsonText, *FilePath))
        {
            return false;
        }

        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
        return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
    }

    static FString MakeDefaultStatusFileName(const FString &ToolName)
    {
        FString BaseName = ToolName;
        BaseName.RemoveFromEnd(TEXT("Tool"));
        if (BaseName.IsEmpty())
        {
            BaseName = ToolName;
        }
        return BaseName + TEXT("Status.txt");
    }

    static FName MakeTabId(const FString &ToolName)
    {
        return FName(*FString::Printf(TEXT("%s.%s"), *GetPluginIdentifier(), *ToolName));
    }

    static FString GetStatusTextPath(const FName &TabId)
    {
        if (const FDiscoveredToolDefinition *Tool = ToolsByTabId.Find(TabId))
        {
            return FPaths::Combine(ResolveProjectPath(GetIntegrationSettings().StateRoot), Tool->StatusFileName);
        }
        return FString();
    }

    static FString GetStateJsonPath(const FName &TabId)
    {
        if (const FDiscoveredToolDefinition *Tool = ToolsByTabId.Find(TabId))
        {
            return FPaths::Combine(ResolveProjectPath(GetIntegrationSettings().StateRoot), Tool->StateFileName);
        }
        return FString();
    }

    static FString LoadStatusText(const FName &TabId)
    {
        const FString StatusPath = GetStatusTextPath(TabId);
        FString StatusText;
        if (!StatusPath.IsEmpty() && FFileHelper::LoadFileToString(StatusText, *StatusPath))
        {
            return StatusText;
        }
        return TEXT("Loading...");
    }

    static FString MakeDefaultStateFileName(const FString &ToolName)
    {
        FString BaseName = ToolName;
        BaseName.RemoveFromEnd(TEXT("Tool"));
        if (BaseName.IsEmpty())
        {
            BaseName = ToolName;
        }
        return BaseName + TEXT("State.json");
    }

    static FString JsonValueToString(const TSharedPtr<FJsonValue> &Value, const FString &Fallback)
    {
        if (!Value.IsValid())
        {
            return Fallback;
        }

        switch (Value->Type)
        {
        case EJson::String:
            return Value->AsString();
        case EJson::Number:
            return FString::SanitizeFloat(Value->AsNumber());
        case EJson::Boolean:
            return Value->AsBool() ? TEXT("True") : TEXT("False");
        case EJson::Null:
            return FString();
        default:
            return Fallback;
        }
    }

    static bool JsonValueToBool(const TSharedPtr<FJsonValue> &Value, bool bFallback)
    {
        if (!Value.IsValid())
        {
            return bFallback;
        }
        if (Value->Type == EJson::Boolean)
        {
            return Value->AsBool();
        }

        const FString StringValue = JsonValueToString(Value).ToLower();
        if (StringValue == TEXT("true") || StringValue == TEXT("1") || StringValue == TEXT("yes") || StringValue == TEXT("checked"))
        {
            return true;
        }
        if (StringValue == TEXT("false") || StringValue == TEXT("0") || StringValue == TEXT("no") || StringValue == TEXT("unchecked"))
        {
            return false;
        }
        return bFallback;
    }

    static float JsonValueToFloat(const TSharedPtr<FJsonValue> &Value, float Fallback)
    {
        if (!Value.IsValid())
        {
            return Fallback;
        }
        if (Value->Type == EJson::Number)
        {
            return (float)Value->AsNumber();
        }

        const FString StringValue = JsonValueToString(Value);
        return StringValue.IsEmpty() ? Fallback : FCString::Atof(*StringValue);
    }

    static FString GetDefinitionStateKey(const TSharedPtr<FJsonObject> &Definition, const FString &Fallback)
    {
        FString StateKey;
        if (Definition->TryGetStringField(TEXT("StateKey"), StateKey) && !StateKey.TrimStartAndEnd().IsEmpty())
        {
            return NormalizeStateLookupKey(StateKey);
        }
        return NormalizeStateLookupKey(Fallback);
    }

    static void LoadToolStateValues(const FName &TabId)
    {
        TMap<FString, TSharedPtr<FJsonValue>> &StateMap = ToolStateValues.FindOrAdd(TabId);
        StateMap.Empty();

        const FString StatePath = GetStateJsonPath(TabId);
        TSharedPtr<FJsonObject> RootObject;
        if (StatePath.IsEmpty() || !LoadJsonObjectFromFile(StatePath, RootObject))
        {
            return;
        }

        for (const TPair<FString, TSharedPtr<FJsonValue>> &Pair : RootObject->Values)
        {
            StateMap.Add(NormalizeStateLookupKey(Pair.Key), Pair.Value);
        }
    }

    static TSharedPtr<FJsonValue> FindToolStateValue(const FName &TabId, const FString &StateKey)
    {
        if (const TMap<FString, TSharedPtr<FJsonValue>> *StateMap = ToolStateValues.Find(TabId))
        {
            if (const TSharedPtr<FJsonValue> *Value = StateMap->Find(NormalizeStateLookupKey(StateKey)))
            {
                return *Value;
            }
        }
        return nullptr;
    }

    static FString ApplyStateFormat(const FString &Format, const FString &Value)
    {
        if (Format.IsEmpty())
        {
            return Value;
        }

        FString Result = Format;
        Result.ReplaceInline(TEXT("%Value%"), *Value);
        return Result;
    }

    static void RefreshToolOutput(const FName &TabId)
    {
        LoadToolStateValues(TabId);
        TabsRefreshingBindings.Add(TabId);

        if (TArray<FEditableTextWidgetBinding> *Widgets = ToolEditableTextWidgets.Find(TabId))
        {
            for (const FEditableTextWidgetBinding &Binding : *Widgets)
            {
                if (const TSharedPtr<SEditableTextBox> Widget = Binding.Widget.Pin())
                {
                    const FString StateValue = JsonValueToString(FindToolStateValue(TabId, Binding.StateKey), GetToolStringBinding(TabId, Binding.BindingKey));
                    SetToolStringBinding(TabId, Binding.BindingKey, StateValue);
                    Widget->SetText(FText::FromString(StateValue));
                }
            }
        }

        if (TArray<FCheckBoxWidgetBinding> *Widgets = ToolCheckBoxWidgets.Find(TabId))
        {
            for (const FCheckBoxWidgetBinding &Binding : *Widgets)
            {
                if (const TSharedPtr<SCheckBox> Widget = Binding.Widget.Pin())
                {
                    const bool bStateValue = JsonValueToBool(FindToolStateValue(TabId, Binding.StateKey), GetToolBoolBinding(TabId, Binding.BindingKey));
                    SetToolBoolBinding(TabId, Binding.BindingKey, bStateValue);
                    Widget->SetIsChecked(bStateValue ? ECheckBoxState::Checked : ECheckBoxState::Unchecked);
                }
            }
        }

        if (TArray<FComboBoxWidgetBinding> *Widgets = ToolComboBoxWidgets.Find(TabId))
        {
            for (const FComboBoxWidgetBinding &Binding : *Widgets)
            {
                if (const TSharedPtr<FStringComboBox> Widget = Binding.Widget.Pin())
                {
                    FString SelectedText = JsonValueToString(FindToolStateValue(TabId, Binding.StateKey), GetToolStringBinding(TabId, Binding.BindingKey));
                    if (SelectedText.IsEmpty() && Binding.Options.IsValid() && Binding.Options->Num() > 0)
                    {
                        SelectedText = *(*Binding.Options)[0];
                    }

                    TSharedPtr<FString> SelectedItem;
                    if (Binding.Options.IsValid())
                    {
                        for (const TSharedPtr<FString> &Option : *Binding.Options)
                        {
                            if (Option.IsValid() && *Option == SelectedText)
                            {
                                SelectedItem = Option;
                                break;
                            }
                        }
                    }

                    if (!SelectedItem.IsValid() && Binding.Options.IsValid() && Binding.Options->Num() > 0)
                    {
                        SelectedItem = (*Binding.Options)[0];
                        SelectedText = *SelectedItem;
                    }

                    if (Binding.CurrentValue.IsValid())
                    {
                        *Binding.CurrentValue = SelectedText;
                    }
                    SetToolStringBinding(TabId, Binding.BindingKey, SelectedText);
                    if (SelectedItem.IsValid())
                    {
                        Widget->SetSelectedItem(SelectedItem);
                    }
                }
            }
        }

        if (TArray<FTextBlockWidgetBinding> *Widgets = ToolTextBlockWidgets.Find(TabId))
        {
            for (const FTextBlockWidgetBinding &Binding : *Widgets)
            {
                if (const TSharedPtr<STextBlock> Widget = Binding.Widget.Pin())
                {
                    const FString StateValue = JsonValueToString(FindToolStateValue(TabId, Binding.StateKey));
                    Widget->SetText(FText::FromString(ApplyStateFormat(Binding.Format, StateValue)));
                }
            }
        }

        if (TArray<FMultiLineTextWidgetBinding> *Widgets = ToolMultiLineTextWidgets.Find(TabId))
        {
            for (const FMultiLineTextWidgetBinding &Binding : *Widgets)
            {
                if (const TSharedPtr<SMultiLineEditableTextBox> Widget = Binding.Widget.Pin())
                {
                    const FString FallbackText = Binding.StateKey.IsEmpty() ? LoadStatusText(TabId) : FString();
                    const FString StateValue = JsonValueToString(FindToolStateValue(TabId, Binding.StateKey), FallbackText);
                    Widget->SetText(FText::FromString(StateValue));
                }
            }
        }

        if (TArray<FProgressBarWidgetBinding> *Widgets = ToolProgressBarWidgets.Find(TabId))
        {
            for (const FProgressBarWidgetBinding &Binding : *Widgets)
            {
                if (const TSharedPtr<SProgressBar> Widget = Binding.Widget.Pin())
                {
                    Widget->SetPercent(JsonValueToFloat(FindToolStateValue(TabId, Binding.StateKey), 0.0f));
                }
            }
        }

        if (TArray<TSharedPtr<FStateTableWidgetBinding>> *Widgets = ToolStateTableWidgets.Find(TabId))
        {
            for (const TSharedPtr<FStateTableWidgetBinding> &Binding : *Widgets)
            {
                if (!Binding.IsValid())
                {
                    continue;
                }

                Binding->RowItems.Empty();
                const TSharedPtr<FJsonValue> RowsValue = FindToolStateValue(TabId, Binding->RowsStateKey);
                if (RowsValue.IsValid() && RowsValue->Type == EJson::Array)
                {
                    for (const TSharedPtr<FJsonValue> &RowValue : RowsValue->AsArray())
                    {
                        const TSharedPtr<FJsonObject> RowObject = RowValue->AsObject();
                        if (!RowObject.IsValid())
                        {
                            continue;
                        }

                        FStateTableRowPtr RowItem = MakeShared<FStateTableRowData>();
                        RowItem->Key = JsonValueToString(RowObject->TryGetField(TEXT("key")));
                        for (const TPair<FString, TSharedPtr<FJsonValue>> &Pair : RowObject->Values)
                        {
                            RowItem->Cells.Add(NormalizeStateLookupKey(Pair.Key), JsonValueToString(Pair.Value));
                        }
                        Binding->RowItems.Add(RowItem);
                    }
                }

                if (const TSharedPtr<FStateTableListView> Widget = Binding->Widget.Pin())
                {
                    Widget->RequestListRefresh();
                    Widget->ClearSelection();

                    const TArray<FString> SelectedKeys = GetJsonStringArray(FindToolStateValue(TabId, Binding->SelectedKeysStateKey));

                    for (const FStateTableRowPtr &RowItem : Binding->RowItems)
                    {
                        if (RowItem.IsValid() && SelectedKeys.Contains(RowItem->Key))
                        {
                            Widget->SetItemSelection(RowItem, true, ESelectInfo::Direct);
                        }
                    }
                }
            }
        }

        TabsRefreshingBindings.Remove(TabId);
    }

    static const FDiscoveredToolDefinition *FindToolByTabId(const FName &TabId)
    {
        return ToolsByTabId.Find(TabId);
    }

    static const FDiscoveredToolDefinition *FindToolByIdentifier(const FString &Identifier)
    {
        const FString LookupKey = NormalizeToolLookupKey(Identifier);
        if (LookupKey.IsEmpty())
        {
            return nullptr;
        }

        for (const FDiscoveredToolDefinition &Tool : DiscoveredTools)
        {
            if (NormalizeToolLookupKey(Tool.ToolName) == LookupKey || NormalizeToolLookupKey(Tool.TabLabel) == LookupKey)
            {
                return &Tool;
            }

            FString ToolNameWithoutSuffix = Tool.ToolName;
            ToolNameWithoutSuffix.RemoveFromEnd(TEXT("Tool"));
            if (NormalizeToolLookupKey(ToolNameWithoutSuffix) == LookupKey)
            {
                return &Tool;
            }
        }

        return nullptr;
    }

    static void EnsurePythonSearchPath()
    {
        const FString PythonRoot = ResolveProjectPath(GetIntegrationSettings().PythonRoot);
        if (PythonRoot.IsEmpty())
        {
            return;
        }

        if (IPythonScriptPlugin *PythonPlugin = IPythonScriptPlugin::Get())
        {
            const FString Command = FString::Printf(
                TEXT("import os, sys; path=os.path.normpath('%s'); existing=[os.path.normpath(p) for p in sys.path]; sys.path.insert(0, path) if path not in existing else None"),
                *EscapePythonString(PythonRoot));
            PythonPlugin->ExecPythonCommand(*Command);
        }
    }

    static bool HandlePeuCommand(const FString &Command, const FName &TabId)
    {
        if (!Command.StartsWith(TEXT("PEU:")))
        {
            return false;
        }

        FString Payload = Command.RightChop(4).TrimStartAndEnd();

        if (Payload.StartsWith(TEXT("BrowseFolder:")))
        {
            const FString Aka = Payload.RightChop(13).TrimStartAndEnd();
            const FString BindingKey = NormalizeStateLookupKey(Aka);
            const FString CurrentValue = GetToolStringBinding(TabId, BindingKey);
            const FString SelectedFolder = BrowseForDirectory(
                FString::Printf(TEXT("Choose %s"), *Aka), CurrentValue);
            if (!SelectedFolder.IsEmpty())
            {
                SetToolStringBinding(TabId, BindingKey, SelectedFolder);
                SyncEditableTextWidgetBinding(TabId, BindingKey, SelectedFolder);
                if (TArray<FEditableTextWidgetBinding> *Widgets = ToolEditableTextWidgets.Find(TabId))
                {
                    for (const FEditableTextWidgetBinding &Binding : *Widgets)
                    {
                        if (Binding.BindingKey == BindingKey && !Binding.OnTextCommittedCmd.IsEmpty())
                        {
                            ExecutePython(ResolveCommandTemplate(Binding.OnTextCommittedCmd, TabId, &SelectedFolder, nullptr), TabId);
                            break;
                        }
                    }
                }
            }
            return true;
        }

        if (Payload.StartsWith(TEXT("BrowseFile:")))
        {
            const FString Aka = Payload.RightChop(11).TrimStartAndEnd();
            const FString BindingKey = NormalizeStateLookupKey(Aka);
            const FString CurrentValue = GetToolStringBinding(TabId, BindingKey);
            const FString DefaultPath = FPaths::GetPath(CurrentValue);
            const FString DefaultFile = FPaths::GetCleanFilename(CurrentValue);
            const FString SelectedFile = BrowseForFile(
                FString::Printf(TEXT("Choose %s"), *Aka),
                DefaultPath, DefaultFile, TEXT("All files|*.*"));
            if (!SelectedFile.IsEmpty())
            {
                SetToolStringBinding(TabId, BindingKey, SelectedFile);
                SyncEditableTextWidgetBinding(TabId, BindingKey, SelectedFile);
                if (TArray<FEditableTextWidgetBinding> *Widgets = ToolEditableTextWidgets.Find(TabId))
                {
                    for (const FEditableTextWidgetBinding &Binding : *Widgets)
                    {
                        if (Binding.BindingKey == BindingKey && !Binding.OnTextCommittedCmd.IsEmpty())
                        {
                            ExecutePython(ResolveCommandTemplate(Binding.OnTextCommittedCmd, TabId, &SelectedFile, nullptr), TabId);
                            break;
                        }
                    }
                }
            }
            return true;
        }

        if (Payload.StartsWith(TEXT("OpenTool:")))
        {
            Payload = Payload.RightChop(9).TrimStartAndEnd();
        }
        else if (Payload.StartsWith(TEXT("Open")))
        {
            Payload = Payload.RightChop(4).TrimStartAndEnd();
        }

        if (const FDiscoveredToolDefinition *Tool = FindToolByIdentifier(Payload))
        {
            FGlobalTabmanager::Get()->TryInvokeTab(Tool->TabId);
            RefreshToolOutput(Tool->TabId);
            return true;
        }

        return true;
    }

    static void ExecutePython(const FString &Command, const FName &TabId)
    {
        EnsurePythonSearchPath();
        if (HandlePeuCommand(Command, TabId))
        {
            RefreshToolOutput(TabId);
            return;
        }

        if (IPythonScriptPlugin *PythonPlugin = IPythonScriptPlugin::Get())
        {
            const FString RewrittenCommand = RewriteConfiguredPythonPackage(Command);
            PythonPlugin->ExecPythonCommand(*RewrittenCommand);
        }

        RefreshToolOutput(TabId);
    }

    static void RunInitPython(const FDiscoveredToolDefinition &Tool)
    {
        FString InitCommand = Tool.InitPyCmd.TrimStartAndEnd();
        if (InitCommand.IsEmpty())
        {
            InitCommand = FString::Printf(TEXT("import %s as tool; tool.refresh_status()"), *GetToolModuleImportPath(Tool.ToolName));
        }
        else
        {
            const FString QuotedJsonPath = FString::Printf(TEXT("'%s'"), *EscapePythonString(Tool.JsonPath));
            InitCommand = InitCommand.Replace(TEXT("%JsonPath"), *QuotedJsonPath);
        }

        ExecutePython(InitCommand, Tool.TabId);
    }

    static const TSharedPtr<FJsonObject> GetFirstChildObject(const TSharedPtr<FJsonObject> &Object, const TSet<FString> &ExcludedFields)
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
            if (!ExcludedFields.Contains(Pair.Key) && Pair.Value.IsValid() && Pair.Value->Type == EJson::Object)
            {
                return Pair.Key;
            }
        }
        return FString();
    }

    static FMargin ParsePadding(const TArray<TSharedPtr<FJsonValue>> *PaddingValues)
    {
        if (PaddingValues == nullptr)
        {
            return FMargin(0.0f);
        }
        if (PaddingValues->Num() == 1)
        {
            return FMargin((float)(*PaddingValues)[0]->AsNumber());
        }
        if (PaddingValues->Num() == 2)
        {
            return FMargin((float)(*PaddingValues)[0]->AsNumber(), (float)(*PaddingValues)[1]->AsNumber());
        }
        if (PaddingValues->Num() == 4)
        {
            return FMargin(
                (float)(*PaddingValues)[0]->AsNumber(),
                (float)(*PaddingValues)[1]->AsNumber(),
                (float)(*PaddingValues)[2]->AsNumber(),
                (float)(*PaddingValues)[3]->AsNumber());
        }
        return FMargin(0.0f);
    }

    static bool IsLikelyAssetPath(const FString &Value)
    {
        return Value.StartsWith(TEXT("/Game")) || Value.StartsWith(TEXT("/Engine")) || Value.StartsWith(TEXT("/Script"));
    }

    static FString FindExistingParentDirectory(const FString &Path)
    {
        FString Candidate = Path;
        IFileManager &FileManager = IFileManager::Get();

        while (!Candidate.IsEmpty())
        {
            if (FileManager.DirectoryExists(*Candidate))
            {
                return Candidate;
            }

            const FString Parent = FPaths::GetPath(Candidate);
            if (Parent.IsEmpty() || Parent == Candidate)
            {
                break;
            }
            Candidate = Parent;
        }

        return FString();
    }

    static FString ResolveDialogDefaultDirectory(const FString &RawPath)
    {
        FString ProjectDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
        FPaths::NormalizeDirectoryName(ProjectDir);

        FString Candidate = RawPath.TrimStartAndEnd();
        if (Candidate.IsEmpty() || IsLikelyAssetPath(Candidate))
        {
            return ProjectDir;
        }

        Candidate = FPaths::ConvertRelativePathToFull(Candidate);
        FPaths::NormalizeFilename(Candidate);

        IFileManager &FileManager = IFileManager::Get();
        if (FileManager.FileExists(*Candidate))
        {
            Candidate = FPaths::GetPath(Candidate);
        }

        FString ExistingDirectory = FindExistingParentDirectory(Candidate);
        if (ExistingDirectory.IsEmpty())
        {
            return ProjectDir;
        }

        FPaths::NormalizeDirectoryName(ExistingDirectory);
        return ExistingDirectory;
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
        const FString InitialDirectory = ResolveDialogDefaultDirectory(DefaultPath);
        const bool bOpened = DesktopPlatform->OpenDirectoryDialog(ParentWindowHandle, Title, InitialDirectory, SelectedFolder);
        return bOpened ? SelectedFolder : FString();
    }

    static FString BrowseForFile(const FString &Title, const FString &DefaultPath, const FString &DefaultFile, const FString &FileTypes)
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

        TArray<FString> SelectedFiles;
        const FString InitialDirectory = ResolveDialogDefaultDirectory(DefaultPath);
        const bool bOpened = DesktopPlatform->OpenFileDialog(
            ParentWindowHandle,
            Title,
            InitialDirectory,
            DefaultFile,
            FileTypes,
            EFileDialogFlags::None,
            SelectedFiles);
        return bOpened && SelectedFiles.Num() > 0 ? SelectedFiles[0] : FString();
    }

    static TSharedRef<SWidget> BuildWidgetFromDefinition(const FString &WidgetType, const TSharedPtr<FJsonObject> &Definition, const FName &TabId);

    static void ResetToolWidgetRegistry(const FName &TabId)
    {
        ToolStringBindings.Remove(TabId);
        ToolBoolBindings.Remove(TabId);
        ToolStateValues.Remove(TabId);
        ToolEditableTextWidgets.Remove(TabId);
        ToolCheckBoxWidgets.Remove(TabId);
        ToolComboBoxWidgets.Remove(TabId);
        ToolTextBlockWidgets.Remove(TabId);
        ToolMultiLineTextWidgets.Remove(TabId);
        ToolProgressBarWidgets.Remove(TabId);
        ToolStateTableWidgets.Remove(TabId);
    }

    static TSharedRef<SWidget> BuildSlotWidget(const TSharedPtr<FJsonObject> &SlotObject, const FName &TabId)
    {
        const TSet<FString> ExcludedFields = {TEXT("AutoHeight"), TEXT("FillHeight"), TEXT("AutoWidth"), TEXT("FillWidth"), TEXT("Padding"), TEXT("Column_Row")};
        const FString ChildType = GetFirstChildWidgetType(SlotObject, ExcludedFields);
        const TSharedPtr<FJsonObject> ChildObject = GetFirstChildObject(SlotObject, ExcludedFields);
        if (!ChildObject.IsValid() || ChildType.IsEmpty())
        {
            return SNew(STextBlock).Text(FText::FromString(TEXT("Unsupported slot")));
        }
        return BuildWidgetFromDefinition(ChildType, ChildObject, TabId);
    }

    static TSharedRef<SWidget> BuildVerticalBox(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
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

            TSharedRef<SWidget> ChildWidget = BuildSlotWidget(SlotObject, TabId);

            const TArray<TSharedPtr<FJsonValue>> *SlotPaddingValues = nullptr;
            FMargin SlotPadding(0.0f);
            if (SlotObject->TryGetArrayField(TEXT("Padding"), SlotPaddingValues))
            {
                SlotPadding = ParsePadding(SlotPaddingValues);
            }

            double FillHeight = 0.0;
            if (SlotObject->TryGetNumberField(TEXT("FillHeight"), FillHeight))
            {
                VerticalBox->AddSlot().FillHeight((float)FillHeight).Padding(SlotPadding)[ChildWidget];
            }
            else
            {
                VerticalBox->AddSlot().AutoHeight().Padding(SlotPadding)[ChildWidget];
            }
        }

        return VerticalBox;
    }

    static TSharedRef<SWidget> BuildHorizontalBox(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
    {
        TSharedRef<SHorizontalBox> HorizontalBox = SNew(SHorizontalBox);
        const TArray<TSharedPtr<FJsonValue>> *Slots = nullptr;
        if (!Definition->TryGetArrayField(TEXT("Slots"), Slots) || Slots == nullptr)
        {
            return HorizontalBox;
        }

        for (const TSharedPtr<FJsonValue> &SlotValue : *Slots)
        {
            const TSharedPtr<FJsonObject> SlotObject = SlotValue->AsObject();
            if (!SlotObject.IsValid())
            {
                continue;
            }

            TSharedRef<SWidget> ChildWidget = BuildSlotWidget(SlotObject, TabId);

            const TArray<TSharedPtr<FJsonValue>> *SlotPaddingValues = nullptr;
            FMargin SlotPadding(0.0f);
            if (SlotObject->TryGetArrayField(TEXT("Padding"), SlotPaddingValues))
            {
                SlotPadding = ParsePadding(SlotPaddingValues);
            }

            double FillWidth = 0.0;
            if (SlotObject->TryGetNumberField(TEXT("FillWidth"), FillWidth))
            {
                HorizontalBox->AddSlot().FillWidth((float)FillWidth).Padding(SlotPadding)[ChildWidget];
            }
            else
            {
                HorizontalBox->AddSlot().AutoWidth().Padding(SlotPadding)[ChildWidget];
            }
        }

        return HorizontalBox;
    }

    static TSharedRef<SWidget> BuildScrollBox(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
    {
        TSharedRef<SScrollBox> ScrollBox = SNew(SScrollBox);
        const TArray<TSharedPtr<FJsonValue>> *Slots = nullptr;
        if (!Definition->TryGetArrayField(TEXT("Slots"), Slots) || Slots == nullptr)
        {
            return ScrollBox;
        }

        for (const TSharedPtr<FJsonValue> &SlotValue : *Slots)
        {
            const TSharedPtr<FJsonObject> SlotObject = SlotValue->AsObject();
            if (!SlotObject.IsValid())
            {
                continue;
            }

            ScrollBox->AddSlot()[BuildSlotWidget(SlotObject, TabId)];
        }

        return ScrollBox;
    }

    static TSharedRef<SWidget> BuildSplitter(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
    {
        TSharedRef<SSplitter> Splitter = SNew(SSplitter);

        FString Orientation;
        if (Definition->TryGetStringField(TEXT("Orientation"), Orientation) && Orientation.Equals(TEXT("Vertical"), ESearchCase::IgnoreCase))
        {
            Splitter->SetOrientation(Orient_Vertical);
        }
        else
        {
            Splitter->SetOrientation(Orient_Horizontal);
        }

        const TArray<TSharedPtr<FJsonValue>> *Slots = nullptr;
        if (!Definition->TryGetArrayField(TEXT("Slots"), Slots) || Slots == nullptr)
        {
            return Splitter;
        }

        for (const TSharedPtr<FJsonValue> &SlotValue : *Slots)
        {
            const TSharedPtr<FJsonObject> SlotObject = SlotValue->AsObject();
            if (!SlotObject.IsValid())
            {
                continue;
            }

            double SizeValue = 1.0;
            SlotObject->TryGetNumberField(TEXT("Value"), SizeValue);
            Splitter->AddSlot()
                .Value((float)SizeValue)
                    [BuildSlotWidget(SlotObject, TabId)];
        }

        return Splitter;
    }

    static TSharedRef<SWidget> BuildStateTable(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
    {
        FString RowsStateKey;
        FString SelectedKeysStateKey;
        FString OnSelectionChanged;
        FString SelectionMode;
        Definition->TryGetStringField(TEXT("RowsStateKey"), RowsStateKey);
        Definition->TryGetStringField(TEXT("SelectedKeysStateKey"), SelectedKeysStateKey);
        Definition->TryGetStringField(TEXT("OnSelectionChanged"), OnSelectionChanged);
        Definition->TryGetStringField(TEXT("SelectionMode"), SelectionMode);

        TSharedPtr<FStateTableWidgetBinding> Binding = MakeShared<FStateTableWidgetBinding>();
        Binding->RowsStateKey = GetDefinitionStateKey(Definition, RowsStateKey);
        Binding->SelectedKeysStateKey = GetDefinitionStateKey(Definition, SelectedKeysStateKey);
        Binding->OnSelectionChanged = OnSelectionChanged;
        Binding->bAllowMultiSelect = SelectionMode.Equals(TEXT("Multi"), ESearchCase::IgnoreCase);

        TSharedRef<SHeaderRow> HeaderRow = SNew(SHeaderRow);
        TSharedPtr<FStateTableColumnFieldMap> ColumnToField = MakeShared<FStateTableColumnFieldMap>();

        const TArray<TSharedPtr<FJsonValue>> *Columns = nullptr;
        if (Definition->TryGetArrayField(TEXT("Columns"), Columns) && Columns != nullptr)
        {
            for (const TSharedPtr<FJsonValue> &ColumnValue : *Columns)
            {
                const TSharedPtr<FJsonObject> ColumnObject = ColumnValue->AsObject();
                if (!ColumnObject.IsValid())
                {
                    continue;
                }

                FStateTableColumnDefinition Column;
                ColumnObject->TryGetStringField(TEXT("Id"), Column.Id);
                ColumnObject->TryGetStringField(TEXT("Title"), Column.Title);
                ColumnObject->TryGetStringField(TEXT("Field"), Column.Field);
                double FillWidth = 1.0;
                if (ColumnObject->TryGetNumberField(TEXT("FillWidth"), FillWidth))
                {
                    Column.FillWidth = (float)FillWidth;
                }

                if (Column.Id.IsEmpty())
                {
                    Column.Id = Column.Field;
                }
                if (Column.Title.IsEmpty())
                {
                    Column.Title = Column.Id;
                }

                Binding->Columns.Add(Column);
                ColumnToField->Add(FName(*Column.Id), NormalizeStateLookupKey(Column.Field));
                HeaderRow->AddColumn(
                    SHeaderRow::Column(FName(*Column.Id))
                        .DefaultLabel(FText::FromString(Column.Title))
                        .FillWidth(Column.FillWidth));
            }
        }

        TSharedPtr<FStateTableListView> TableWidget;
        SAssignNew(TableWidget, FStateTableListView)
            .ListItemsSource(&Binding->RowItems)
            .SelectionMode(Binding->bAllowMultiSelect ? ESelectionMode::Multi : ESelectionMode::Single)
            .HeaderRow(HeaderRow)
            .OnGenerateRow_Lambda([ColumnToField](FStateTableRowPtr RowItem, const TSharedRef<STableViewBase> &OwnerTable)
                                  { return SNew(SStateTableRow, OwnerTable)
                                        .RowItem(RowItem)
                                        .ColumnToField(ColumnToField); })
            .OnSelectionChanged_Lambda([Binding, TabId](FStateTableRowPtr, ESelectInfo::Type SelectInfo)
                                       {
                if (TabsRefreshingBindings.Contains(TabId) || !Binding.IsValid() || SelectInfo == ESelectInfo::Direct)
                {
                    return;
                }

                if (const TSharedPtr<FStateTableListView> Widget = Binding->Widget.Pin())
                {
                    TArray<FStateTableRowPtr> SelectedRows;
                    Widget->GetSelectedItems(SelectedRows);

                    TArray<FString> SelectedKeys;
                    for (const FStateTableRowPtr &SelectedRow : SelectedRows)
                    {
                        if (SelectedRow.IsValid())
                        {
                            AppendUniqueString(SelectedKeys, SelectedRow->Key);
                        }
                    }

                    const TArray<FString> ExistingSelectedKeys =
                        GetJsonStringArray(FindToolStateValue(TabId, Binding->SelectedKeysStateKey));

                    if (AreStringArraysEquivalent(SelectedKeys, ExistingSelectedKeys))
                    {
                        return;
                    }

                    if (SelectedKeys.Num() == 0 && ExistingSelectedKeys.Num() > 0)
                    {
                        return;
                    }

                    if (!Binding->OnSelectionChanged.IsEmpty())
                    {
                        const FString FirstKey = SelectedKeys.Num() > 0 ? SelectedKeys[0] : FString();
                        ExecutePython(ResolveCommandTemplate(Binding->OnSelectionChanged, TabId, nullptr, nullptr, &SelectedKeys, &FirstKey), TabId);
                    }
                } });

        Binding->Widget = TableWidget;
        ToolStateTableWidgets.FindOrAdd(TabId).Add(Binding);
        return TableWidget.ToSharedRef();
    }

    static TSharedRef<SWidget> BuildBorder(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
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
            ChildContainer = GetFirstChildObject(Definition, {TEXT("Padding")});
        }

        const FString ChildType = ChildContainer.IsValid() ? GetFirstChildWidgetType(ChildContainer, {}) : FString();
        const TSharedPtr<FJsonObject> ChildObject = ChildContainer.IsValid() ? GetFirstChildObject(ChildContainer, {}) : nullptr;

        return SNew(SBorder)
            .Padding(Padding)
                [ChildObject.IsValid() ? BuildWidgetFromDefinition(ChildType, ChildObject, TabId) : SNew(STextBlock).Text(FText::FromString(TEXT("Empty border")))];
    }

    static TSharedRef<SWidget> BuildUniformGrid(const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
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

            Grid->AddSlot(Column, Row)[BuildSlotWidget(SlotObject, TabId)];
        }

        return Grid;
    }

    static TSharedRef<SWidget> BuildWidgetFromDefinition(const FString &WidgetType, const TSharedPtr<FJsonObject> &Definition, const FName &TabId)
    {
        if (WidgetType == TEXT("SVerticalBox"))
        {
            return BuildVerticalBox(Definition, TabId);
        }
        if (WidgetType == TEXT("SHorizontalBox"))
        {
            return BuildHorizontalBox(Definition, TabId);
        }
        if (WidgetType == TEXT("SSplitter"))
        {
            return BuildSplitter(Definition, TabId);
        }
        if (WidgetType == TEXT("SScrollBox"))
        {
            return BuildScrollBox(Definition, TabId);
        }
        if (WidgetType == TEXT("SBorder"))
        {
            return BuildBorder(Definition, TabId);
        }
        if (WidgetType == TEXT("STextBlock"))
        {
            FString TextValue;
            FString Format = TEXT("%Value%");
            bool bAutoWrapText = true;
            Definition->TryGetStringField(TEXT("Text"), TextValue);
            Definition->TryGetStringField(TEXT("Format"), Format);
            Definition->TryGetBoolField(TEXT("AutoWrapText"), bAutoWrapText);
            const FString StateKey = GetDefinitionStateKey(Definition, FString());

            TSharedPtr<STextBlock> TextWidget;
            SAssignNew(TextWidget, STextBlock)
                .Text(FText::FromString(TextValue))
                .AutoWrapText(bAutoWrapText);

            if (!StateKey.IsEmpty())
            {
                FTextBlockWidgetBinding Binding;
                Binding.StateKey = StateKey;
                Binding.Format = Format;
                Binding.Widget = TextWidget;
                ToolTextBlockWidgets.FindOrAdd(TabId).Add(Binding);
            }

            return TextWidget.ToSharedRef();
        }
        if (WidgetType == TEXT("SButton"))
        {
            const FString ButtonText = Definition->GetStringField(TEXT("Text"));
            const FString OnClick = Definition->GetStringField(TEXT("OnClick"));
            return SNew(SButton)
                .Text(FText::FromString(ButtonText))
                .OnClicked_Lambda([OnClick, TabId]()
                                  {
                    ExecutePython(OnClick, TabId);
                    return FReply::Handled(); });
        }
        if (WidgetType == TEXT("SEditableTextBox"))
        {
            FString InitialText;
            FString Aka;
            FString HintText;
            FString OnTextCommitted;
            Definition->TryGetStringField(TEXT("Text"), InitialText);
            Definition->TryGetStringField(TEXT("Aka"), Aka);
            Definition->TryGetStringField(TEXT("HintText"), HintText);
            Definition->TryGetStringField(TEXT("OnTextCommitted"), OnTextCommitted);
            const FString BindingKey = NormalizeStateLookupKey(Aka);
            const FString StateKey = GetDefinitionStateKey(Definition, Aka);
            SetToolStringBinding(TabId, BindingKey, InitialText);

            TSharedPtr<SEditableTextBox> EditableTextBox;
            SAssignNew(EditableTextBox, SEditableTextBox)
                .Text(FText::FromString(InitialText))
                .HintText(FText::FromString(HintText))
                .SelectAllTextWhenFocused(true)
                .OnTextCommitted_Lambda([BindingKey, OnTextCommitted, TabId](const FText &NewText, ETextCommit::Type CommitType)
                                        {
                const FString TextValue = NewText.ToString();
                const FString NormalizedBindingKey = NormalizeStateLookupKey(BindingKey);
                if (CommitType == ETextCommit::OnCleared)
                {
                    if (TSet<FString>* PendingClearedCommits = ToolPendingClearedEditableCommits.Find(TabId))
                    {
                        if (PendingClearedCommits->Remove(NormalizedBindingKey) > 0)
                        {
                            UE_LOG(LogTemp, Log, TEXT("PythonEditorUtility skipping duplicate OnCleared commit tab=%s binding=%s value=%s"),
                                *TabId.ToString(),
                                *BindingKey,
                                *TextValue);
                            return;
                        }
                    }
                }
                else if (CommitType == ETextCommit::OnEnter)
                {
                    ToolPendingClearedEditableCommits.FindOrAdd(TabId).Add(NormalizedBindingKey);
                }
                else if (TSet<FString>* PendingClearedCommits = ToolPendingClearedEditableCommits.Find(TabId))
                {
                    PendingClearedCommits->Remove(NormalizedBindingKey);
                }
                SetToolStringBinding(TabId, BindingKey, TextValue);
                SyncEditableTextWidgetBinding(TabId, BindingKey, TextValue);
                UE_LOG(LogTemp, Log, TEXT("PythonEditorUtility OnTextCommitted tab=%s binding=%s value=%s commit=%s refreshing=%s"),
                    *TabId.ToString(),
                    *BindingKey,
                    *TextValue,
                    *TextCommitTypeToString(CommitType),
                    TabsRefreshingBindings.Contains(TabId) ? TEXT("true") : TEXT("false"));
                if (TabsRefreshingBindings.Contains(TabId))
                {
                    return;
                }
                if (!OnTextCommitted.IsEmpty())
                {
                    UE_LOG(LogTemp, Log, TEXT("PythonEditorUtility ExecutePython OnTextCommitted tab=%s binding=%s command=%s"),
                        *TabId.ToString(),
                        *BindingKey,
                        *OnTextCommitted);
                    ExecutePython(ResolveCommandTemplate(OnTextCommitted, TabId, &TextValue, nullptr), TabId);
                } });

            FEditableTextWidgetBinding Binding;
            Binding.BindingKey = BindingKey;
            Binding.StateKey = StateKey;
            Binding.OnTextCommittedCmd = OnTextCommitted;
            Binding.Widget = EditableTextBox;
            ToolEditableTextWidgets.FindOrAdd(TabId).Add(Binding);
            return EditableTextBox.ToSharedRef();
        }
        if (WidgetType == TEXT("SCheckBox"))
        {
            bool bInitiallyChecked = false;
            FString Aka;
            FString Label;
            FString OnCheckStateChanged;
            Definition->TryGetBoolField(TEXT("IsChecked"), bInitiallyChecked);
            Definition->TryGetStringField(TEXT("Aka"), Aka);
            Definition->TryGetStringField(TEXT("Text"), Label);
            Definition->TryGetStringField(TEXT("OnCheckStateChanged"), OnCheckStateChanged);
            const FString BindingKey = NormalizeStateLookupKey(Aka);
            const FString StateKey = GetDefinitionStateKey(Definition, Aka);
            SetToolBoolBinding(TabId, BindingKey, bInitiallyChecked);

            TSharedPtr<SCheckBox> CheckBoxWidget;
            SAssignNew(CheckBoxWidget, SCheckBox)
                .IsChecked(bInitiallyChecked ? ECheckBoxState::Checked : ECheckBoxState::Unchecked)
                .OnCheckStateChanged_Lambda([BindingKey, OnCheckStateChanged, TabId](ECheckBoxState NewState)
                                            {
                const bool bChecked = NewState == ECheckBoxState::Checked;
                SetToolBoolBinding(TabId, BindingKey, bChecked);
                if (TabsRefreshingBindings.Contains(TabId))
                {
                    return;
                }
                if (!OnCheckStateChanged.IsEmpty())
                {
                    ExecutePython(ResolveCommandTemplate(OnCheckStateChanged, TabId, nullptr, &bChecked), TabId);
                } })
                    [SNew(STextBlock).Text(FText::FromString(Label))];

            FCheckBoxWidgetBinding Binding;
            Binding.BindingKey = BindingKey;
            Binding.StateKey = StateKey;
            Binding.Widget = CheckBoxWidget;
            ToolCheckBoxWidgets.FindOrAdd(TabId).Add(Binding);
            return CheckBoxWidget.ToSharedRef();
        }
        if (WidgetType == TEXT("SComboBox"))
        {
            FString Aka;
            FString SelectedValue;
            FString OnSelectionChanged;
            Definition->TryGetStringField(TEXT("Aka"), Aka);
            Definition->TryGetStringField(TEXT("Selected"), SelectedValue);
            Definition->TryGetStringField(TEXT("OnSelectionChanged"), OnSelectionChanged);
            const FString BindingKey = NormalizeStateLookupKey(Aka);
            const FString StateKey = GetDefinitionStateKey(Definition, Aka);

            const TArray<TSharedPtr<FJsonValue>> *OptionValues = nullptr;
            TSharedPtr<TArray<TSharedPtr<FString>>> Options = MakeShared<TArray<TSharedPtr<FString>>>();
            if (Definition->TryGetArrayField(TEXT("Options"), OptionValues) && OptionValues != nullptr)
            {
                for (const TSharedPtr<FJsonValue> &OptionValue : *OptionValues)
                {
                    const FString OptionText = OptionValue->AsString();
                    Options->Add(MakeShared<FString>(OptionText));
                    if (SelectedValue.IsEmpty())
                    {
                        SelectedValue = OptionText;
                    }
                }
            }

            if (SelectedValue.IsEmpty() && Options.IsValid() && Options->Num() > 0)
            {
                SelectedValue = *(*Options)[0];
            }

            TSharedRef<FString> CurrentValue = MakeShared<FString>(SelectedValue);
            SetToolStringBinding(TabId, BindingKey, *CurrentValue);

            TSharedPtr<FString> InitiallySelectedItem;
            for (const TSharedPtr<FString> &Option : *Options)
            {
                if (Option.IsValid() && *Option == *CurrentValue)
                {
                    InitiallySelectedItem = Option;
                    break;
                }
            }

            TSharedPtr<FStringComboBox> ComboBoxWidget;
            SAssignNew(ComboBoxWidget, FStringComboBox)
                .OptionsSource(Options.Get())
                .InitiallySelectedItem(InitiallySelectedItem)
                .OnGenerateWidget_Lambda([Options](TSharedPtr<FString> Item)
                                         { return SNew(STextBlock).Text(FText::FromString(Item.IsValid() ? *Item : FString())); })
                .OnSelectionChanged_Lambda([CurrentValue, BindingKey, OnSelectionChanged, TabId](TSharedPtr<FString> NewSelection, ESelectInfo::Type)
                                           {
                const FString SelectedText = NewSelection.IsValid() ? *NewSelection : FString();
                *CurrentValue = SelectedText;
                SetToolStringBinding(TabId, BindingKey, SelectedText);
                if (TabsRefreshingBindings.Contains(TabId))
                {
                    return;
                }
                if (!OnSelectionChanged.IsEmpty())
                {
                    ExecutePython(ResolveCommandTemplate(OnSelectionChanged, TabId, &SelectedText, nullptr), TabId);
                } })
                    [SNew(STextBlock).Text_Lambda([CurrentValue]()
                                                  { return FText::FromString(*CurrentValue); })];

            FComboBoxWidgetBinding Binding;
            Binding.BindingKey = BindingKey;
            Binding.StateKey = StateKey;
            Binding.Widget = ComboBoxWidget;
            Binding.Options = Options;
            Binding.CurrentValue = CurrentValue;
            ToolComboBoxWidgets.FindOrAdd(TabId).Add(Binding);
            return ComboBoxWidget.ToSharedRef();
        }
        if (WidgetType == TEXT("SMultiLineEditableTextBox"))
        {
            bool bReadOnly = false;
            FString InitialText;
            Definition->TryGetStringField(TEXT("Text"), InitialText);
            Definition->TryGetBoolField(TEXT("IsReadOnly"), bReadOnly);
            const FString StateKey = GetDefinitionStateKey(Definition, FString());

            TSharedPtr<SMultiLineEditableTextBox> OutputTextBox;
            SAssignNew(OutputTextBox, SMultiLineEditableTextBox)
                .IsReadOnly(bReadOnly)
                .AlwaysShowScrollbars(true)
                .Text(FText::FromString(InitialText.IsEmpty() ? LoadStatusText(TabId) : InitialText));

            FMultiLineTextWidgetBinding Binding;
            Binding.StateKey = StateKey;
            Binding.Widget = OutputTextBox;
            ToolMultiLineTextWidgets.FindOrAdd(TabId).Add(Binding);
            return OutputTextBox.ToSharedRef();
        }
        if (WidgetType == TEXT("SProgressBar"))
        {
            double PercentValue = 0.0;
            Definition->TryGetNumberField(TEXT("Percent"), PercentValue);
            const FString StateKey = GetDefinitionStateKey(Definition, TEXT("Percent"));

            TSharedPtr<SProgressBar> ProgressBarWidget;
            SAssignNew(ProgressBarWidget, SProgressBar)
                .Percent((float)PercentValue);

            FProgressBarWidgetBinding Binding;
            Binding.StateKey = StateKey;
            Binding.Widget = ProgressBarWidget;
            ToolProgressBarWidgets.FindOrAdd(TabId).Add(Binding);
            return ProgressBarWidget.ToSharedRef();
        }
        if (WidgetType == TEXT("SStateTable"))
        {
            return BuildStateTable(Definition, TabId);
        }
        if (WidgetType == TEXT("SUniformGridPanel"))
        {
            return BuildUniformGrid(Definition, TabId);
        }

        return SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("Unsupported widget type: %s"), *WidgetType)));
    }

    static TSharedRef<SWidget> BuildWidgetTreeFromJson(const FName &TabId)
    {
        ResetToolWidgetRegistry(TabId);

        const FDiscoveredToolDefinition *Tool = FindToolByTabId(TabId);
        if (Tool == nullptr)
        {
            return SNew(STextBlock).Text(FText::FromString(TEXT("Unknown PythonEditorUtility tool.")));
        }

        TSharedPtr<FJsonObject> RootObject;
        if (!LoadJsonObjectFromFile(Tool->JsonPath, RootObject))
        {
            return SNew(STextBlock).Text(FText::FromString(FString::Printf(TEXT("Could not load JSON: %s"), *Tool->JsonPath)));
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
                return BuildWidgetFromDefinition(Pair.Key, Pair.Value->AsObject(), TabId);
            }
        }

        return SNew(STextBlock).Text(FText::FromString(TEXT("No root widget found in UI definition.")));
    }

    static TArray<FDiscoveredToolDefinition> DiscoverToolDefinitions()
    {
        TArray<FDiscoveredToolDefinition> Result;
        const FString UiRoot = ResolveProjectPath(GetIntegrationSettings().UiRoot);
        if (!IFileManager::Get().DirectoryExists(*UiRoot))
        {
            return Result;
        }

        TArray<FString> JsonFiles;
        IFileManager::Get().FindFiles(JsonFiles, *FPaths::Combine(UiRoot, TEXT("*.json")), true, false);
        JsonFiles.Sort();

        for (const FString &JsonFileName : JsonFiles)
        {
            const FString JsonPath = FPaths::Combine(UiRoot, JsonFileName);
            TSharedPtr<FJsonObject> RootObject;
            if (!LoadJsonObjectFromFile(JsonPath, RootObject))
            {
                continue;
            }

            FDiscoveredToolDefinition Tool;
            Tool.ToolName = FPaths::GetBaseFilename(JsonFileName);
            Tool.JsonPath = JsonPath;
            Tool.TabLabel = Tool.ToolName;
            Tool.TabLabel.RemoveFromEnd(TEXT("Tool"));
            Tool.StatusFileName = MakeDefaultStatusFileName(Tool.ToolName);
            Tool.StateFileName = MakeDefaultStateFileName(Tool.ToolName);
            Tool.Tooltip = FString::Printf(TEXT("Open the %s tool."), *Tool.TabLabel);
            RootObject->TryGetStringField(TEXT("TabLabel"), Tool.TabLabel);
            RootObject->TryGetStringField(TEXT("StatusFile"), Tool.StatusFileName);
            RootObject->TryGetStringField(TEXT("StateFile"), Tool.StateFileName);
            RootObject->TryGetStringField(TEXT("Tooltip"), Tool.Tooltip);
            RootObject->TryGetStringField(TEXT("InitPyCmd"), Tool.InitPyCmd);
            Tool.TabId = MakeTabId(Tool.ToolName);
            Tool.MenuEntryName = FName(*FString::Printf(TEXT("OpenPythonEditorUtility%s"), *Tool.ToolName));
            Result.Add(Tool);
        }

        return Result;
    }

    static void RefreshDiscoveredTools()
    {
        DiscoveredTools = DiscoverToolDefinitions();
        ToolsByTabId.Empty();
        for (const FDiscoveredToolDefinition &Tool : DiscoveredTools)
        {
            ToolsByTabId.Add(Tool.TabId, Tool);
        }
    }
}

class FPythonEditorUtilityModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        PythonEditorUtility::RefreshDiscoveredTools();

        if (IPythonScriptPlugin *PythonPlugin = IPythonScriptPlugin::Get())
        {
            PythonPlugin->RegisterOnPythonInitialized(FSimpleDelegate::CreateStatic(&PythonEditorUtility::EnsurePythonSearchPath));
        }

        for (const PythonEditorUtility::FDiscoveredToolDefinition &Tool : PythonEditorUtility::DiscoveredTools)
        {
            FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
                                        Tool.TabId,
                                        FOnSpawnTab::CreateRaw(this, &FPythonEditorUtilityModule::SpawnDiscoveredToolTab, Tool.TabId))
                .SetDisplayName(FText::FromString(Tool.TabLabel))
                .SetTooltipText(FText::FromString(Tool.Tooltip))
                .SetMenuType(ETabSpawnerMenuType::Hidden);
        }

        UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FPythonEditorUtilityModule::RegisterMenus));
    }

    virtual void ShutdownModule() override
    {
        PythonEditorUtility::ToolStringBindings.Empty();
        PythonEditorUtility::ToolBoolBindings.Empty();
        PythonEditorUtility::ToolStateValues.Empty();
        PythonEditorUtility::ToolEditableTextWidgets.Empty();
        PythonEditorUtility::ToolCheckBoxWidgets.Empty();
        PythonEditorUtility::ToolComboBoxWidgets.Empty();
        PythonEditorUtility::ToolTextBlockWidgets.Empty();
        PythonEditorUtility::ToolMultiLineTextWidgets.Empty();
        PythonEditorUtility::ToolProgressBarWidgets.Empty();
        PythonEditorUtility::ToolStateTableWidgets.Empty();
        PythonEditorUtility::TabsRefreshingBindings.Empty();
        UToolMenus::UnRegisterStartupCallback(this);
        UToolMenus::UnregisterOwner(this);

        for (const PythonEditorUtility::FDiscoveredToolDefinition &Tool : PythonEditorUtility::DiscoveredTools)
        {
            FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(Tool.TabId);
        }
    }

private:
    void PopulateToolsSubMenu(UToolMenu *SubMenu)
    {
        if (SubMenu == nullptr)
        {
            return;
        }

        FToolMenuSection &SubMenuSection = SubMenu->FindOrAddSection(TEXT("PythonEditorUtilityTools"));
        for (const PythonEditorUtility::FDiscoveredToolDefinition &Tool : PythonEditorUtility::DiscoveredTools)
        {
            if (SubMenuSection.FindEntry(Tool.MenuEntryName) == nullptr)
            {
                SubMenuSection.AddMenuEntry(
                    Tool.MenuEntryName,
                    FText::FromString(Tool.TabLabel),
                    FText::FromString(Tool.Tooltip),
                    FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("Icons.Tool")),
                    FUIAction(FExecuteAction::CreateRaw(this, &FPythonEditorUtilityModule::OpenDiscoveredToolTab, Tool.TabId)));
            }
        }
    }

    void RegisterMenus()
    {
        if (UToolMenu *ToolsMenu = UToolMenus::Get()->ExtendMenu(TEXT("LevelEditor.MainMenu.Tools")))
        {
            FToolMenuSection &PythonSection = ToolsMenu->FindOrAddSection(TEXT("Python"));
            if (PythonSection.FindEntry(TEXT("PythonEditorUtilitySubMenu")) == nullptr)
            {
                PythonSection.AddSubMenu(
                    TEXT("PythonEditorUtilitySubMenu"),
                    FText::FromString(TEXT("Editor Utility Widget")),
                    FText::FromString(TEXT("Open PythonEditorUtility widgets discovered from the configured UI root.")),
                    FNewToolMenuDelegate::CreateRaw(this, &FPythonEditorUtilityModule::PopulateToolsSubMenu),
                    false,
                    FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("WorkspaceMenu.AdditionalUI")));
            }
        }

        UToolMenus::Get()->RefreshMenuWidget(TEXT("LevelEditor.MainMenu.Tools"));
    }

    void OpenDiscoveredToolTab(FName TabId)
    {
        FGlobalTabmanager::Get()->TryInvokeTab(TabId);
        PythonEditorUtility::RefreshToolOutput(TabId);
    }

    TSharedRef<SDockTab> SpawnDiscoveredToolTab(const FSpawnTabArgs &Args, FName TabId)
    {
        PythonEditorUtility::EnsurePythonSearchPath();
        if (const PythonEditorUtility::FDiscoveredToolDefinition *Tool = PythonEditorUtility::FindToolByTabId(TabId))
        {
            PythonEditorUtility::RunInitPython(*Tool);
        }

        const TSharedRef<SWidget> RootWidget = PythonEditorUtility::BuildWidgetTreeFromJson(TabId);
        PythonEditorUtility::RefreshToolOutput(TabId);

        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
                [RootWidget];
    }
};

IMPLEMENT_MODULE(FPythonEditorUtilityModule, PythonEditorUtility)
