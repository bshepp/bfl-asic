# BFL YouTube research archive

Primary-source video from the **Butterfly Labs Inc** YouTube channel
(`UCqQQxENTiJKoiEjeuE1UwDw`), preserved for research alongside this project's
work on the BFL Jalapeño SHA-256 ASIC and the [production census](../../docs/production-census.md).

Butterfly Labs was **shut down by the U.S. FTC in 2014** (settled 2016) for
taking ~$50M in pre-orders and largely failing to deliver — the FTC found it
was **mining on customers' machines before shipping them**. These three 2013
"production" clips are contemporaneous public statements from that period, which
makes them a useful primary source: e.g. the **Fall-2013 production video shows
a monitoring dashboard of dozens of units (`BFL19`–`BFL27`+) running hot** while
20,000 customers had received nothing — a visual footnote to the FTC's case.

## What's here

| Path | Committed? | What |
|---|---|---|
| `media/` | **no** (gitignored) | the video files, thumbnails, `.info.json`, `.srt` |
| `MANIFEST.md` | yes | per-video metadata + **SHA-256 checksums** (verifiable record) |
| `transcripts/` | yes | captions flattened to plain, searchable text |
| `build_manifest.py` | yes | regenerates the two above from `media/` |

**Why the video files are not committed:** re-hosting a copyrighted video
publicly is redistribution, which is a different thing from a local research
archive. Keeping a personal/research copy of primary-source material from a
defunct company is defensible; **re-publishing it is not**, so the `.mp4`s stay
local (`.gitignore` blocks `research/bfl-youtube/media/`). The committed layer is
just factual metadata and the transcript of public statements — the actual
research payload.

## How it was captured

```bash
# JS runtime for YouTube's challenge solver:
#   deno (https://deno.land) + yt-dlp's ejs remote component
yt-dlp --cookies <cookies.txt> --remote-components ejs:github \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --write-info-json --write-thumbnail \
  --write-subs --write-auto-subs --sub-langs "en.*" --convert-subs srt \
  -o "media/%(upload_date)s - %(title)s [%(id)s].%(ext)s" <urls>

python research/bfl-youtube/build_manifest.py   # -> MANIFEST.md + transcripts/
```

A YouTube login cookie (`cookies.txt`) was needed only to pass the bot-gate; it
held a live session token, so it was kept out of the repo and **deleted
immediately after** the download.

## Notable stills (single frames, kept as research figures)

- **Farm dashboard** from the Fall-2013 video — `BFL19`–`BFL27`+ running at 76–83 °C: [`../../docs/screenshot-34sec-bfl-labs-bitcoin-mining-harware-production-video-fall-2013-youtube.png`](../../docs/screenshot-34sec-bfl-labs-bitcoin-mining-harware-production-video-fall-2013-youtube.png)
- **BFL forum "Shipping Notes"** — a rep replying to customers "asking odd things about our shipping practices" (2013): [`../../docs/images/screenshot-bfl-forum-shipping-notes-production-video-2013.png`](../../docs/images/screenshot-bfl-forum-shipping-notes-production-video-2013.png)

## Related

- Production census (how many units BFL actually built): [`../../docs/production-census.md`](../../docs/production-census.md)
