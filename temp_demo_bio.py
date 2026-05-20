import os
import sys
import base64
from io import BytesIO
from PIL import Image

# Add PepBielsa path
sys.path.insert(0, r"C:\D\Bot Tele\PepBielsa")

from custom_visuals import generate_player_bio_card

# 1. Create a dummy Cole Palmer background since direct download failed due to 403 Forbidden/captcha
img = Image.new("RGB", (1080, 1080), color="#190e29")
img_path = r"C:\D\Bot Tele\PepBielsa\temp_palmer_bg.jpg"
img.save(img_path)

# 2. Stats
stats = {
    "APPEARANCES": "10",
    "MINUTES PLAYED": "763",
    "GOALS": "0",
    "EXPECTED GOALS (XG)": "3.42",
    "TOTAL SHOTS": "25",
    "ASSISTS": "0",
    "CHANCES CREATED": "11"
}

# 3. Generate Card
img_b64 = generate_player_bio_card(
    player_name="Cole Palmer",
    player_sub="Last 10 Competitive Appearances For Chelsea",
    stats=stats,
    user_image_path=img_path
)

# 4. Save Image
img_data = base64.b64decode(img_b64)
workspace_path = r"C:\D\Bot Tele\PepBielsa\outputs\Cole_Palmer_Bio_Demo.png"
gemini_path = r"C:\Users\akram\.gemini\antigravity\brain\afee9046-d8f2-4707-8fe4-6563af57e94f\Cole_Palmer_Bio_Demo.png"

with open(workspace_path, "wb") as f:
    f.write(img_data)
with open(gemini_path, "wb") as f:
    f.write(img_data)

print(f"Saved to {workspace_path}")
