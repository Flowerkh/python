"""
Windows 11 + Python 3.11 + PyCharm
Whisper API (whisper-1) + pyannote.audio (speaker-diarization-3.1)
- HF gated 모델: 모델 페이지에서 Access 수락 필요
- 파이프라인 로딩: 항상 MODEL_ID + cache_dir 방식
- 화자 분리 + Whisper 세그먼트 타임스탬프 매칭
- 세그먼트 정규화 함수로 SDK 버전차(객체/딕셔너리) 호환
- (옵션) SRT 저장
"""

import os
import torch
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI
from pyannote.audio import Pipeline as PnPipeline

# ===== 사용자 설정 =====
AUDIO_FILE = Path(r"C:/Users/cdffe/Desktop/vpn/회의녹음.mp3")
SAVE_SRT = True
MODEL_ID = "pyannote/speaker-diarization-3.1"
CACHE_DIR = Path.home()/".cache"/"hf_diarization_cache" # 다운로드 캐시 위치
# ======================

def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise ValueError(f"{name} 환경변수가 없습니다. PyCharm → Run/Debug Config → Environment variables에 추가하세요.")
    return v

def sec_to_srt(ts: float) -> str:
    if ts is None:
        ts = 0.0
    h = int(ts // 3600)
    ts -= 3600 * h
    m = int(ts // 60)
    ts -= 60 * m
    s = int(ts)
    ms = int(round((ts - s) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


#세그먼트 정규화 (객체/딕셔너리 모두 지원)
def _seg_to_dict(seg) -> Dict[str, Any]:
    if isinstance(seg, dict):
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        text = seg.get("text", "")
    else:
        start = getattr(seg, "start", 0.0)
        end = getattr(seg, "end", 0.0)
        text = getattr(seg, "text", "")
    return {"start": float(start or 0.0), "end": float(end or 0.0), "text": str(text or "").strip()}

#whisper 처리
def transcribe_with_whisper(api_key: str, audio_path: Path) -> List[Dict[str, Any]]:
    if not audio_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {audio_path}")
    print("🎙 Whisper API로 음성 인식 중...")
    client = OpenAI(api_key=api_key)
    with audio_path.open("rb") as f:
        tr = client.audio.transcriptions.create(
            model="whisper-1", #whipser 모델
            file=f,
            response_format="verbose_json" #segments 포함
        )

    segments = getattr(tr, "segments", None)
    if segments is None and isinstance(tr, dict):
        segments = tr.get("segments")

    if not segments:
        raise RuntimeError("Whisper 결과에 segments가 없습니다. 모델/response_format 확인.")

    # ✅ 여기서 모두 dict로 정규화해 반환
    return [_seg_to_dict(seg) for seg in segments]


def load_diarization_pipeline(hf_token: str):
    print("📥 화자 분리 모델 로드 중...")
    print("HF_TOKEN check:", hf_token[:8] + "*" * (len(hf_token) - 8))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ⚠️ 핵심: 첫 인자는 항상 MODEL_ID (로컬 경로 금지), 캐시 위치만 지정
    try:
        diar_pipe = PnPipeline.from_pretrained(
            MODEL_ID,
            use_auth_token=hf_token,
            cache_dir=str(CACHE_DIR)
        )
    except TypeError:
        # 일부 환경에서 인자명이 auth_token인 경우
        diar_pipe = PnPipeline.from_pretrained(
            MODEL_ID,
            auth_token=hf_token,
            cache_dir=str(CACHE_DIR)
        )

    if torch.cuda.is_available():
        diar_pipe.to(torch.device("cuda"))  # 재할당 금지
        print("GPU 사용: CUDA 활성화")
    else:
        print("CPU 사용")
    return diar_pipe


def match_speakers(segments: List[Dict[str, Any]], diarization) -> List[Dict[str, Any]]:
    print("🗣 화자 분리 중...")
    dia = diarization(str(AUDIO_FILE)) #pyannote는 str 경로 허용
    turns = [(float(t.start), float(t.end), spk) for t, _, spk in dia.itertracks(yield_label=True)]

    out = []
    for seg in segments:
        s0 = float(seg["start"])
        s1 = float(seg["end"])
        txt = seg["text"]

        best_spk, best_ov = "Unknown", 0.0
        for t0, t1, spk in turns:
            ov = overlap(s0, s1, t0, t1)
            if ov > best_ov:
                best_ov, best_spk = ov, spk

        out.append({"start": s0, "end": s1, "speaker": best_spk, "text": txt})
    return out


def save_srt(segments: List[Dict[str, Any]], audio_path: Path) -> Path:
    srt_path = audio_path.with_suffix("").with_name(audio_path.stem + "_diarized.srt")
    with srt_path.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{sec_to_srt(seg['start'])} --> {sec_to_srt(seg['end'])}\n")
            f.write(f"{seg['speaker']}: {seg['text']}\n\n")
    return srt_path


def main():
    #환경변수 세팅
    OPENAI_API_KEY = require_env("OPENAI_API_KEY")
    HF_TOKEN = require_env("HF_TOKEN")

    #세그먼트 dict 정규화
    segments = transcribe_with_whisper(OPENAI_API_KEY, AUDIO_FILE)

    #파이프라인 로드 (MODEL_ID + cache_dir) & 매칭
    diar_pipe = load_diarization_pipeline(HF_TOKEN)
    speakered = match_speakers(segments, diar_pipe)

    print("\n화자별 대화 스크립트\n" + "-" * 40)
    for seg in speakered:
        print(f"{seg['speaker']}: {seg['text']}")
    print("-" * 40)
    print("작업 완료")

    #SRT 저장
    if SAVE_SRT:
        srt = save_srt(speakered, AUDIO_FILE)
        print(f"💾 SRT 저장: {srt}")


if __name__ == "__main__":
    # 권장 버전: numpy==1.26.4, pyannote.audio==3.1.1
    main()
