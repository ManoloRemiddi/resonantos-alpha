#!/usr/bin/env python3
"""YouTube Weekly Analytics Report. Generates markdown with insights."""
import json, os, sys, re
import urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHANNEL_ID = "UC9HwoV7VQpDRDXOzviV2DIQ"
API_KEY = ""
WORKSPACE = Path(os.environ.get("WORKSPACE", os.path.expanduser("~/.openclaw/workspace")))
REPORT_DIR = WORKSPACE / "memory" / "youtube-reports"

def load_api_key():
    global API_KEY
    API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
    if not API_KEY:
        ef = Path(os.path.expanduser("~/resonantos-alpha/.env.local"))
        if ef.exists():
            for line in ef.read_text().splitlines():
                if line.strip().startswith("YOUTUBE_API_KEY="):
                    API_KEY = line.strip().split("=", 1)[1]
                    break
    if not API_KEY:
        print("YOUTUBE_API_KEY not set", file=sys.stderr); sys.exit(1)

def api(endpoint, params):
    params["key"] = API_KEY
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{qs}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())

def dur_fmt(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m: return d
    h, mi, s = int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0)
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"

def dur_sec(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m: return 0
    return int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)

def get_channel():
    return api("channels", {"part": "statistics,snippet", "id": CHANNEL_ID})["items"][0]

