export function attachScannerListener(onScan: (value: string) => void) {
  let buffer = "";
  let timer: number | undefined;

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      const value = buffer.trim();
      buffer = "";
      if (timer) {
        window.clearTimeout(timer);
      }
      if (value) {
        onScan(value);
      }
      return;
    }
    if (event.key.length === 1) {
      buffer += event.key;
      if (timer) {
        window.clearTimeout(timer);
      }
      timer = window.setTimeout(() => {
        buffer = "";
      }, 500);
    }
  }

  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}

export function printReceiptText(content: string) {
  const printable = content.trim();
  if (!printable) {
    return;
  }
  const printWindow = window.open("", "_blank", "width=360,height=640");
  if (!printWindow) {
    return;
  }
  printWindow.document.write(`<pre style="font-family: monospace; padding: 12px;">${printable}</pre>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  printWindow.close();
}
