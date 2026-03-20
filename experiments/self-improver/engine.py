#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import requests
except ModuleNotFoundError:
    requests = None


EMBEDDING_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-embedding-001:embedContent"
)
SIMILARITY_THRESHOLD = 0.80


class _StdlibResponse:
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self._body = body

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise RuntimeError(f"HTTP {self.status_code}: {self._body}")

    def json(self) -> dict:
        return json.loads(self._body)


def post_json(url: str, params: dict, body: dict, timeout: int):
    if requests is not None:
        return requests.post(url, params=params, json=body, timeout=timeout)

    encoded = urllib.parse.urlencode(params)
    full_url = f"{url}?{encoded}" if encoded else url
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        full_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _StdlibResponse(resp.status, resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return _StdlibResponse(exc.code, body_text)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest_date_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_google_api_key(auth_profiles_path: Path) -> str:
    payload = load_json(auth_profiles_path, {})
    try:
        return payload["profiles"]["google:manual"]["token"]
    except KeyError as exc:
        raise RuntimeError(
            f"Missing API key at profiles['google:manual']['token'] in {auth_profiles_path}"
        ) from exc


def fetch_embedding(text: str, api_key: str) -> List[float]:
    body = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text}]},
    }
    response = post_json(EMBEDDING_ENDPOINT, params={"key": api_key}, body=body, timeout=30)
    response.raise_for_status()
    payload = response.json()
    try:
        values = payload["embedding"]["values"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected embedding response format: {payload}") from exc
    if not isinstance(values, list) or not values:
        raise RuntimeError("Embedding response did not include a valid vector.")
    return [float(v) for v in values]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Cannot compare embeddings with different dimensions.")
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def normalize_source(raw: str) -> str:
    source = (raw or "").lower()
    if "self" in source:
        return "self"
    if "human" in source:
        return "human"
    if "archivist" in source:
        return "archivist"
    return "other"


def short_lesson(text: str, width: int = 84) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= width:
        return cleaned
    return cleaned[: width - 3] + "..."


def build_digest(date_str: str, lessons: List[dict], new_patterns: List[dict]) -> str:
    source_counts: Dict[str, int] = {"self": 0, "human": 0, "archivist": 0}
    for lesson in lessons:
        source_key = normalize_source(lesson.get("source", ""))
        if source_key in source_counts:
            source_counts[source_key] += 1

    tracked_count = sum(1 for lesson in lessons if lesson.get("status") == "tracked")
    lines = [
        f"🔄 Self-Improvement Digest — {date_str}",
        "",
        (
            "Captured: "
            f"{len(lessons)} lessons (sources: "
            f"{source_counts['self']} self, "
            f"{source_counts['human']} human, "
            f"{source_counts['archivist']} archivist)"
        ),
        f"New patterns: {len(new_patterns)}",
    ]
    for pattern in new_patterns:
        lines.append(
            f"- {pattern['ts']} matched {pattern['similarTo']}: {short_lesson(pattern['lesson'])}"
        )
    lines.extend(
        [
            f"Tracked (one-off): {tracked_count}",
            "Escalations: 0",
        ]
    )
    return "\n".join(lines)


def run_pipeline(dry_run: bool) -> int:
    base_dir = Path(__file__).resolve().parent
    queue_path = Path.home() / ".openclaw" / "workspace" / "memory" / "lessons-queue.jsonl"
    auth_profiles_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
    cache_path = base_dir / "embeddings-cache.json"
    digest_dir = base_dir / "digests"
    date_str = digest_date_utc()
    processed_at = utc_now_iso()

    print("1) Loading queue...")
    lessons = load_jsonl(queue_path)
    print(f"   Loaded lessons: {len(lessons)}")

    pending_indices = [idx for idx, lesson in enumerate(lessons) if lesson.get("status") == "pending"]
    print(f"   Pending lessons: {len(pending_indices)}")

    print("2) Computing embeddings for pending lessons...")
    cache_raw = load_json(cache_path, {})
    cache: Dict[str, List[float]] = {
        key: [float(v) for v in val] for key, val in cache_raw.items() if isinstance(val, list)
    }
    api_key = read_google_api_key(auth_profiles_path)
    computed_count = 0
    cached_count = 0
    cache_updated = False
    embeddings_by_index: Dict[int, List[float]] = {}

    for idx in pending_indices:
        lesson_text = lessons[idx].get("lesson", "")
        text_hash = sha256_text(lesson_text)
        lessons[idx]["embeddingHash"] = text_hash
        if text_hash in cache:
            embedding = cache[text_hash]
            cached_count += 1
        else:
            embedding = fetch_embedding(lesson_text, api_key)
            computed_count += 1
            if not dry_run:
                cache[text_hash] = embedding
                cache_updated = True
        embeddings_by_index[idx] = embedding

    print(f"   Embeddings cached: {cached_count}")
    print(f"   Embeddings computed: {computed_count}")

    print("3) Running repetition detection...")
    processed_indices = [idx for idx, lesson in enumerate(lessons) if lesson.get("status") != "pending"]
    similarity_rows: List[Tuple[str, str, float]] = []
    new_patterns: List[dict] = []

    for idx in pending_indices:
        lesson = lessons[idx]
        lesson["processedAt"] = processed_at
        severity = (lesson.get("severity") or "").lower()

        if severity == "critical":
            lesson["status"] = "pattern-detected"
            lesson["occurrences"] = max(1, int(lesson.get("occurrences", 1)))
            processed_indices.append(idx)
            print(f"   {lesson.get('ts', f'index-{idx}')}: critical severity, skipped similarity gate")
            continue

        best_match_idx = None
        best_similarity = -1.0
        current_embedding = embeddings_by_index[idx]

        for candidate_idx in processed_indices:
            candidate_hash = lessons[candidate_idx].get("embeddingHash")
            if candidate_idx not in embeddings_by_index:
                if candidate_hash and candidate_hash in cache:
                    embeddings_by_index[candidate_idx] = cache[candidate_hash]
                else:
                    candidate_text = lessons[candidate_idx].get("lesson", "")
                    candidate_hash = sha256_text(candidate_text)
                    lessons[candidate_idx]["embeddingHash"] = candidate_hash
                    if candidate_hash in cache:
                        embeddings_by_index[candidate_idx] = cache[candidate_hash]
                        cached_count += 1
                    else:
                        candidate_embedding = fetch_embedding(candidate_text, api_key)
                        embeddings_by_index[candidate_idx] = candidate_embedding
                        computed_count += 1
                        if not dry_run:
                            cache[candidate_hash] = candidate_embedding
                            cache_updated = True

            similarity = cosine_similarity(current_embedding, embeddings_by_index[candidate_idx])
            similarity_rows.append(
                (
                    lesson.get("ts", f"index-{idx}"),
                    lessons[candidate_idx].get("ts", f"index-{candidate_idx}"),
                    similarity,
                )
            )
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_idx = candidate_idx

        if best_match_idx is not None and best_similarity > SIMILARITY_THRESHOLD:
            matched = lessons[best_match_idx]
            new_occurrences = int(matched.get("occurrences", 1)) + 1

            lesson["status"] = "pattern-detected"
            lesson["similarTo"] = matched.get("ts")
            lesson["occurrences"] = new_occurrences

            matched["status"] = "pattern-detected"
            matched["occurrences"] = new_occurrences
            if not matched.get("similarTo"):
                matched["similarTo"] = lesson.get("ts")

            new_patterns.append(
                {
                    "ts": lesson.get("ts", f"index-{idx}"),
                    "similarTo": matched.get("ts", f"index-{best_match_idx}"),
                    "lesson": lesson.get("lesson", ""),
                    "similarity": best_similarity,
                }
            )
            print(
                f"   {lesson.get('ts', f'index-{idx}')}: pattern-detected "
                f"(matched {matched.get('ts', f'index-{best_match_idx}')}, sim={best_similarity:.4f})"
            )
        else:
            lesson["status"] = "tracked"
            lesson["occurrences"] = max(1, int(lesson.get("occurrences", 1)))
            print(f"   {lesson.get('ts', f'index-{idx}')}: tracked (no match > {SIMILARITY_THRESHOLD})")

        processed_indices.append(idx)

    if similarity_rows:
        print("   Similarity matrix results:")
        for row in similarity_rows:
            print(f"   - {row[0]} vs {row[1]} => {row[2]:.4f}")
    else:
        print("   Similarity matrix results: no comparisons (no previously processed lessons).")

    print("4) Generating digest...")
    digest_text = build_digest(date_str, lessons, new_patterns)
    print("   Digest preview:")
    print(digest_text)

    print("5) Updating queue and cache...")
    if dry_run:
        print("   Dry-run mode: no file modifications.")
        return 0

    if cache_updated:
        save_json(cache_path, cache)
        print(f"   Wrote embeddings cache: {cache_path}")
    else:
        print(f"   Embeddings cache unchanged: {cache_path}")

    digest_dir.mkdir(parents=True, exist_ok=True)
    digest_path = digest_dir / f"{date_str}.txt"
    with digest_path.open("w", encoding="utf-8") as f:
        f.write(digest_text + "\n")
    print(f"   Wrote digest: {digest_path}")

    write_jsonl(queue_path, lessons)
    print(f"   Rewrote queue: {queue_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-Improvement Pipeline Core Engine")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without writing files")
    args = parser.parse_args()
    return run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