def get_videos(n=50):
    data = api("search", {"part": "id", "channelId": CHANNEL_ID, "type": "video", "order": "date", "maxResults": str(n)})
    ids = [i["id"]["videoId"] for i in data.get("items", [])]
    if not ids: return []
    vdata = api("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)})
    return vdata.get("items", [])

def load_prev():
    f = REPORT_DIR / "latest-snapshot.json"
    return json.loads(f.read_text()) if f.exists() else None

def save_snap(ch, vids):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    snap = {"timestamp": datetime.now(timezone.utc).isoformat(),
            "subscribers": int(ch["statistics"]["subscriberCount"]),
            "totalViews": int(ch["statistics"]["viewCount"]),
            "videoCount": int(ch["statistics"]["videoCount"]), "videos": {}}
    for v in vids:
        s = v["statistics"]
        snap["videos"][v["id"]] = {"title": v["snippet"]["title"],
            "publishedAt": v["snippet"]["publishedAt"],
            "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0))}
    (REPORT_DIR / "latest-snapshot.json").write_text(json.dumps(snap, indent=2))

def report(ch, vids, prev):
    rome = timezone(timedelta(hours=1))
    now = datetime.now(timezone.utc)
    now_r = now.astimezone(rome)
    st = ch["statistics"]
    subs, tv, vc = int(st["subscriberCount"]), int(st["viewCount"]), int(st["videoCount"])
    sd = f" ({'+' if (d:=subs-prev['subscribers'])>=0 else ''}{d})" if prev else ""
    vd = f" ({'+' if (d:=tv-prev['totalViews'])>=0 else ''}{d:,})" if prev else ""

    entries = []
    for v in vids:
        s = v["statistics"]
        pub = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        views = int(s.get("viewCount", 0))
        likes = int(s.get("likeCount", 0))
        comments = int(s.get("commentCount", 0))
        entries.append({"id": v["id"], "title": v["snippet"]["title"], "pub": pub,
            "views": views, "likes": likes, "comments": comments,
            "dur": dur_fmt(v["contentDetails"]["duration"]),
            "dur_s": dur_sec(v["contentDetails"]["duration"]),
            "lr": likes/views*100 if views else 0})

    w7 = now - timedelta(days=7)
    w30 = now - timedelta(days=30)
    week = [e for e in entries if e["pub"] >= w7]
    month = [e for e in entries if w30 <= e["pub"] < w7]

    avg_v = sum(e["views"] for e in entries) / len(entries) if entries else 0
    avg_lr = sum(e["lr"] for e in entries) / len(entries) if entries else 0
    avg_c = sum(e["comments"] for e in entries) / len(entries) if entries else 0
    avg_d = sum(e["dur_s"] for e in entries) / len(entries) if entries else 0

    L = []
    L.append("# YouTube Weekly Report")
    L.append(f"*Generated: {now_r.strftime('%A, %B %d, %Y at %H:%M')} (Rome)*\n")
    L.append("## Channel Overview\n")
    L.append("| Metric | Value |")
    L.append("|--------|-------|")
    L.append(f"| Subscribers | {subs:,}{sd} |")
    L.append(f"| Total views | {tv:,}{vd} |")
    L.append(f"| Videos | {vc} |")
    L.append(f"| Avg views/video | {avg_v:,.0f} |")
    L.append(f"| Avg like ratio | {avg_lr:.1f}% |")
    L.append(f"| Avg comments/video | {avg_c:.1f} |")
    L.append(f"| Avg duration | {int(avg_d//60)}:{int(avg_d%60):02d} |")
    L.append("")

    if week:
        L.append("## This Week\n")
        for e in week:
            dlt = ""
            if prev and prev.get("videos", {}).get(e["id"]):
                p = prev["videos"][e["id"]]
                dlt = f" *(+{e['views']-p['views']} views)*"
            L.append(f"### {e['title']}")
            L.append(f"- Published: {e['pub'].strftime('%Y-%m-%d')} | Duration: {e['dur']}")
            L.append(f"- Views: {e['views']:,} | Likes: {e['likes']} ({e['lr']:.1f}%) | Comments: {e['comments']}{dlt}")
            L.append("")

    if month:
        L.append("## Last 30 Days\n")
        L.append("| Video | Views | Likes (%) | Comments |")
        L.append("|-------|-------|-----------|----------|")
        for e in sorted(month, key=lambda x: x["views"], reverse=True):
            L.append(f"| {e['title'][:55]} | {e['views']:,} | {e['likes']} ({e['lr']:.1f}%) | {e['comments']} |")
        L.append("")

    L.append("## Top 5 by Views\n")
    L.append("| # | Video | Views | Likes (%) | Comments |")
    L.append("|---|-------|-------|-----------|----------|")
    for i, e in enumerate(sorted(entries, key=lambda x: x["views"], reverse=True)[:5], 1):
        L.append(f"| {i} | {e['title'][:55]} | {e['views']:,} | {e['likes']} ({e['lr']:.1f}%) | {e['comments']} |")
    L.append("")

    L.append("## Top 5 by Engagement (min 100 views)\n")
    L.append("| # | Video | Like Ratio | Views |")
    L.append("|---|-------|------------|-------|")
    qual = [e for e in entries if e["views"] >= 100]
    for i, e in enumerate(sorted(qual, key=lambda x: x["lr"], reverse=True)[:5], 1):
        L.append(f"| {i} | {e['title'][:55]} | {e['lr']:.1f}% | {e['views']:,} |")
    L.append("")

    L.append("## Most Discussed\n")
    L.append("| # | Video | Comments | Views |")
    L.append("|---|-------|----------|-------|")
    for i, e in enumerate(sorted(entries, key=lambda x: x["comments"], reverse=True)[:5], 1):
        L.append(f"| {i} | {e['title'][:55]} | {e['comments']} | {e['views']:,} |")
    L.append("")

    pats = {}
    for e in entries:
        t = e["title"].lower()
        tags = []
        if "openclaw" in t or "open claw" in t: tags.append("OpenClaw")
        if any(w in t for w in ["resonantos", "resonant"]): tags.append("ResonantOS")
        if any(w in t for w in ["fix", "stop", "delusion", "problem", "sabotag"]): tags.append("Problem/Fix")
        if any(w in t for w in ["built", "build", "brain", "engineer", "blueprint"]): tags.append("Building")
        if any(w in t for w in ["philosophy", "sovereign", "augmentat"]): tags.append("Philosophy")
        for tag in tags:
            pats.setdefault(tag, {"n": 0, "v": 0, "l": 0})
            pats[tag]["n"] += 1; pats[tag]["v"] += e["views"]; pats[tag]["l"] += e["likes"]

    if pats:
        L.append("## Content Patterns\n")
        L.append("| Pattern | Videos | Avg Views | Avg Likes |")
        L.append("|---------|--------|-----------|-----------|")
        for tag, d in sorted(pats.items(), key=lambda x: x[1]["v"]/x[1]["n"], reverse=True):
            L.append(f"| {tag} | {d['n']} | {d['v']/d['n']:,.0f} | {d['l']/d['n']:,.0f} |")
        L.append("")

    under = [e for e in entries if e["views"] < avg_v * 0.5 and e["pub"] < w7]
    if under:
        L.append("## Underperformers (< 50% avg views)\n")
        for e in sorted(under, key=lambda x: x["views"])[:5]:
            L.append(f"- **{e['title'][:60]}** ({e['views']:,} views, {e['lr']:.1f}%)")
        L.append("")

    L.append("## Insights\n")
    days = {}
    for e in entries:
        d = e["pub"].strftime("%A")
        days.setdefault(d, {"n": 0, "v": 0})
        days[d]["n"] += 1; days[d]["v"] += e["views"]
    best = max(days.items(), key=lambda x: x[1]["v"]/x[1]["n"])
    L.append(f"- **Best publish day:** {best[0]} (avg {best[1]['v']/best[1]['n']:,.0f} views, {best[1]['n']} videos)")

    for label, lo, hi in [("Short (<15m)", 0, 900), ("Medium (15-30m)", 900, 1800), ("Long (30m+)", 1800, 99999)]:
        grp = [e for e in entries if lo <= e["dur_s"] < hi]
        if grp:
            L.append(f"- **{label}:** {len(grp)} videos, avg {sum(e['views'] for e in grp)/len(grp):,.0f} views")

    if week:
        L.append(f"- **This week total:** {sum(e['views'] for e in week):,} views across {len(week)} videos")

    L.append("")
    L.append("---")
    L.append(f"*Next report: {(now_r + timedelta(days=7)).strftime('%A, %B %d, %Y')}*")
    return "\n".join(L)

def main():
    load_api_key()
    out = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv): out = sys.argv[idx + 1]

    print("Fetching channel...", file=sys.stderr)
    ch = get_channel()
    print("Fetching videos...", file=sys.stderr)
    vids = get_videos()
    print(f"Got {len(vids)} videos", file=sys.stderr)

    prev = load_prev()
    rpt = report(ch, vids, prev)
    save_snap(ch, vids)

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(rpt)
        print(f"Saved to {out}", file=sys.stderr)
    else:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ds = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        p = REPORT_DIR / f"youtube-report-{ds}.md"
        p.write_text(rpt)
        print(f"Saved to {p}", file=sys.stderr)
        print(rpt)

if __name__ == "__main__":
    main()
