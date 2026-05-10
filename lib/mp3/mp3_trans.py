import os
import shutil

# pydub import 전에 ffmpeg 경로를 환경변수에 등록 (PATH 미적용 대비)
_FFMPEG_BIN = r"C:\Users\cdffe\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
if not shutil.which("ffmpeg") and os.path.isdir(_FFMPEG_BIN):
    os.environ["PATH"] = _FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")

from pydub import AudioSegment

def wav_to_mp3(input_path, output_path=None, bitrate="192k"):
    """
    WAV 파일을 MP3 파일로 변환합니다.
    :param input_path: 원본 WAV 파일 경로
    :param output_path: 저장할 MP3 파일 경로 (None이면 같은 위치에 .mp3로 저장)
    :param bitrate: MP3 비트레이트 (예: "128k", "192k", "320k")
    """
    try:
        if not os.path.exists(input_path):
            print(f"파일을 찾을 수 없습니다: {input_path}")
            return

        if output_path is None:
            base = os.path.splitext(input_path)[0]
            output_path = base + ".mp3"

        audio = AudioSegment.from_wav(input_path)
        audio.export(output_path, format="mp3", bitrate=bitrate)

        original_size = os.path.getsize(input_path) / 1024
        converted_size = os.path.getsize(output_path) / 1024

        print(f"변환 완료!")
        print(f"원본 WAV 용량: {original_size:.2f} KB")
        print(f"변환된 MP3 용량: {converted_size:.2f} KB")
        print(f"줄어든 비율: {((original_size - converted_size) / original_size) * 100:.1f}%")
        print(f"저장 경로: {output_path}")

    except Exception as e:
        print(f"에러 발생: {e}")


# 사용 예시
input_wav = "./Let's Go - JAXSON GAMBLE.wav"   # 원본 WAV 파일명
output_mp3 = "./Let's Go - JAXSON GAMBLE.mp3"  # 결과 MP3 파일명

wav_to_mp3(input_wav, output_mp3, bitrate="192k")
