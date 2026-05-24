import { useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { useI18n } from "@/lib/i18n";

interface MonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
  onVerify?: () => void;
  readOnly?: boolean;
}

export function CodeEditor({ value, onChange, onSave, onVerify, readOnly }: MonacoEditorProps) {
  const { t } = useI18n();
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // Save: Ctrl/Cmd+S
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => onSave?.());
    // Verify: Ctrl/Cmd+Enter
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => onVerify?.());

    // Indicator contract autocomplete
    monaco.languages.registerCompletionItemProvider("python", {
      provideCompletionItems: () => ({
        suggestions: [
          {
            label: "my_indicator_name",
            kind: monaco.languages.CompletionItemKind.Variable,
            insertText: 'my_indicator_name = "${1:My Name}"',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Display name of the indicator",
          },
          {
            label: "my_indicator_description",
            kind: monaco.languages.CompletionItemKind.Variable,
            insertText: 'my_indicator_description = "${1:Description}"',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Description of the indicator strategy",
          },
          {
            label: 'df["buy"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["buy"]',
            documentation: "Boolean Series: set True on entry bars",
          },
          {
            label: 'df["sell"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["sell"]',
            documentation: "Boolean Series: set True on exit bars",
          },
          {
            label: 'df["close"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["close"]',
          },
          {
            label: 'df["open"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["open"]',
          },
          {
            label: 'df["high"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["high"]',
          },
          {
            label: 'df["low"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["low"]',
          },
          {
            label: 'df["volume"]',
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: 'df["volume"]',
          },
          {
            label: "output",
            kind: monaco.languages.CompletionItemKind.Variable,
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
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Chart output dict with plots and signals",
          },
          {
            label: "# @param",
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: "# @param ${1:name} ${2:int} ${3:default} ${4:description}",
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Declare a tunable parameter",
          },
          {
            label: "# @strategy",
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: "# @strategy ${1:key} ${2:value}",
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Strategy config: stopLossPct, takeProfitPct, entryPct, etc.",
          },
          {
            label: "df = df.copy()",
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: "df = df.copy()",
            documentation: "Required: work on a copy of the DataFrame",
          },
          {
            label: "params.get()",
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: 'params.get("${1:param_name}", ${2:default})',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Read a tunable parameter with fallback",
          },
        ],
      }),
    });
  };

  return (
    <div className="flex flex-col h-full border rounded-lg overflow-hidden bg-[#1e1e2e]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#181825] border-b border-[#313244] shrink-0">
        <span className="text-xs text-[#a6adc8] font-mono">indicator.py</span>
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
