#!/usr/bin/env python3
"""Build the committed research layer for the BFL YouTube archive.

Reads the yt-dlp outputs in ``media/`` (gitignored) and emits the two things
that ARE committed:

  - ``MANIFEST.md``       — per-video metadata + SHA-256 checksums (a
                            verifiable, tamper-evident record of what was
                            archived and from where).
  - ``transcripts/*.txt`` — the captions flattened to plain, searchable text.

The ``media/`` files (the actual .mp4, thumbnails, .info.json, .srt) stay
**local and uncommitted** — re-hosting a company's video is redistribution;
this committed layer is the metadata + transcript, kept for research on a
defunct, court-shuttered company (Butterfly Labs, shut by the FTC in 2014).

Run after downloading:  python research/bfl-youtube/build_manifest.py
Deps: stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent
MEDIA = DIR / "media"
TRANSCRIPTS = DIR / "transcripts"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def srt_to_text(srt_path: Path) -> str:
    """Flatten an .srt to plain text: drop indices/timestamps, de-dup the
    rolling repeats YouTube auto-captions produce."""
    raw = srt_path.read_text(encoding="utf-8", errors="replace")
    lines: list[str] = []
    for block in re.split(r"\n\s*\n", raw):
        keep = [l.strip() for l in block.splitlines()
                if l.strip() and not l.strip().isdigit() and "-->" not in l]
        if keep:
            lines.append(" ".join(keep))
    out: list[str] = []
    for l in lines:
        if not out or out[-1] != l:
            out.append(l)
    return "\n".join(out)


def main() -> None:
    TRANSCRIPTS.mkdir(exist_ok=True)
    rows = []
    for ij in sorted(MEDIA.glob("*.info.json")):
        d = json.loads(ij.read_text(encoding="utf-8", errors="replace"))
        stem = ij.name[: -len(".info.json")]
        mp4 = MEDIA / f"{stem}.mp4"
        srt = next((MEDIA / f"{stem}.{s}.srt" for s in ("en", "en-orig")
                    if (MEDIA / f"{stem}.{s}.srt").exists()), None)
        tname = None
        if srt:
            txt = srt_to_text(srt)
            tname = f"{d.get('upload_date', '')}_{d.get('id')}.txt"
            (TRANSCRIPTS / tname).write_text(
                f"# {d.get('title')}\n# {d.get('webpage_url')}\n"
                f"# uploaded {d.get('upload_date')}  |  duration {d.get('duration')}s\n\n"
                f"{txt}\n", encoding="utf-8")
        rows.append({
            "id": d.get("id"), "title": d.get("title"),
            "url": d.get("webpage_url"),
            "channel": d.get("channel") or d.get("uploader"),
            "channel_id": d.get("channel_id"),
            "upload_date": d.get("upload_date"), "duration": d.get("duration"),
            "views": d.get("view_count"),
            "mp4": mp4.name, "size": mp4.stat().st_size if mp4.exists() else None,
            "sha256": sha256(mp4) if mp4.exists() else None,
            "transcript": tname,
            "description": (d.get("description") or "").strip(),
        })
    rows.sort(key=lambda r: r["upload_date"] or "")

    def fdate(s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}" if s and len(s) == 8 else s

    out = ["# BFL YouTube archive — manifest\n",
           "Primary-source video from the **Butterfly Labs Inc** YouTube "
           "channel, archived for research on a defunct, FTC-shuttered company. "
           "The video files themselves are kept local (not committed — see "
           "`README.md`); this manifest + the `transcripts/` are the committed, "
           "verifiable record.\n",
           "| Date | Video | Dur | Views | Transcript |",
           "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {fdate(r['upload_date'])} | [{r['title']}]({r['url']}) "
                   f"| {r['duration']}s | {r['views']} "
                   f"| `transcripts/{r['transcript']}` |")
    out.append("\n## Per-video detail\n")
    for r in rows:
        mb = f"{r['size']/1e6:.1f} MB" if r["size"] else "—"
        out += [
            f"### {r['title']}",
            f"- **URL:** {r['url']}",
            f"- **Channel:** {r['channel']} (`{r['channel_id']}`)",
            f"- **Uploaded:** {fdate(r['upload_date'])}  ·  **Duration:** {r['duration']}s  ·  **Views (at archive):** {r['views']}",
            f"- **File (local, gitignored):** `media/{r['mp4']}` ({mb})",
            f"- **SHA-256:** `{r['sha256']}`",
            f"- **Transcript:** `transcripts/{r['transcript']}`",
            "- **Description:**",
            "  > " + (r["description"].replace("\n", "\n  > ") if r["description"] else "*(none)*"),
            "",
        ]
    (DIR / "MANIFEST.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"MANIFEST.md + {len(rows)} transcript(s) written.")
    for r in rows:
        print(f"  {r['id']}  {fdate(r['upload_date'])}  {r['sha256'][:16]}…  {r['title'][:50]}")


if __name__ == "__main__":
    main()
