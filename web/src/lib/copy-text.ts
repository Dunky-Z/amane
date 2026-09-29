/**
 * 把文本写入系统剪贴板.
 *
 * 优先 Clipboard API; 在非安全上下文 (局域网 `http://` 等) 下该 API 会拒绝,
 * 再回退到选中隐藏 textarea + `document.execCommand("copy")`.
 */
export async function copyText(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText != null) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 落到 execCommand 回退.
    }
  }
  return copyTextViaExecCommand(text);
}

function copyTextViaExecCommand(text: string): boolean {
  if (typeof document === "undefined") {
    return false;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.left = "-9999px";
  area.style.top = "0";
  document.body.appendChild(area);
  area.focus();
  area.select();
  area.setSelectionRange(0, area.value.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}
