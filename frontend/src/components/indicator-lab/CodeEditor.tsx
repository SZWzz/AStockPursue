import { useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import type Monaco from "monaco-editor";
import { useI18n } from "@/lib/i18n";

interface MonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
  onVerify?: () => void;
  readOnly?: boolean;
  filename?: string;
  mode?: "indicator" | "strategy";
}

function getIndicatorCompletions(monaco: typeof Monaco) {
  const kind = monaco.languages.CompletionItemKind;
  const rules = monaco.languages.CompletionItemInsertTextRule;
  return [
    {
      label: "my_indicator_name",
      kind: kind.Variable,
      insertText: 'my_indicator_name = "${1:My Name}"',
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Display name of the indicator",
    },
    {
      label: "my_indicator_description",
      kind: kind.Variable,
      insertText: 'my_indicator_description = "${1:Description}"',
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Description of the indicator strategy",
    },
    {
      label: 'df["buy"]',
      kind: kind.Property,
      insertText: 'df["buy"]',
      documentation: "Boolean Series: set True on entry bars",
    },
    {
      label: 'df["sell"]',
      kind: kind.Property,
      insertText: 'df["sell"]',
      documentation: "Boolean Series: set True on exit bars",
    },
    {
      label: 'df["close"]',
      kind: kind.Property,
      insertText: 'df["close"]',
      documentation: "Close price column",
    },
    {
      label: 'df["open"]',
      kind: kind.Property,
      insertText: 'df["open"]',
      documentation: "Open price column",
    },
    {
      label: 'df["high"]',
      kind: kind.Property,
      insertText: 'df["high"]',
      documentation: "High price column",
    },
    {
      label: 'df["low"]',
      kind: kind.Property,
      insertText: 'df["low"]',
      documentation: "Low price column",
    },
    {
      label: 'df["volume"]',
      kind: kind.Property,
      insertText: 'df["volume"]',
      documentation: "Volume column",
    },
    {
      label: "output",
      kind: kind.Variable,
      insertText: [
        'output = {',
        '    "name": my_indicator_name,',
        '    "plots": [',
        '        {"name": "${1:Line}", "data": ${2:data}.tolist(), "color": "${3:#000000}", "overlay": ${4:True}}',
        "    ],",
        '    "signals": [',
        '        {"type": "${5:buy}", "text": "${6:Buy}", "data": ${7:marks}, "color": "${8:#4CAF50}"}',
        "    ],",
        "}",
      ].join("\n"),
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Chart output dict with plots and signals",
    },
    {
      label: "# @param",
      kind: kind.Snippet,
      insertText: "# @param ${1:name} ${2:int} ${3:default} ${4:description}",
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Declare a tunable parameter",
    },
    {
      label: "# @strategy",
      kind: kind.Snippet,
      insertText: "# @strategy ${1:key} ${2:value}",
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Strategy config: stopLossPct, takeProfitPct, entryPct, etc.",
    },
    {
      label: "df = df.copy()",
      kind: kind.Snippet,
      insertText: "df = df.copy()",
      documentation: "Required: work on a copy of the DataFrame",
    },
    {
      label: "params.get()",
      kind: kind.Snippet,
      insertText: 'params.get("${1:param_name}", ${2:default})',
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Read a tunable parameter with fallback",
    },
  ];
}

