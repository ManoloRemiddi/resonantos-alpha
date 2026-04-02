#!/usr/bin/env python3
"""Build and send a morning HTML digest from recent research markdown files."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from pathlib import Path


LOOKBACK_HOURS = 28
FROM_EMAIL = os.environ.get("DIGEST_FROM_EMAIL", "")
DEFAULT_TO_EMAIL = os.environ.get("DIGEST_TO_EMAIL", "")
PREVIEW_PATH = Path("/tmp/digest-preview.html")
REPO_ROOT = Path(__file__).resolve().parent.parent
SSOT_L4_DIR = REPO_ROOT / "ssot" / "L4"
CONTENT_IDEAS_DIR = Path.home() / ".openclaw" / "workspace" / "memory" / "content-ideas"
SOCIAL_DRAFTS_DIR = Path.home() / ".openclaw" / "workspace" / "memory" / "social-drafts"


@dataclass
class Category:
    key: str
    label: str
    emoji: str
    color: str


CATEGORIES = [
    Category("youtube_content", "YouTube & Content", "🎬", "#e74c3c"),
    Category("finance_pricing", "Finance & Pricing", "💰", "#27ae60"),
    Category("security_claw", "Security & Claw", "🔒", "#e67e22"),
    Category("x_trends_twitter", "X Trends & Twitter", "🐦", "#3498db"),
    Category("content_ideas", "Content Ideas", "💡", "#9b59b6"),
    Category("default", "General Research", "🔬", "#2c3e50"),
]
CATEGORY_BY_KEY = {cat.key: cat for cat in CATEGORIES}


@dataclass
class DigestItem:
    path: Path
    title: str
    category_key: str
    modified_at: datetime
    html_content: str


@dataclass
class SocialDrafts:
    path: Path
    x_post: str
    linkedin_post: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send morning intelligence digest email.")
    parser.add_argument("--dry-run", action="store_true", help="Write HTML preview to /tmp and do not send.")
    parser.add_argument("--to", default=DEFAULT_TO_EMAIL, help="Override recipient email.")
    return parser.parse_args()


def modified_after(path: Path, cutoff_utc: datetime) -> bool:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified >= cutoff_utc


def scan_recent_files(cutoff_utc: datetime) -> list[Path]:
    files: dict[Path, Path] = {}

    for pattern in ("L4-RESEARCH-*", "L4-YOUTUBE-*", "research-*"):
        for path in SSOT_L4_DIR.glob(pattern):
            if path.is_file() and modified_after(path, cutoff_utc):
                files[path.resolve()] = path

    if CONTENT_IDEAS_DIR.exists():
        for path in CONTENT_IDEAS_DIR.glob("*.md"):
            if path.is_file() and modified_after(path, cutoff_utc):
                files[path.resolve()] = path

    return sorted(files.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def extract_title(markdown_text: str, path: Path) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem


def infer_category(path: Path) -> str:
    lower_name = path.name.lower()
    lower_path = str(path).lower()

    if "content-ideas" in lower_path:
        return "content_ideas"
    if "x-trends" in lower_name or "x_trends" in lower_name or "twitter" in lower_name:
        return "x_trends_twitter"
    if "finance" in lower_name or "pricing" in lower_name:
        return "finance_pricing"
    if "youtube" in lower_name or "content" in lower_name:
        return "youtube_content"
    if "security" in lower_name or "claw" in lower_name:
        return "security_claw"
    return "default"


def apply_inline_markdown(text: str) -> str:
    text = escape(text)
    code_chunks: list[str] = []

    def stash_inline_code(match: re.Match[str]) -> str:
        code_chunks.append(
            f'<code style="font-family:SFMono-Regular,Menlo,Consolas,monospace;'
            f'background:#f5f7fb;border:1px solid #e2e8f0;border-radius:4px;'
            f'padding:1px 5px;font-size:13px;">{escape(match.group(1))}</code>'
        )
        return f"__INLINE_CODE_{len(code_chunks) - 1}__"

    text = re.sub(r"`([^`]+)`", stash_inline_code, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    for i, code_html in enumerate(code_chunks):
        text = text.replace(f"__INLINE_CODE_{i}__", code_html)

    return text


def markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    out: list[str] = []
    in_code = False
    code_lines: list[str] = []
    list_type: str | None = None
    in_table_block = False
    table_lines: list[str] = []

    def close_list() -> None:
        nonlocal list_type
        if list_type == "ul":
            out.append("</ul>")
        elif list_type == "ol":
            out.append("</ol>")
        list_type = None

    def close_table_block() -> None:
        nonlocal in_table_block, table_lines
        if in_table_block:
            table_text = "\n".join(table_lines)
            out.append(
                '<pre style="background:#f8fafc;border:1px solid #dfe6ee;border-radius:8px;'
                'padding:10px;font-size:12px;line-height:1.5;overflow:auto;">'
                f"{escape(table_text)}</pre>"
            )
            in_table_block = False
            table_lines = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("```"):
            close_list()
            close_table_block()
            if in_code:
                out.append(
                    '<pre style="background:#0f172a;color:#e2e8f0;border-radius:10px;'
                    'padding:12px 14px;overflow:auto;font-size:12px;line-height:1.5;">'
                    f"{escape('\n'.join(code_lines))}</pre>"
                )
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            close_list()
            close_table_block()
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            close_list()
            in_table_block = True
            table_lines.append(stripped)
            continue
        if in_table_block:
            close_table_block()

        if stripped in ("---", "***", "___"):
            close_list()
            out.append('<hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">')
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            close_list()
            level = min(len(heading.group(1)), 4)
            content = apply_inline_markdown(heading.group(2).strip())
            if level == 1:
                style = "margin:6px 0 10px;font-size:24px;color:#111827;line-height:1.3;"
            elif level == 2:
                style = "margin:14px 0 8px;font-size:20px;color:#111827;line-height:1.35;"
            elif level == 3:
                style = "margin:12px 0 6px;font-size:17px;color:#1f2937;line-height:1.4;"
            else:
                style = "margin:10px 0 6px;font-size:15px;color:#374151;line-height:1.4;"
            out.append(f'<h{level} style="{style}">{content}</h{level}>')
            continue

        unordered = re.match(r"^[-*+]\s+(.*)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)

        if unordered:
            if list_type != "ul":
                close_list()
                out.append(
                    '<ul style="margin:8px 0 10px;padding-left:22px;color:#1f2937;line-height:1.6;">'
                )
                list_type = "ul"
            out.append(f"<li>{apply_inline_markdown(unordered.group(1))}</li>")
            continue

        if ordered:
            if list_type != "ol":
                close_list()
                out.append(
                    '<ol style="margin:8px 0 10px;padding-left:22px;color:#1f2937;line-height:1.6;">'
                )
                list_type = "ol"
            out.append(f"<li>{apply_inline_markdown(ordered.group(1))}</li>")
            continue

        close_list()
        if stripped.startswith(">"):
            quote = apply_inline_markdown(stripped.lstrip(">").strip())
            out.append(
                '<blockquote style="margin:10px 0;padding:8px 12px;border-left:4px solid #cbd5e1;'
                f'background:#f8fafc;color:#334155;">{quote}</blockquote>'
            )
            continue

        out.append(
            '<p style="margin:8px 0;color:#1f2937;font-size:14px;line-height:1.65;">'
            f"{apply_inline_markdown(stripped)}</p>"
        )

    if in_code:
        out.append(
            '<pre style="background:#0f172a;color:#e2e8f0;border-radius:10px;'
            'padding:12px 14px;overflow:auto;font-size:12px;line-height:1.5;">'
            f"{escape('\n'.join(code_lines))}</pre>"
        )
    close_list()
    close_table_block()
    return "\n".join(out)


def render_display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_subject(now: datetime) -> str:
    return f"🦾 Intelligence Digest — {now.strftime('%b')} {now.day}, {now.year}"


def build_digest_items(files: list[Path]) -> list[DigestItem]:
    items: list[DigestItem] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title = extract_title(text, path)
        category_key = infer_category(path)
        modified_at = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        items.append(
            DigestItem(
                path=path,
                title=title,
                category_key=category_key,
                modified_at=modified_at,
                html_content=markdown_to_html(text),
            )
        )
    return items


def extract_markdown_section(markdown_text: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    )
    match = pattern.search(markdown_text)
    if not match:
        return ""
    return match.group(1).strip()


def load_social_drafts(target_date: date) -> SocialDrafts | None:
    drafts_path = SOCIAL_DRAFTS_DIR / f"{target_date.isoformat()}.md"
    if not drafts_path.exists():
        return None

    try:
        text = drafts_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    x_post = extract_markdown_section(text, "X Post")
    linkedin_post = extract_markdown_section(text, "LinkedIn Post")
    if not x_post and not linkedin_post:
        return None

    return SocialDrafts(path=drafts_path, x_post=x_post, linkedin_post=linkedin_post)


def render_social_card(platform_icon: str, platform_name: str, accent_color: str, text: str) -> str:
    return (
        '<div style="background:#ffffff;border:1px solid #e6ebf2;border-left:6px solid '
        f"{accent_color};border-radius:12px;box-shadow:0 3px 8px rgba(15,23,42,0.06);"
        'margin:14px 0;padding:16px 16px 14px;">'
        f'<div style="font-size:16px;font-weight:700;color:{accent_color};margin-bottom:10px;">'
        f"{platform_icon} {escape(platform_name)}"
        "</div>"
        '<pre style="margin:0;white-space:pre-wrap;word-break:break-word;'
        'background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;'
        'font-size:14px;line-height:1.6;color:#0f172a;font-family:SFMono-Regular,Menlo,Consolas,monospace;">'
        f"{escape(text)}"
        "</pre>"
        "</div>"
    )


def build_social_drafts_section(social_drafts: SocialDrafts | None) -> str:
    if social_drafts is None:
        return ""

    cards: list[str] = []
    if social_drafts.x_post:
        cards.append(render_social_card("🐦", "X Post", "#1DA1F2", social_drafts.x_post))
    if social_drafts.linkedin_post:
        cards.append(render_social_card("💼", "LinkedIn Post", "#0077B5", social_drafts.linkedin_post))

    if not cards:
        return ""

    return (
        '<section style="margin:24px 0 30px;">'
        '<h2 style="margin:0 0 12px;font-size:22px;color:#0f172a;">📣 Ready to Post</h2>'
        f'<div style="font-size:12px;color:#64748b;margin-bottom:12px;">{escape(str(social_drafts.path))}</div>'
        f"{''.join(cards)}"
        "</section>"
    )


def build_email_html(
    items: list[DigestItem], generated_at: datetime, social_drafts: SocialDrafts | None = None
) -> str:
    grouped: dict[str, list[DigestItem]] = defaultdict(list)
    for item in items:
        grouped[item.category_key].append(item)

    sections: list[str] = []
    for category in CATEGORIES:
        category_items = grouped.get(category.key, [])
        if not category_items:
            continue
        cards: list[str] = []
        for item in category_items:
            cards.append(
                '<div style="background:#ffffff;border:1px solid #e6ebf2;border-radius:12px;'
                'box-shadow:0 3px 8px rgba(15,23,42,0.06);margin:14px 0;padding:18px;">'
                f'<div style="font-size:20px;font-weight:700;color:#0f172a;margin-bottom:6px;">{escape(item.title)}</div>'
                f'<div style="font-size:12px;color:#64748b;margin-bottom:14px;">{escape(render_display_path(item.path))} '
                f'| Updated {item.modified_at.strftime("%Y-%m-%d %H:%M %Z")}</div>'
                f"{item.html_content}"
                "</div>"
            )
        sections.append(
            '<section style="margin:24px 0 30px;">'
            f'<h2 style="margin:0 0 12px;font-size:22px;color:{category.color};">'
            f"{category.emoji} {escape(category.label)} ({len(category_items)})"
            "</h2>"
            f"{''.join(cards)}"
            "</section>"
        )

    if not sections:
        sections.append(
            '<section style="margin:24px 0;">'
            '<div style="background:#ffffff;border:1px solid #e6ebf2;border-radius:12px;padding:22px;">'
            '<p style="margin:0;color:#374151;font-size:15px;line-height:1.6;">'
            "No qualifying files were modified in the last 28 hours."
            "</p></div></section>"
        )

    social_section = build_social_drafts_section(social_drafts)

    return (
        "<!doctype html>"
        '<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f3f6fb;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        '<div style="max-width:980px;margin:0 auto;padding:20px 16px 40px;">'
        '<div style="background:linear-gradient(120deg,#0b1220,#172a46,#1f3d68);color:#f8fafc;'
        'padding:24px;border-radius:16px;box-shadow:0 12px 26px rgba(2,8,23,0.24);">'
        '<div style="font-size:30px;font-weight:800;line-height:1.25;">🦾 Morning Intelligence Digest</div>'
        f'<div style="margin-top:8px;font-size:14px;opacity:0.95;">Generated {generated_at.strftime("%Y-%m-%d %H:%M %Z")} '
        f'| {len(items)} report(s)</div>'
        "</div>"
        f"{''.join(sections)}"
        f"{social_section}"
        '<div style="margin-top:32px;color:#94a3b8;font-size:12px;text-align:center;">'
        "ResonantOS research digest automation"
        "</div></div></body></html>"
    )


def build_mime_message(recipient: str, subject: str, html_body: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(
        "Your email client does not support HTML. Please open this message in an HTML-capable client."
    )
    message.add_alternative(html_body, subtype="html")
    return message


def encode_message_raw(message: EmailMessage) -> str:
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return raw.rstrip("=")


def send_via_gws(raw_b64url: str) -> None:
    cmd = [
        "gws",
        "gmail",
        "users",
        "messages",
        "send",
        "--params",
        json.dumps({"userId": "me"}),
        "--json",
        json.dumps({"raw": raw_b64url}),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to send message via gws.\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )
    output = result.stdout.strip() or "Message sent."
    print(output)


def main() -> int:
    args = parse_args()
    now = datetime.now().astimezone()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    recent_files = scan_recent_files(cutoff)
    digest_items = build_digest_items(recent_files)
    social_drafts = load_social_drafts(now.date())
    subject = build_subject(now)
    html_body = build_email_html(digest_items, now, social_drafts=social_drafts)
    message = build_mime_message(args.to, subject, html_body)
    raw_b64url = encode_message_raw(message)

    if args.dry_run:
        PREVIEW_PATH.write_text(html_body, encoding="utf-8")
        print(f"Dry run complete: {PREVIEW_PATH}")
        print(f"Subject: {subject}")
        print(f"To: {args.to}")
        print(f"Files included: {len(digest_items)}")
        return 0

    send_via_gws(raw_b64url)
    print(f"Sent digest to {args.to}")
    print(f"Files included: {len(digest_items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
