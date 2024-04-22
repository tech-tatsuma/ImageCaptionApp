#!/bin/bash

# FastAPI サーバーをバックグラウンドで実行
pipenv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --log-level debug

# another_client.py スクリプトをバックグラウンドで実行
pipenv run python app/python_client/python_client.py