function getStrategyCompletions(monaco: typeof Monaco) {
  const kind = monaco.languages.CompletionItemKind;
  const rules = monaco.languages.CompletionItemInsertTextRule;
  return [
    {
      label: "class SignalEngine",
      kind: kind.Snippet,
      insertText: [
        "class SignalEngine:",
        '    """${1:Strategy description}."""',
        "",
        "    def __init__(self):",
        "        ${2:pass}",
        "",
        "    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:",
        "        signal_map: Dict[str, pd.Series] = {}",
        "        ${3:pass}",
        "        return signal_map",
      ].join("\n"),
      insertTextRules: rules.InsertAsSnippet,
      documentation: "SignalEngine class boilerplate",
    },
    {
      label: "generate()",
      kind: kind.Method,
      insertText: [
        "def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:",
        "    signal_map: Dict[str, pd.Series] = {}",
        "    ${1:pass}",
        "    return signal_map",
      ].join("\n"),
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Required generate method — iterate data_map, return signal_map",
    },
    {
      label: "data_map",
      kind: kind.Variable,
      insertText: "data_map",
      documentation: "dict[str, pd.DataFrame] — symbol → OHLCV DataFrame",
    },
    {
      label: "signal_map",
      kind: kind.Variable,
      insertText: "signal_map",
      documentation: "dict[str, pd.Series] — symbol → signal Series (values in [-1, 1])",
    },
    {
      label: 'df["close"]',
      kind: kind.Property,
      insertText: 'df["close"]',
      documentation: "Close price column",
    },
    {
      label: 'df["open"]',
      kind: kind.Property,
      insertText: 'df["open"]',
      documentation: "Open price column",
    },
    {
      label: 'df["high"]',
      kind: kind.Property,
      insertText: 'df["high"]',
      documentation: "High price column",
    },
    {
      label: 'df["low"]',
      kind: kind.Property,
      insertText: 'df["low"]',
      documentation: "Low price column",
    },
    {
      label: 'df["volume"]',
      kind: kind.Property,
      insertText: 'df["volume"]',
      documentation: "Volume column",
    },
    {
      label: "pd.DataFrame",
      kind: kind.Class,
      insertText: "pd.DataFrame",
      documentation: "Pandas DataFrame",
    },
    {
      label: "pd.Series",
      kind: kind.Class,
      insertText: "pd.Series",
      documentation: "Pandas Series",
    },
    {
      label: "import pandas as pd",
      kind: kind.Snippet,
      insertText: "import pandas as pd",
      documentation: "Pandas import",
    },
    {
      label: "import numpy as np",
      kind: kind.Snippet,
      insertText: "import numpy as np",
      documentation: "NumPy import",
    },
    {
      label: "from typing import Dict",
      kind: kind.Snippet,
      insertText: "from typing import Dict",
      documentation: "Type hint import",
    },
    {
      label: "for code, df in data_map.items()",
      kind: kind.Snippet,
      insertText: "for code, df in data_map.items():\n    ${1:pass}",
      insertTextRules: rules.InsertAsSnippet,
      documentation: "Iterate over symbols in data_map",
    },
  ];
}

export function CodeEditor({ value, onChange, onSave, onVerify, readOnly, filename, mode }: MonacoEditorProps) {
  const { t } = useI18n();
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // Save: Ctrl/Cmd+S
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => onSave?.());
    // Verify: Ctrl/Cmd+Enter
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => onVerify?.());

    // Register completion provider
    monaco.languages.registerCompletionItemProvider("python", {
      provideCompletionItems: () => ({
        suggestions: mode === "strategy" ? getStrategyCompletions(monaco) : getIndicatorCompletions(monaco),
      }),
    });
  };

  return (
    <div className="flex flex-col h-full border rounded-lg overflow-hidden bg-[#1e1e2e]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#181825] border-b border-[#313244] shrink-0">
        <span className="text-xs text-[#a6adc8] font-mono">{filename || "indicator.py"}</span>
        <div className="flex items-center gap-1.5">
          {onVerify && (
            <button
              onClick={onVerify}
              className="px-2 py-0.5 text-xs rounded bg-[#313244] text-[#a6e3a1] hover:bg-[#45475a] transition-colors"
              title={`${t.indicatorLabVerify} (Ctrl+Enter)`}
            >
              {t.indicatorLabVerify}
            </button>
          )}
          {onSave && (
            <button
              onClick={onSave}
              className="px-2 py-0.5 text-xs rounded bg-[#313244] text-[#89b4fa] hover:bg-[#45475a] transition-colors"
              title={`${t.indicatorLabSave} (Ctrl+S)`}
            >
              {t.indicatorLabSave}
            </button>
          )}
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          defaultLanguage="python"
          value={value}
          onChange={(v) => onChange(v || "")}
          onMount={handleMount}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            readOnly,
            tabSize: 4,
            wordWrap: "on",
            padding: { top: 8 },
            suggest: { showKeywords: true, showSnippets: true },
          }}
          loading={
            <div className="flex items-center justify-center h-full bg-[#1e1e2e] text-[#a6adc8] text-sm">
              {t.indicatorLabLoadingEditor}
            </div>
          }
        />
      </div>
    </div>
  );
}
