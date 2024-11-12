@echo off
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
cls
python main.py