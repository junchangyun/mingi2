# Bybit Trade Journal Web

## 1) 설치
```bash
cd bybit_web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) OpenAI 키 설정 (서버 고정값)
```bash
export OPENAI_API_KEY="YOUR_INTERNAL_OPENAI_KEY"
```

## 3) 실행
```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속 후, Bybit API Key/Secret만 입력합니다.

## 보안 규칙
- OpenAI 키는 화면에서 입력받지 않습니다.
- Bybit 키는 `/v5/user/query-api`로 권한을 검사하며, 출금 권한이 감지되면 시작을 차단합니다.
- 실제 운영 전, Bybit에서 API 권한을 `읽기/거래 전용`으로 생성하세요.
