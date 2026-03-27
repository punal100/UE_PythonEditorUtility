# PEU JSON Widget Patterns

Canonical patterns for PythonEditorUtility JSON tool definitions.

## 1. Label + TextBox + Browse + Action Row

```json
{
  "AutoHeight": true,
  "Padding": [0, 0, 0, 6],
  "SHorizontalBox": {
    "Slots": [
      {
        "AutoWidth": true,
        "Padding": [0, 0, 8, 0],
        "STextBlock": { "Text": "Label" }
      },
      {
        "FillWidth": 1.0,
        "Padding": [0, 0, 6, 0],
        "SEditableTextBox": {
          "Aka": "FieldName",
          "StateKey": "field_name",
          "HintText": "Descriptive hint",
          "OnTextCommitted": "..."
        }
      },
      {
        "AutoWidth": true,
        "SButton": { "Text": "Browse", "OnClick": "PEU:BrowseFolder:FieldName" }
      },
      {
        "AutoWidth": true,
        "SButton": { "Text": "Open Folder", "OnClick": "..." }
      }
    ]
  }
}
```

- Use `PEU:BrowseFolder:{Aka}` for directories and `PEU:BrowseFile:{Aka}` for files.
- Browse updates the text binding and then fires `OnTextCommitted` to persist state.

## 2. Label + TextBox Row

```json
{
  "AutoHeight": true,
  "SHorizontalBox": {
    "Slots": [
      {
        "AutoWidth": true,
        "Padding": [0, 0, 8, 0],
        "STextBlock": { "Text": "Label" }
      },
      {
        "FillWidth": 1.0,
        "SEditableTextBox": { "Aka": "Field", "StateKey": "field", "Text": "" }
      }
    ]
  }
}
```

Use no textbox-slot padding when nothing follows the text box.

## 3. Button Toolbar Row

```json
{
  "AutoHeight": true,
  "SHorizontalBox": {
    "Slots": [
      {
        "AutoWidth": true,
        "Padding": [0, 0, 6, 6],
        "SButton": { "Text": "Action 1", "OnClick": "..." }
      },
      {
        "AutoWidth": true,
        "Padding": [0, 0, 6, 6],
        "SButton": { "Text": "Action 2", "OnClick": "..." }
      }
    ]
  }
}
```

`Padding [0,0,6,6]` gives right and bottom spacing between buttons.

## 4. Progress Section

```json
{
  "Value": 0.16,
  "SBorder": {
    "Padding": [8, 6, 8, 6],
    "Content": {
      "SVerticalBox": {
        "Slots": [
          {
            "AutoHeight": true,
            "STextBlock": { "Text": "Idle", "StateKey": "progress_text" }
          },
          {
            "AutoHeight": true,
            "SProgressBar": { "StateKey": "progress_percent", "Percent": 0.0 }
          }
        ]
      }
    }
  }
}
```

Use inside an `SSplitter` slot for live status and progress updates.

## Slot Padding

`Padding` on slot objects accepts `[uniform]`, `[horizontal, vertical]`, or `[left, top, right, bottom]` and applies to `SVerticalBox` and `SHorizontalBox` slots.
