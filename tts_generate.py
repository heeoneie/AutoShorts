# tts_generate.py
import os
import json
from glob import glob
from pathlib import Path

# gTTS: 설치 필요 -> pip install gTTS
from gtts import gTTS

# -------------------------------
# 설정값
# -------------------------------
SCRIPTS_DIR = "output/scripts"
AUDIO_DIR = "output/audio"
SUBS_DIR = "output/subtitles"

LANG = "ko"          # gTTS 언어 (한국어)
VOICE_SLOW = False   # gTTS 속도(느리게 = True)
CHARS_PER_SEC = 9.0  # 자막 타이밍 추정 기준(한글 대략 8~10 추천)

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(SUBS_DIR, exist_ok=True)

def estimate_duration(text: str, cps: float = CHARS_PER_SEC, min_sec: float = 1.2, max_sec: float = 5.0):
    """문자 수로 길이 추정(자막 타이밍용)."""
    secs = max(min_sec, min(len(text) / cps, max_sec))
    return round(secs, 2)

def flatten_script_for_narration(script_list):
    """
    JSON의 script 배열을 나레이션 한 줄씩으로 펼친다.
    - opening -> rank순 content -> closing
    """
    opening = [s["text"] for s in script_list if s.get("type") == "opening" or s.get("type") == "hook"]
    content = sorted(
        [s for s in script_list if s.get("type") == "content" or s.get("type") == "body"],
        key=lambda x: x.get("rank", 999)
    )
    closing = [s["text"] for s in script_list if s.get("type") == "closing"]

    lines = []
    lines.extend(opening)
    lines.extend([s["text"] for s in content])
    lines.extend(closing)
    # 문장 사이 약간의 쉼표/구두점을 추가해 발화 자연스럽게
    return [ln.strip() for ln in lines if ln and ln.strip()]

def to_srt_time(t):
    """초(float) -> SRT 타임코드 (HH:MM:SS,mmm)"""
    hrs = int(t // 3600)
    mins = int((t % 3600) // 60)
    secs = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

def build_srt(lines):
    """
    lines: 자막 한 줄씩 배열
    길이 추정으로 구간을 만든 뒤 SRT 문자열 반환
    """
    srt_chunks = []
    cur = 0.0
    idx = 1
    for ln in lines:
        dur = estimate_duration(ln)
        start = cur
        end = cur + dur
        srt_chunks.append(f"{idx}\n{to_srt_time(start)} --> {to_srt_time(end)}\n{ln}\n")
        cur = end + 0.15  # 자막 사이 0.15초 여유
        idx += 1
    return "\n".join(srt_chunks)

def make_tts(text, outpath):
    """gTTS로 음성 합성."""
    tts = gTTS(text=text, lang=LANG, slow=VOICE_SLOW)
    tts.save(outpath)

def process_script_file(fpath):
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data.get("title", "untitled")
    script_list = data.get("script", [])
    if not script_list:
        print(f"⚠️  스크립트 없음: {fpath}")
        return

    # 1) 나레이션용 문장 배열
    lines = flatten_script_for_narration(script_list)
    narration_text = " ".join(lines)  # 한 트랙 나레이션(문장 사이 공백)

    stem = Path(fpath).stem  # 파일명(확장자 제외)
    audio_out = os.path.join(AUDIO_DIR, f"{stem}.mp3")
    srt_out = os.path.join(SUBS_DIR, f"{stem}.srt")

    # 2) 음성 생성
    print(f"🎙️  TTS 생성: {audio_out}")
    make_tts(narration_text, audio_out)

    # 3) SRT 생성
    print(f"🧾  SRT 생성: {srt_out}")
    srt_text = build_srt(lines)
    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(srt_text)

    print(f"✅ 완료: {stem}  (타이틀: {title})")

def main():
    files = sorted(glob(os.path.join(SCRIPTS_DIR, "*.json")))
    if not files:
        print(f"⚠️  {SCRIPTS_DIR} 안에 JSON 대본 파일이 없습니다. (먼저 main.py를 실행해 대본을 생성하세요)")
        return

    print(f"총 {len(files)}개 대본 처리 시작…")
    for fpath in files:
        process_script_file(fpath)

    print("\n--- ✅ 모든 TTS & SRT 생성 완료 ---")
    print("\n다음 단계 예시(FFmpeg로 미리보기 영상 1개 만들기):")
    print("ffmpeg -y -i output/audio/01_script.mp3 -f lavfi -i color=c=black:s=1080x1920:d=60 \\")
    print("-vf \"subtitles=output/subtitles/01_script.srt:force_style='Fontsize=36,PrimaryColour=&H00FFFFFF&'\" \\")
    print("-shortest output/videos/01_script_preview.mp4")
    print("\nTip) 실제 템플릿/이미지/영상 위에 자막 얹는 건 CapCut 템플릿이나 AE, 또는 ffmpeg 필터체인으로 확장 가능!")

if __name__ == "__main__":
    main()