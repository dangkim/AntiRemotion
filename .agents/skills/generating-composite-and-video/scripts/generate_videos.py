#!/usr/bin/env python3
"""
Generate composite images and video clips for each shot — fully parallelized.

Both phases use the same kie.ai Jobs API (taskId-based polling), so ALL shots
run concurrently in both phases:

  Phase 1 — ALL composite images IN PARALLEL (flux-2/pro-image-to-image)
    • Submits all shots simultaneously → each gets a unique taskId
    • Polls all tasks concurrently → total time ≈ slowest single composite
    • Downloads composites to ./composites/{shot_id}.png

  Phase 2 — ALL video clips IN PARALLEL (grok-imagine/image-to-video)
    • Submits all shots simultaneously → each gets a unique taskId
    • Polls all tasks concurrently → total time ≈ slowest single video
    • Downloads clips to ./clips/{shot_id}.mp4

Config — create a .env file in your project directory:
  KIE_API_TOKEN=your_kie_api_key_here
  IMGBB_API_KEY=your_imgbb_api_key_here

  On first run the script auto-creates a .env template if one is not found.

Usage:
  cd /path/to/your/project
  python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py

Requirements:
  pip install requests
  characters.json and backgrounds.json must have image_url fields
  (populated by generate_images.py from Step 3 of the pipeline).
"""

import os
import json
import time
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
import base64


# ── Config loading (.env) ─────────────────────────────────────────────────────

_ENV_TEMPLATE = """\
# Story-to-Animation — API Keys
# Get your kie.ai key from: https://kie.ai -> Dashboard -> API Keys
# Get your imgbb key from:  https://api.imgbb.com (free account)

KIE_API_TOKEN=your_kie_api_key_here
IMGBB_API_KEY=your_imgbb_api_key_here
"""

def load_env() -> None:
    """Load .env from the project directory into os.environ.
    Auto-creates a template .env and exits cleanly if none is found.
    Real environment variables always take precedence.
    """
    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text(_ENV_TEMPLATE, encoding="utf-8")
        print("\n  .env file created in your project directory.")
        print("  -> Open .env, fill in your API keys, then re-run this script.\n")
        raise SystemExit(0)

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val

    print("  Loaded API keys from .env")

def get_key(name: str) -> str:
    """Return a required key from os.environ (populated by load_env)."""
    val = os.environ.get(name, "").strip()
    placeholder = f"your_{name.lower()}_here"
    if not val or val == placeholder:
        print(f"\nERROR: '{name}' is not set in .env")
        print(f"  Open .env in your project directory and set:  {name}=your_actual_key")
        raise SystemExit(1)
    return val

load_env()
KIE_API_TOKEN = get_key("KIE_API_TOKEN")


# ── API endpoints (both phases use the same kie.ai Jobs API) ──────────────────

JOBS_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
JOBS_STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

POST_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {KIE_API_TOKEN}",
}
GET_HEADERS = {"Authorization": f"Bearer {KIE_API_TOKEN}"}


# ── Tunable settings ──────────────────────────────────────────────────────────

COMPOSITE_MAX_WORKERS = 2    # Parallel composite jobs (Reduced for reliability)
VIDEO_MAX_WORKERS     = 2    # Parallel video jobs (Reduced for reliability)

POLL_INTERVAL_START   = 15   # Seconds between first few polls
POLL_INTERVAL_STEP    = 5    # Increase interval by this much after every 5 polls
MAX_POLLS             = 60   # Max polls (60 × ~20s avg = 20 minutes per task)

# grok-imagine/image-to-video settings
VIDEO_ASPECT_RATIO     = "16:9"       # "16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "auto"
VIDEO_DURATION         = "6"          # duration must be a string for grok-imagine/image-to-video
VIDEO_RESOLUTION       = "720p"       # "720p" or "480p"


# ── Thread-safe print ─────────────────────────────────────────────────────────

_print_lock = threading.Lock()

def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

def fmt_elapsed(start: float) -> str:
    s = int(time.time() - start)
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


# ── Shared Jobs API helpers ───────────────────────────────────────────────────

def submit_job(model: str, input_payload: dict) -> tuple:
    """Submit any kie.ai job with up to 3 retries for transient errors."""
    payload = {"model": model, "input": input_payload}
    for attempt in range(1, 4):
        try:
            resp   = requests.post(JOBS_CREATE_URL, headers=POST_HEADERS, json=payload, timeout=30)
            result = resp.json()
            if result.get("code") != 200:
                msg = result.get("msg", "Unknown API error")
                if "internal" in msg.lower() or "busy" in msg.lower():
                    tprint(f"    [submit] transient error ({msg}), retrying in {attempt*5}s...")
                    time.sleep(attempt * 5)
                    continue
                return None, msg
            return result["data"]["taskId"], None
        except Exception as e:
            if attempt < 3:
                time.sleep(attempt * 5)
                continue
            return None, str(e)
    return None, "Failed after 3 submission attempts"


