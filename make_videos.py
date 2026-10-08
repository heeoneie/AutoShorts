# make_videos.py
# 타임라인 JSON + 오디오 -> 1.5초 주기 배경 전환 + 키워드 강조 자막이 들어간 쇼츠 mp4
import json
import os
import random
import subprocess
from glob import glob
from pathlib import Path

from config import (AUDIO_DIR, BG_PROVIDER, FPS, OUT_DIR, SCENE_SEC, SUBS_DIR,
                    TIMELINE_DIR, VIDEO_H, VIDEO_W)
from providers import get_provider
from tts_generate import probe_duration

FONT = "Apple SD Gothic Neo"
# ASS 색상은 BGR 순서
COLORS = {"yellow": "&H0000F0FF&", "red": "&H003030FF&"}
WHITE = "&H00FFFFFF&"


# ---------- 자막 (ASS) ----------

def ass_time(t: float) -> str:
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def style_text(text: str, highlights, color_name: str) -> str:
    """강조 키워드만 큰 폰트 + 색상 + 팝 애니메이션."""
    color = COLORS.get(color_name, COLORS["yellow"])
    for kw in sorted(set(highlights or []), key=len, reverse=True):
        if kw and kw in text:
            tag = (r"{\c%s\fs120\fscx60\fscy60\t(0,150,\fscx100\fscy100)}%s"
                   r"{\c%s\fs88\fscx100\fscy100}") % (color, kw, WHITE)
            text = text.replace(kw, tag, 1)
    return text


def build_ass(lines) -> str:
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_W}
PlayResY: {VIDEO_H}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{FONT},88,{WHITE},{WHITE},&H00000000&,&H80000000&,1,0,0,0,100,100,0,0,1,8,2,5,60,60,0,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = [
        f"Dialogue: 0,{ass_time(l['start'])},{ass_time(l['end'])},Default,,0,0,0,,"
        + style_text(l["text"], l.get("highlight"), l.get("highlight_color", "yellow"))
        for l in lines
    ]
    return head + "\n".join(events) + "\n"


# ---------- 배경 장면 ----------

def split_scenes(lines):
    """문장 구간을 ~SCENE_SEC 단위로 쪼개 [(length, keywords)] 반환."""
    scenes = []
    for l in lines:
        length = l["end"] - l["start"]
        n = max(1, round(length / SCENE_SEC))
        for _ in range(n):
            scenes.append((length / n, l.get("bg_keywords", [])))
    return scenes


def run_ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def render_scene(clip, length, out_path):
    vf = (f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
          f"crop={VIDEO_W}:{VIDEO_H},setsar=1,fps={FPS},eq=brightness=-0.08")
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    if clip is None:  # 클립을 못 구했을 때 단색 대체
        run_ffmpeg(["-f", "lavfi", "-i", f"color=c=0x1b1f3b:s={VIDEO_W}x{VIDEO_H}:r={FPS}",
                    "-t", f"{length:.3f}", *enc, out_path])
        return
    dur = probe_duration(str(clip))
    start = random.uniform(0, max(0.0, dur - length))
    run_ffmpeg(["-ss", f"{start:.2f}", "-stream_loop", "-1", "-i", str(clip),
                "-t", f"{length:.3f}", "-vf", vf, *enc, out_path])


def build_background(stem, lines, provider, work_dir):
    scene_files, used = [], set()
    scenes = split_scenes(lines)
    for i, (length, kws) in enumerate(scenes):
        clip = provider.fetch_clip(kws, min_duration=length, exclude=used) if provider else None
        if clip:
            used.add(str(clip))
        out = os.path.join(work_dir, f"scene_{i:03d}.mp4")
        render_scene(clip, length, out)
        scene_files.append(out)
        print(f"  🎞️  장면 {i + 1}/{len(scenes)} ({length:.2f}s) {Path(clip).name if clip else '단색'}")

    list_file = os.path.join(work_dir, "scenes.txt")
    with open(list_file, "w") as f:
        for p in scene_files:
            f.write(f"file '{os.path.abspath(p)}'\n")
    bg = os.path.join(work_dir, "bg.mp4")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", bg])
    return bg


# ---------- 메인 ----------

def get_provider_safe():
    try:
        return get_provider(BG_PROVIDER)
    except Exception as e:
        print(f"[경고] 배경 provider 사용 불가 ({e}) → 단색 배경으로 진행")
        return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SUBS_DIR, exist_ok=True)
    files = sorted(glob(f"{TIMELINE_DIR}/*.json"))
    if not files:
        print("⚠️ 타임라인 없음. 먼저 tts_generate.py를 실행하세요.")
        return

    provider = get_provider_safe()
    for tl_path in files:
        stem = Path(tl_path).stem
        audio = f"{AUDIO_DIR}/{stem}.mp3"
        if not os.path.exists(audio):
            print(f"⚠️ 오디오 없음: {audio}")
            continue
        with open(tl_path, encoding="utf-8") as f:
            tl = json.load(f)

        print(f"🎬 {stem} ({tl['duration']:.1f}초)")
        work_dir = os.path.join(OUT_DIR, f"_work_{stem}")
        os.makedirs(work_dir, exist_ok=True)

        bg = build_background(stem, tl["lines"], provider, work_dir)

        ass_path = f"{SUBS_DIR}/{stem}.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(build_ass(tl["lines"]))

        out = f"{OUT_DIR}/{stem}.mp4"
        run_ffmpeg(["-i", bg, "-i", audio, "-vf", f"ass={ass_path}",
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", out])
        print(f"✅ 완료: {out}")

    print("\n✅ 모든 영상 생성 완료!")


if __name__ == "__main__":
    main()
