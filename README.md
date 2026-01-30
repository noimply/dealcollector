# 글모아 프로젝트

커뮤니티 핫딜 게시판 크롤러

## 설정

1. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

2. 패키지 설치
```bash
pip install -r requirements.txt
playwright install chromium
```

3. `.env` 파일 생성 및 설정
```env
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
```

## 실행
```bash
python crawlers/main.py
```

## GitHub Actions

2시간마다 자동 실행됩니다.