def poll_job(task_id: str, label: str) -> tuple:
    """Poll a Jobs API task by taskId until done with adaptive backoff."""
    params = {"taskId": task_id}
    current_interval = POLL_INTERVAL_START
    
    for attempt in range(1, MAX_POLLS + 1):
        time.sleep(current_interval)
        
        # Adaptive backoff: increase interval every 5 attempts
        if attempt % 5 == 0 and current_interval < 60:
            current_interval += POLL_INTERVAL_STEP
            
        try:
            resp  = requests.get(JOBS_STATUS_URL, headers=GET_HEADERS, params=params, timeout=30)
            data  = resp.json().get("data", {})
            state = data.get("state", "").lower()

            if state == "success":
                result = data.get("resultJson", {})
                if isinstance(result, str):
                    result = json.loads(result)
                urls = result.get("resultUrls", [])
                if urls:
                    return urls[0], None
                return None, "state=success but no resultUrls in response"

            elif state == "fail":
                return None, data.get("failMsg", "Job failed (no reason given)")

            else:
                tprint(f"    [{label}] {state or 'waiting'} (attempt {attempt}, next poll in {current_interval}s)")

        except Exception as e:
            tprint(f"    [{label}] poll error: {e}")

    return None, f"Timed out after {attempt} polls"


def download_file(url: str, output_path: Path) -> bool:
    """Download file with 3 retries for transient network issues."""
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)
            if output_path.stat().st_size > 0:
                return True
        except Exception as e:
            if attempt < 3:
                tprint(f"    Download attempt {attempt} failed ({e}), retrying...")
                time.sleep(attempt * 5)
            else:
                tprint(f"    Download failed after 3 attempts: {e}")
    return False


def upload_to_imgbb(local_path: Path, api_key: str) -> str:
    """Upload local PNG to imgbb. Returns public_url or None."""
    try:
        url = "https://api.imgbb.com/1/upload"
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        resp = requests.post(
            url,
            params={"key": api_key},
            data={"image": b64},
            timeout=60,
        )
        result = resp.json()
        if result.get("success"):
            return result["data"]["url"]
        return None
    except Exception as e:
        tprint(f"    Upload failed: {e}")
        return None


# ── Phase 1 worker: composite image ──────────────────────────────────────────

def run_composite(shot: dict, bg_map: dict, char_map: dict,
                  composite_path: Path) -> tuple:
    """Generate one composite image. Returns (shot_id, url, None) or (shot_id, None, error)."""
    sid = shot["shot_id"]
    t0  = time.time()

    # Build input_urls: background first, then characters
    bg         = bg_map.get(shot.get("background", ""), {})
    input_urls = []
    if bg.get("image_url"):
        input_urls.append(bg["image_url"])
    for cid in shot.get("characters", []):
        c = char_map.get(cid, {})
        if c.get("image_url"):
            input_urls.append(c["image_url"])

    if not input_urls:
        return sid, None, "No image_urls found for this shot"

    prompt = (
        f"Composited animation scene: {shot.get('action', 'characters in location')}. "
        f"Pixar-style 3D animation, cinematic 16:9 composition, "
        f"high quality render, no text, no UI elements."
    )

    task_id, err = submit_job("flux-2/pro-image-to-image", {
        "input_urls":   input_urls,
        "prompt":       prompt,
        "aspect_ratio": "16:9",
        "resolution":   "1K",
    })
    if not task_id:
        return sid, None, f"Submit failed: {err}"

    tprint(f"  [{sid}] composite submitted → taskId: {task_id[:16]}...")

    url, err = poll_job(task_id, f"{sid}/composite")
    if not url:
        return sid, None, err

    download_file(url, composite_path)
    tprint(f"  [{sid}] composite done ({fmt_elapsed(t0)}) → composites/{sid}.png")
    return sid, url, None


# ── Phase 2 worker: grok-imagine/image-to-video (parallel — taskId-based) ─────

