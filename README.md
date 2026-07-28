# 네이버 블로그 통합 자동화 도구 (Streamlit)

네이버 오픈 API(공식) + GPT-4o 글쓰기 보조 + Pillow 이미지 처리를 하나로 묶은
1인 블로그 운영 보조 웹 도구입니다. 파일 하나(`streamlit_app.py`)로 동작합니다.

## 폴더 구조

```
.
├── streamlit_app.py               # 앱 전체 (이 파일 하나면 실행 가능)
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml.example       # 키 형식 예시 (실제 키 없음)
```

## 로컬 실행 방법 (단계별)

### 1) 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

### 2) 키 설정

`.streamlit/secrets.toml.example`을 복사해서 `.streamlit/secrets.toml`로 저장한 뒤,
실제 키 값을 채워넣습니다.

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`.streamlit/secrets.toml` 내용 예:
```toml
NAVER_CLIENT_ID = "실제_Client_ID"
NAVER_CLIENT_SECRET = "실제_Client_Secret"
OPENAI_API_KEY = "sk-실제키"
```

- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`: [네이버 개발자센터](https://developers.naver.com)에서
  애플리케이션 등록 후 "블로그" API 사용 신청하면 발급받을 수 있습니다.
- `OPENAI_API_KEY`: [OpenAI Platform](https://platform.openai.com)에서 발급받습니다.

### 3) 실행

```bash
streamlit run streamlit_app.py
```

터미널에 아래처럼 뜨면 정상입니다:
```
Local URL: http://localhost:8501
```
자동으로 브라우저가 안 열리면 이 주소를 직접 입력해서 접속하세요.

### 4) 화면이 하얗게만 뜨는 경우

앱 상단의 **"⚙️ 설정 상태 확인"** 박스를 펼쳐보세요. 어떤 키가 비어있는지,
어떤 패키지가 문제인지 화면에서 바로 보여줍니다. 터미널에 남은 에러 메시지도 함께 확인하세요.

## 깃허브에 올릴 때 주의사항

- `.streamlit/secrets.toml`(실제 키가 든 파일)은 `.gitignore`에 포함되어 있어 자동으로 제외됩니다.
  실수로 이 파일이 깃허브에 올라간 적이 있다면, 키를 즉시 재발급하는 걸 추천합니다.
- 커밋 전에 `git status`로 `.streamlit/secrets.toml`이 목록에 없는지 한 번 확인하는 습관을 들이면 안전합니다.

## Streamlit Cloud에 배포하는 경우

1. 이 저장소를 깃허브에 올립니다 (`.streamlit/secrets.toml`은 올라가지 않음).
2. [share.streamlit.io](https://share.streamlit.io)에서 저장소 연결 후 배포.
3. 앱 설정의 **Secrets** 메뉴에 `.streamlit/secrets.toml.example`과 같은 형식으로
   실제 키 값을 입력합니다.

## 이 도구가 하지 않는 것

- 브라우저 자동화나 로그인 위장을 사용하지 않습니다. 네이버 공식 오픈 API(OAuth)만 사용합니다.
- 초안은 항상 사람이 검토/수정 후 직접 "게시하기" 버튼을 눌러야 게시됩니다.
