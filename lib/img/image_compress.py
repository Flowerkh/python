from PIL import Image
import os

def compress_image(input_path, output_path, quality=85):
    """
    이미지 해상도는 유지하면서 압축률을 조절해 용량을 줄입니다.
    :param input_path: 원본 이미지 경로
    :param output_path: 저장할 이미지 경로
    :param quality: 압축 품질 (1-100, 수치가 낮을수록 용량이 작아짐)
    """
    try:
        # 이미지 열기
        with Image.open(input_path) as img:
            # RGB 모드로 변환 (PNG나 RGBA 파일을 JPEG로 저장할 때 필요)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # 이미지 저장 (optimize=True는 추가적인 용량 최적화를 수행함)
            img.save(output_path, "JPEG", optimize=True, quality=quality)
            img.thumbnail((1024, 1024))

            original_size = os.path.getsize(input_path) / 1024
            compressed_size = os.path.getsize(output_path) / 1024

            print(f"압축 완료!")
            print(f"원본 용량: {original_size:.2f} KB")
            print(f"압축 후 용량: {compressed_size:.2f} KB")
            print(f"줄어든 비율: {((original_size - compressed_size) / original_size) * 100:.1f}%")

    except Exception as e:
        print(f"에러 발생: {e}")

# 사용 예시
input_img = "./mypage.png"  # 원본 파일명
output_img = "mypage_.png"  # 결과 파일명

compress_image(input_img, output_img, quality=60)  # 품질을 60으로 설정