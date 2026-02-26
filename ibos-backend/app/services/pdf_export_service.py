from __future__ import annotations

from datetime import datetime, timezone


def _escape_pdf_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("(", "\\(")
    escaped = escaped.replace(")", "\\)")
    return escaped


def build_text_pdf(
    *,
    title: str,
    lines: list[str],
    generated_at: datetime | None = None,
    max_lines: int = 48,
) -> bytes:
    timestamp = generated_at or datetime.now(timezone.utc)
    content_lines = [title, f"Generated: {timestamp.isoformat()}", ""]
    normalized_lines = [line.strip() for line in lines if line and line.strip()]

    if len(normalized_lines) > max_lines:
        normalized_lines = normalized_lines[: max_lines - 1] + ["... (truncated)"]
    content_lines.extend(normalized_lines)

    stream_commands = ["BT", "/F1 11 Tf", "50 770 Td"]
    first = True
    for line in content_lines:
        if first:
            first = False
        else:
            stream_commands.append("0 -14 Td")
        stream_commands.append(f"({_escape_pdf_text(line)}) Tj")
    stream_commands.append("ET")

    stream = "\n".join(stream_commands).encode("utf-8")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]

    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode("ascii")
        pdf += obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode("ascii")
    return pdf
