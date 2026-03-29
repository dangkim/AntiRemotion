#!/usr/bin/env python3
"""
Merge all shot clips in order into final_animation.mp4 using FFmpeg.
"""
import subprocess
import json
from pathlib import Path

def main():
    clips_dir = Path("clips")
    shots_data = json.loads(Path("shots.json").read_text(encoding="utf-8"))
    shot_ids = [s["shot_id"] for s in shots_data["shots"]]

    # Verify all clips exist
    missing = [sid for sid in shot_ids if not (clips_dir / f"{sid}.mp4").exists()]
    if missing:
        print(f"Missing clips: {', '.join(missing)}")
        raise SystemExit(1)

    # Write a concat list file for FFmpeg
    concat_file = Path("concat_list.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for sid in shot_ids:
            clip_path = (clips_dir / f"{sid}.mp4").resolve()
            f.write(f"file '{clip_path}'\n")

    output = Path("final_animation.mp4")
    print(f"Merging {len(shot_ids)} clips → {output} ...")

    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output)
    ], capture_output=True, text=True)

    concat_file.unlink(missing_ok=True)

    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr)
        raise SystemExit(1)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Done! → {output} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
