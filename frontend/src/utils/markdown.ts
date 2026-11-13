export interface InlineSpan {
  text: string;
  bold?: boolean;
  code?: boolean;
  link?: boolean;
}

export type MarkdownBlock =
  | { type: "heading"; level: 1 | 2 | 3 | 4; spans: InlineSpan[] }
  | { type: "hr" }
  | { type: "code"; lang: string; text: string }
  | { type: "quote"; spans: InlineSpan[] }
  | { type: "list"; ordered: boolean; items: { marker: string; spans: InlineSpan[] }[] }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "paragraph"; spans: InlineSpan[] };

// 行内解析：支持 **加粗**、`行内代码`、[文本](链接)
export function parseInline(input: string): InlineSpan[] {
  const spans: InlineSpan[] = [];
  const pattern = /(\*\*([^*\n]+)\*\*|`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s]+)\))/g;
  let lastIndex = 0;

  for (const match of input.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      spans.push({ text: input.slice(lastIndex, start) });
    }
    if (match[2] !== undefined) {
      spans.push({ text: match[2], bold: true });
    } else if (match[3] !== undefined) {
      spans.push({ text: match[3], code: true });
    } else if (match[4] !== undefined) {
      spans.push({ text: match[4], link: true });
    }
    lastIndex = start + match[0].length;
  }

  if (lastIndex < input.length) {
    spans.push({ text: input.slice(lastIndex) });
  }
  return spans.length ? spans : [{ text: input }];
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableSeparator(line: string): boolean {
  const trimmed = line.trim();
  return /^\|?(\s*:?-{3,}:?\s*\|)+\s*$/.test(`${trimmed.endsWith("|") ? trimmed : `${trimmed}|`}`);
}

/**
 * 轻量级 Markdown 解析器（支持流式未闭合代码块），直接输出给 Vue 组件渲染，同时兼容 H5 与微信小程序
 */
export function parseMarkdown(source: string): MarkdownBlock[] {
  if (!source) return [];
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    // 围栏代码块（流式输出尚未收到闭合 ``` 时也作为代码块渲染，避免闪烁）
    const fenceMatch = trimmed.match(/^```([\w-]*)$/);
    if (fenceMatch) {
      const lang = fenceMatch[1] || "";
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length && lines[i].trim().startsWith("```")) {
        i += 1;
      }
      // 模型常把文书模板包在 ```markdown 围栏里，直接展开为排版块以便用户阅读
      if (lang.toLowerCase() === "markdown" || lang.toLowerCase() === "md") {
        blocks.push({ type: "hr" });
        blocks.push(...parseMarkdown(codeLines.join("\n")));
        blocks.push({ type: "hr" });
      } else {
        blocks.push({ type: "code", lang, text: codeLines.join("\n") });
      }
      continue;
    }

    // 分割线
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: "hr" });
      i += 1;
      continue;
    }

    // 标题 # ~ ####
    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length as 1 | 2 | 3 | 4,
        spans: parseInline(headingMatch[2]),
      });
      i += 1;
      continue;
    }

    // 简单 Markdown 表格
    if (
      trimmed.includes("|") &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1])
    ) {
      const headers = splitTableRow(trimmed);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().includes("|")) {
        rows.push(splitTableRow(lines[i]));
        i += 1;
      }
      blocks.push({ type: "table", headers, rows });
      continue;
    }

    // 引用块
    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push({ type: "quote", spans: parseInline(quoteLines.join("\n")) });
      continue;
    }

    // 有序/无序列表
    const ulMatch = trimmed.match(/^[-*+]\s+(.+)$/);
    const olMatch = trimmed.match(/^(\d+)[.)]\s+(.+)$/);
    if (ulMatch || olMatch) {
      const ordered = Boolean(olMatch);
      const items: { marker: string; spans: InlineSpan[] }[] = [];
      while (i < lines.length) {
        const current = lines[i].trim();
        const u = !ordered ? current.match(/^[-*+]\s+(.+)$/) : null;
        const o = ordered ? current.match(/^(\d+)[.)]\s+(.+)$/) : null;
        if (u) {
          items.push({ marker: "•", spans: parseInline(u[1]) });
          i += 1;
        } else if (o) {
          items.push({ marker: `${o[1]}.`, spans: parseInline(o[2]) });
          i += 1;
        } else {
          break;
        }
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    // 普通段落：合并相邻非空普通文本行
    const paraLines: string[] = [];
    while (i < lines.length) {
      const cur = lines[i];
      const curTrim = cur.trim();
      if (
        !curTrim ||
        curTrim.startsWith("```") ||
        /^#{1,4}\s+/.test(curTrim) ||
        /^(-{3,}|\*{3,}|_{3,})$/.test(curTrim) ||
        curTrim.startsWith(">") ||
        /^[-*+]\s+/.test(curTrim) ||
        /^\d+[.)]\s+/.test(curTrim)
      ) {
        break;
      }
      paraLines.push(cur);
      i += 1;
    }
    blocks.push({ type: "paragraph", spans: parseInline(paraLines.join("\n")) });
  }

  return blocks;
}