def run_video(shot: dict, composite_url: str, clip_path: Path) -> tuple:
    """Generate one Grok Imagine video clip. Returns (shot_id, True, None) or (shot_id, False, error)."""
    sid = shot["shot_id"]
    t0  = time.time()

    # Grok Imagine requires @image1 prefix to reference the first image in image_urls
    original_prompt = shot.get("veo_prompt", shot.get("action", ""))
    grok_prompt = f"@image1 {original_prompt}"

    task_id, err = submit_job("grok-imagine/image-to-video", {
        "prompt":            grok_prompt,
        "image_urls":        [composite_url],
        "aspect_ratio":      VIDEO_ASPECT_RATIO,
        "duration":          VIDEO_DURATION,
        "resolution":        VIDEO_RESOLUTION,
        "upload_method":     "s3",
    })
    if not task_id:
        return sid, False, f"Submit failed: {err}"

    tprint(f"  [{sid}] video submitted   → taskId: {task_id[:16]}...")

    url, err = poll_job(task_id, f"{sid}/video")
    if not url:
        return sid, False, err

    if download_file(url, clip_path):
        tprint(f"  [{sid}] video done ({fmt_elapsed(t0)}) → clips/{sid}.mp4")
        return sid, True, None

    return sid, False, "Download failed"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate composite images and video clips.")
    parser.add_argument(
        "--shot", metavar="SHOT_ID",
        help="Process a single shot only (e.g. --shot shot_001). "
             "Claude uses this for per-shot approval workflow. "
             "Omit to process all pending shots at once.",
    )
    args = parser.parse_args()

    run_start = time.time()
    print("\n=== Story-to-Animation: Step 5 — Composite + Video Generation ===\n")

    # ── Load data ─────────────────────────────────────────────────────────────
    for fname in ["shots.json", "characters.json", "backgrounds.json"]:
        if not Path(fname).exists():
            print(f"ERROR: {fname} not found in current directory")
            raise SystemExit(1)

    shots_data = json.loads(Path("shots.json").read_text(encoding="utf-8"))
    chars_data = json.loads(Path("characters.json").read_text(encoding="utf-8"))
    bgs_data   = json.loads(Path("backgrounds.json").read_text(encoding="utf-8"))

    char_map = {c["character_id"]: c for c in chars_data["characters"]}
    bg_map   = {b["bg_id"]:        b for b in bgs_data["backgrounds"]}

    # Verify image_url fields (set by generate_images.py, Step 3)
    missing = []
    for c in chars_data["characters"]:
        if not c.get("image_url"):
            missing.append(f"  characters/{c['character_id']} — missing image_url")
    for b in bgs_data["backgrounds"]:
        if not b.get("image_url"):
            missing.append(f"  backgrounds/{b['bg_id']} — missing image_url")
    if missing:
        print("ERROR: image_url fields missing. Run generate_images.py (Step 3) first.")
        for m in missing:
            print(m)
        raise SystemExit(1)

    all_shots = shots_data.get("shots", [])

    # ── Build pending list ─────────────────────────────────────────────────────
    if args.shot:
        # Single-shot mode — Claude calls this once per shot for approval workflow
        target = next((s for s in all_shots if s["shot_id"] == args.shot), None)
        if not target:
            print(f"ERROR: shot_id '{args.shot}' not found in shots.json")
            raise SystemExit(1)
        clip_path = Path("clips") / f"{args.shot}.mp4"
        if clip_path.exists():
            print(f"[{args.shot}] clip already exists — nothing to do.")
            return
        pending = [target]
        skipped = []
        print(f"  Mode    : single-shot  ({args.shot})")
    else:
        # Bulk mode — process all pending shots without pausing
        pending = [s for s in all_shots if not (Path("clips") / f"{s['shot_id']}.mp4").exists()]
        skipped = [s["shot_id"] for s in all_shots if s not in pending]
        print(f"  Mode    : bulk  ({len(pending)} pending, {len(skipped)} already done)")

    print(f"  Video   : grok-imagine/image-to-video  (duration: {VIDEO_DURATION}s, aspect: {VIDEO_ASPECT_RATIO})\n")

    if skipped:
        print(f"Skipping {len(skipped)} shot(s) with existing clips: {', '.join(skipped)}")
    if not pending:
        print("All clips already exist. Nothing to do.")
        return

    Path("composites").mkdir(exist_ok=True)
    Path("clips").mkdir(exist_ok=True)

    results        = {"success": [], "failed": [], "skipped": skipped}
    composite_urls = {}   # shot_id → composite_url (filled in Phase 1)

    # ── Phase 1: Composites ───────────────────────────────────────────────────
    p1_start = time.time()

    if args.shot:
        # Single shot — run directly, no thread pool needed
        composite_file = Path("composites") / f"{args.shot}.png"
        if composite_file.exists():
            print(f"  [{args.shot}] composite already exists — skipping generation.")
            composite_urls[args.shot] = "local" # Sentinel to indicate it's already there
        else:
            print(f"Phase 1 — Composite: generating {args.shot}...\n")
            sid, url, err = run_composite(
                pending[0], bg_map, char_map,
                composite_file,
            )
            if url:
                composite_urls[sid] = url
            else:
                print(f"  [{sid}] composite FAILED: {err}")
                results["failed"].append(sid)
    else:
        # Bulk — all composites in parallel (skip existing)
        to_generate = []
        for shot in pending:
            sid = shot["shot_id"]
            composite_file = Path("composites") / f"{sid}.png"
            if composite_file.exists():
                composite_urls[sid] = "local"
            else:
                to_generate.append(shot)
        
        if to_generate:
            print(f"Phase 1 — Composites: submitting {len(to_generate)} jobs in parallel...\n")
            with ThreadPoolExecutor(max_workers=COMPOSITE_MAX_WORKERS) as ex:
                futures = {
                    ex.submit(
                        run_composite,
                        shot, bg_map, char_map,
                        Path("composites") / f"{shot['shot_id']}.png"
                    ): shot["shot_id"]
                    for shot in to_generate
                }
                for future in as_completed(futures):
                    sid, url, err = future.result()
                    if url:
                        composite_urls[sid] = url
                    else:
                        tprint(f"  [{sid}] composite FAILED: {err}")
                        results["failed"].append(sid)
        else:
            print("Phase 1 — Composites: All required composites already exist.")

    print(f"\nPhase 1 done in {fmt_elapsed(p1_start)}: "
          f"{len(composite_urls)}/{len(pending)} composites ready.\n")

    # ── Phase 2: All videos in parallel ───────────────────────────────────────
    # Only shots whose composite succeeded
    video_shots = [s for s in pending if s["shot_id"] in composite_urls]

    if not video_shots:
        print("No composites succeeded — cannot generate any videos.")
    else:
        p2_start = time.time()

        if args.shot:
            # Single shot — run directly
            print(f"Phase 2 — Video: generating {args.shot}...\n")
            sid = video_shots[0]["shot_id"]
            comp_url = composite_urls[sid]
            
            # If composite was local, we need to upload it to get a URL for Grok
            if comp_url == "local":
                IMGBB_API_KEY = get_key("IMGBB_API_KEY")
                tprint(f"  [{sid}] uploading local composite to imgbb...")
                comp_url = upload_to_imgbb(Path("composites") / f"{sid}.png", IMGBB_API_KEY)
                if not comp_url:
                    print(f"  [{sid}] failed to upload composite")
                    results["failed"].append(sid)
                    return

            sid, ok, err = run_video(video_shots[0], comp_url, Path("clips") / f"{sid}.mp4")
            if ok:
                results["success"].append(sid)
            else:
                print(f"  [{sid}] video FAILED: {err}")
                results["failed"].append(sid)
        else:
            # Bulk — all videos in parallel
            print(f"Phase 2 — Videos: submitting {len(video_shots)} jobs in parallel "
                  f"(grok-imagine/image-to-video)...\n")
            
            # Helper to ensure URL exists before submitting to thread pool
            def get_comp_url(sid):
                url = composite_urls[sid]
                if url == "local":
                    key = get_key("IMGBB_API_KEY")
                    tprint(f"  [{sid}] uploading local composite to imgbb...")
                    res = upload_to_imgbb(Path("composites") / f"{sid}.png", key)
                    if not res:
                        tprint(f"  [{sid}] failed to upload composite")
                    return res
                return url

            with ThreadPoolExecutor(max_workers=VIDEO_MAX_WORKERS) as ex:
                # Prepare URLs first (sequential naturally, but could be threaded)
                final_urls = {}
                for s in video_shots:
                    u = get_comp_url(s["shot_id"])
                    if u: final_urls[s["shot_id"]] = u
                
                valid_video_shots = [s for s in video_shots if s["shot_id"] in final_urls]
                
                futures = {
                    ex.submit(
                        run_video,
                        shot,
                        final_urls[shot["shot_id"]],
                        Path("clips") / f"{shot['shot_id']}.mp4"
                    ): shot["shot_id"]
                    for shot in valid_video_shots
                }
                for future in as_completed(futures):
                    sid, ok, err = future.result()
                    if ok:
                        results["success"].append(sid)
                    else:
                        tprint(f"  [{sid}] video FAILED: {err}")
                        results["failed"].append(sid)

        print(f"\nPhase 2 done in {fmt_elapsed(p2_start)}: "
              f"{len(results['success'])}/{len(video_shots)} videos ready.")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_run_time = fmt_elapsed(run_start)

    print(f"\n{'='*55}")
    print(f"  Total run time : {total_run_time}")
    print(f"  Generated      : {len(results['success'])} clips")
    print(f"  Skipped        : {len(results['skipped'])} (clips already existed)")
    print(f"  Failed         : {len(results['failed'])}")
    print(f"{'='*55}")
    print(f"  Composites → ./composites/")
    print(f"  Clips      → ./clips/")

    if results["failed"]:
        print("\nFailed shots (delete composite + clip file then re-run):")
        for sid in results["failed"]:
            print(f"  - {sid}")
        raise SystemExit(1)
    else:
        print("\nAll done! The Story-to-Animation pipeline is complete.")


if __name__ == "__main__":
    main()
