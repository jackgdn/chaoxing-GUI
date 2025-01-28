python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
Clear-Host
python main.py
