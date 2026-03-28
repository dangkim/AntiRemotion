#!/usr/bin/env python3
"""
Generate Vietnamese voiceover audio for each shot using edge-tts.
All dialogue is narrated by Minh (a young boy), so we use the male voice 'vi-VN-NamMinhNeural'.

Usage:
  python ~/.claude/skills/generating-composite-and-video/scripts/generate_audio.py
"""

import json
import subprocess
from pathlib import Path
import os
import argparse

VOICE = "vi-VN-NamMinhNeural"
# We could adjust rate or pitch to sound more like a 6-year-old boy.
# e.g., --rate=+10% --pitch=+20Hz
PITCH_ADJUST = "+15Hz"
RATE_ADJUST = "+5%"

def generate_tts(text: str, output_path: str):
    # Use edge-tts CLI tool
    cmd = [
        "edge-tts",
        "--voice", VOICE,
        "--rate", RATE_ADJUST,
        "--pitch", PITCH_ADJUST,
        "--text", text,
        "--write-media", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error generating audio for '{text[:20]}...': {result.stderr}")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Generate audio files for shots via Edge-TTS.")
    parser.add_argument("--shot", type=str, help="Process only a specific shot ID (e.g. shot_001)")
    args = parser.parse_args()

    shots_path = Path("shots.json")
    if not shots_path.exists():
        print("Error: shots.json not found.")
        return

    with open(shots_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    audio_dir = Path("audio")
    audio_dir.mkdir(exist_ok=True)

    shots_to_process = data["shots"]
    if args.shot:
        shots_to_process = [s for s in shots_to_process if s["shot_id"] == args.shot]
        if not shots_to_process:
            print(f"Error: Shot {args.shot} not found.")
            return

    success_count = 0
    total = len(shots_to_process)
    
    for shot in shots_to_process:
        sid = shot["shot_id"]
        text_vn = shot.get("dialogue_vn", "")
        
        if not text_vn:
            print(f"[{sid}] No Vietnamese dialogue found. Skipping.")
            continue
            
        output_file = audio_dir / f"{sid}.mp3"
        print(f"[{sid}] Generating audio: '{text_vn}'")
        
        if generate_tts(text_vn, str(output_file)):
            success_count += 1
            print(f"  -> Saved to {output_file}")
            
    print(f"\nDone: {success_count}/{total} audio files generated.")

if __name__ == "__main__":
    main()
