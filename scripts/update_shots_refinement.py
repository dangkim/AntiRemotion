import json
from pathlib import Path

def update_shots():
    path = Path("shots.json")
    if not path.exists():
        print("shots.json not found")
        return

    # Try multiple encodings
    content = None
    for enc in ["utf-8-sig", "utf-8", "utf-16", "latin-1"]:
        try:
            content = path.read_text(encoding=enc)
            print(f"Read success with {enc}")
            break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        print("Could not decode shots.json with common encodings.")
        return

    data = json.loads(content)

    # Teacher description for prompts
    teacher_desc = "Cô Hòa, a Vietnamese teacher in her late 40s wearing a light blue patterned Áo Dài with purple trousers"
    # Background student description for prompts
    classroom_bg = "diverse 6-year-old students sitting at desks and busy with art projects in the background"
    garden_bg = "many students sitting on stools and sketching in the background"

    updated_ids = []

    for shot in data["shots"]:
        sid = shot["shot_id"]
        
        # Classroom shots (bg_001)
        if shot.get("background") == "bg_001":
            if classroom_bg not in shot["veo_prompt"]:
                shot["veo_prompt"] += f", with {classroom_bg}"
                shot["action"] += f" with other students visible in the background"
                updated_ids.append(sid)
        
        # Garden shots (bg_006)
        elif shot.get("background") == "bg_006":
            if garden_bg not in shot["veo_prompt"]:
                shot["veo_prompt"] += f", with {garden_bg}"
                shot["action"] += f" with other students visible in the background"
                updated_ids.append(sid)

        # Teacher shots (char_002 / Cô Hòa)
        if "char_002" in shot.get("characters", []):
            if "Cô Hòa" not in shot.get("veo_prompt", ""):
                shot["veo_prompt"] = shot.get("veo_prompt", "").replace("Ms. Lan", "Cô Hòa")
                # Add physical description of her outfit
                if "Áo Dài" not in shot.get("veo_prompt", ""):
                    shot["veo_prompt"] += f", featuring {teacher_desc}"
                updated_ids.append(sid)

    # Final name replacement check (just in case)
    for shot in data["shots"]:
        shot["action"] = shot["action"].replace("Ms. Lan", "Cô Hòa")
        shot["veo_prompt"] = shot.get("veo_prompt", "").replace("Ms. Lan", "Cô Hòa")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Updated {len(set(updated_ids))} affected shots in shots.json.")
    print(f"IDs: {', '.join(sorted(list(set(updated_ids))))}")

if __name__ == "__main__":
    update_shots()
