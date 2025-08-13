from huggingface_hub import hf_hub_download
import os
t = os.getenv("HF_TOKEN")
# segmentation-3.0의 아무 파일이나 받아보기 (접근되면 바로 다운로드됨)
p = hf_hub_download("pyannote/segmentation-3.0", filename="config.yaml", token=t)
print("OK:", p)