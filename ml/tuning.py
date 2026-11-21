# -*- coding: utf-8 -*-
"""CLOVA Studio 튜닝 학습 생성 (5차시 Lab 6 방식). 키는 .env 에서 읽음.
실행: python3 tuning.py   → 응답의 id 가 튜닝 작업 ID (TUNED_TASK_ID)
"""
import os
from pathlib import Path
import requests

for line in (Path(__file__).resolve().parent.parent / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ["CLOVASTUDIO_API_KEY"]
headers = {"Authorization": f"Bearer {API_KEY}", "X-NCP-CLOVASTUDIO-REQUEST-ID": "1"}
request_data = {
    "name": "minwon_cls_v1",
    "model": "HCX-003",
    "tuningType": "PEFT",
    "taskType": "GENERATION",
    "trainEpochs": "8",
    "learningRate": "1e-4",
    "trainingDatasetBucket": os.environ.get("TUNING_BUCKET", "minwon-1120"),
    "trainingDatasetFilePath": "train.csv",
    "trainingDatasetAccessKey": os.environ["NCP_ACCESS_KEY"],
    "trainingDatasetSecretKey": os.environ["NCP_SECRET_KEY"],
}
res = requests.post("https://clovastudio.stream.ntruss.com/tuning/v2/tasks", json=request_data, headers=headers).json()
print(res.get("result", res))
