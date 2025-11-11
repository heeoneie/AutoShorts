import os
from glob import glob
from pathlib import Path
import subprocess

AUDIO_DIR = "output/audio"
SUB_DIR = "output/subtitles"
OUT_DIR = "output/videos"

os.makedirs(OUT_DIR, exist_ok=True)

for audio_path in sorted(glob(f"{AUDIO_DIR}/*.mp3")):
    stem = Path(audio_path).stem
    srt_path = f"{SUB_DIR}/{stem}.srt"
    out_path = f"{OUT_DIR}/{stem}_preview.mp4"

    if not os.path.exists(srt_path):
        print(f"⚠️ SRT 없음: {srt_path}")
        continue

    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=60",
        "-vf", f"subtitles={srt_path}:force_style='Fontsize=36,PrimaryColour=&H00FFFFFF&,Outline=1,BorderStyle=3,Shadow=1'",
        "-shortest", out_path
    ]
    print(f"🎬 영상 생성: {out_path}")
    subprocess.run(cmd)

print("\n✅ 모든 영상 생성 완료!")