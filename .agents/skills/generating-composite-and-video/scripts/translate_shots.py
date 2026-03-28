import json
from pathlib import Path
import os

def translate_dialogue():
    # Go to project root since this script is in scripts/
    # Actually, let's assume it's run from project root, same as others.
    shots_path = Path("shots.json")
    if not shots_path.exists():
        print(f"Error: shots.json not found at {shots_path.absolute()}")
        return

    with open(shots_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # High-quality Vietnamese translation mapping
    translations = {
        "shot_001": "Chào các bạn! Mình là Minh! Hôm nay mình sẽ giới thiệu cho các bạn tiết học YÊU THÍCH nhất của mình — Mỹ thuật!",
        "shot_002": "Trong giờ mỹ thuật, chúng mình được học về một điều cực kỳ thú vị... đó là SẢN PHẨM MỸ THUẬT!",
        "shot_003": "Bức tranh đó là của MÌNH đấy! Mình đã vẽ nó vào tuần trước!",
        "shot_004": "Mỹ thuật tạo hình nghĩa là... những thứ chúng mình làm ra để các bạn NGẮM nhìn. Như tranh vẽ này, hình vẽ này, và cả — những bức tượng nữa!",
        "shot_005": "Cô Lan còn dạy chúng mình cách SỬ DỤNG tất cả các loại vật liệu nữa! Như là bút màu sáp...",
        "shot_006": "Cô ấy luôn giúp bức tranh của mình trông đẹp hơn.",
        "shot_007": "Và còn có cả MỸ THUẬT ỨNG DỤNG nữa! Đây là khi chúng mình dùng... những đồ vật CŨ... để tạo ra những tác phẩm MỚI!",
        "shot_008": "Bạn Lena đã làm con cú đó từ một vỏ chai nước đấy. Một VỎ CHAI NƯỚC luôn!",
        "shot_009": "Chúng mình còn học cả... cắt và dán giấy nữa.",
        "shot_010": "Các bạn cắt các hình khối... rồi dán chúng lại... và bất ngờ chưa, nó đã trở thành một BỨC TRANH!",
        "shot_011": "Vậy thì — ai là người tạo ra nghệ thuật? Các bạn có thể nghĩ chỉ có nhà điêu khắc... hay nhà thiết kế thời trang mới làm nghệ thuật...",
        "shot_012": "Nhưng thực ra? Nghệ thuật được tạo ra bởi... NHỮNG NGƯỜI YÊU NGHỆ THUẬT! Bất cứ ai yêu nghệ thuật đều có thể làm ra nó!",
        "shot_013": "Nghệ thuật là dành cho TẤT CẢ mọi lứa tuổi!",
        "shot_014": "Ông Nam đã 70 tuổi rồi... mà ông VẪN vẽ tranh đấy!",
        "shot_015": "Chúng mình vẽ tranh ngay tại lớp học! Cô Lan dạy chúng mình cách quan sát mọi thứ... và thể hiện chúng lên trang giấy.",
        "shot_016": "Và thỉnh thoảng... chúng mình còn ra NGOÀI TRỜI để vẽ nữa!",
        "shot_017": "Vẽ ở ngoài trời là TUYỆT nhất vì thiên nhiên mang lại cho chúng mình rất nhiều cảm hứng để vẽ.",
        "shot_018": "Bút màu sáp: Để tạo ra MÀU SẮC!",
        "shot_019": "Và ĐÂY — là dành cho những bức họa định cao!",
        "shot_020": "Và ĐÓ... chính là giờ Mỹ thuật. Mỹ thuật tạo hình. Mỹ thuật ứng dụng. Bút chì, màu sáp, đất sét, giấy, sơn...",
        "shot_021": "Nghệ thuật dành cho TẤT CẢ MỌI NGƯỜI. Kể cả BẠN đấy!"
    }

    for shot in data["shots"]:
        sid = shot["shot_id"]
        if sid in translations:
            shot["dialogue_vn"] = translations[sid]

    with open(shots_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Success: Added dialogue_vn (Vietnamese) to shots.json")

if __name__ == "__main__":
    translate_dialogue()
