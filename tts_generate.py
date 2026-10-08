# tts_generate.py
# 대본 JSON -> 문장별 TTS -> 실제 길이 기반 타임라인(JSON) + 합쳐진 mp3
import json
import os
import subprocess
from glob import glob
from pathlib import Path

from gtts import gTTS

from config import AUDIO_DIR, SCRIPTS_DIR, TIMELINE_DIR, TTS_TEMPO

LANG = "ko"
PAD_SEC = 0.08  # 문장 끝 여유

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TIMELINE_DIR, exist_ok=True)


def flatten_script(script_list):
    """hook -> body(rank순) -> closing 순서로 문장 dict 리스트 반환."""
    hook = [s for s in script_list if s.get("type") in ("hook", "opening")]
    body = sorted(
        [s for s in script_list if s.get("type") in ("body", "content")],
        key=lambda x: x.get("rank", 999),
    )
    closing = [s for s in script_list if s.get("type") == "closing"]
    return [s for s in hook + body + closing if (s.get("text") or "").strip()]


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def synth_sentence(text: str, wav_path: str) -> float:
    """gTTS -> 속도 조절 + 패딩한 wav. 실제 길이(초) 반환."""
    tmp_mp3 = wav_path + ".tmp.mp3"
    gTTS(text=text, lang=LANG).save(tmp_mp3)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_mp3,
         "-af", f"atempo={TTS_TEMPO},apad=pad_dur={PAD_SEC}",
         "-ar", "44100", "-ac", "1", wav_path],
        check=True,
    )
    os.remove(tmp_mp3)
    return probe_duration(wav_path)


def concat_wavs(wavs, out_mp3):
    list_file = out_mp3 + ".list.txt"
    with open(list_file, "w") as f:
        for w in wavs:
            f.write(f"file '{os.path.abspath(w)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", list_file, "-c:a", "libmp3lame", "-q:a", "3", out_mp3],
        check=True,
    )
    os.remove(list_file)


def process_script_file(fpath):
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    sentences = flatten_script(data.get("script", []))
    if not sentences:
        print(f"⚠️  스크립트 없음: {fpath}")
        return

    stem = Path(fpath).stem
    wav_dir = os.path.join(AUDIO_DIR, stem)
    os.makedirs(wav_dir, exist_ok=True)

    timeline, wavs, cur = [], [], 0.0
    for i, s in enumerate(sentences, start=1):
        wav = os.path.join(wav_dir, f"{i:02d}.wav")
        print(f"🎙️  [{i}/{len(sentences)}] {s['text']}")
        dur = synth_sentence(s["text"].strip(), wav)
        timeline.append({
            "type": s.get("type"),
            "text": s["text"].strip(),
            "highlight": s.get("highlight", []),
            "highlight_color": s.get("highlight_color", "yellow"),
            "bg_keywords": s.get("bg_keywords", []),
            "start": round(cur, 3),
            "end": round(cur + dur, 3),
        })
        wavs.append(wav)
        cur += dur

    audio_out = os.path.join(AUDIO_DIR, f"{stem}.mp3")
    concat_wavs(wavs, audio_out)

    with open(os.path.join(TIMELINE_DIR, f"{stem}.json"), "w", encoding="utf-8") as f:
        json.dump({"title": data.get("title", "untitled"), "duration": round(cur, 3),
                   "lines": timeline}, f, ensure_ascii=False, indent=2)
    print(f"✅ 완료: {stem}  ({cur:.1f}초)")


def main():
    files = sorted(glob(os.path.join(SCRIPTS_DIR, "*.json")))
    if not files:
        print(f"⚠️  {SCRIPTS_DIR} 안에 JSON 대본 파일이 없습니다. "
              "script_prompt.md로 생성한 JSON을 넣어주세요.")
        return
    for fpath in files:
        process_script_file(fpath)
    print("\n--- ✅ TTS & 타임라인 생성 완료 → make_videos.py 실행 ---")


if __name__ == "__main__":
    main()
