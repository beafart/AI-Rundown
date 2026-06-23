# 설정 가이드

## 1. `.env` 만들기

프로젝트 루트에서 `.env.example`을 복사해 `.env`를 만들고 아래 값을 채우세요.

```text
NAVER_EMAIL=your_naver_id@naver.com
NAVER_APP_PASSWORD=네이버_애플리케이션_비밀번호
NAVER_FOLDER=AI rundown
APP_API_TOKEN=원하는_토큰
FETCH_DAYS=14
FETCH_LIMIT=50
MAX_ARTICLES_PER_SYNC=1
MAX_SENTENCES_PER_ARTICLE=40
```

`APP_API_TOKEN`은 Android 앱에서 노트북 백엔드에 직접 붙을 때만 씁니다.

## 2. Supabase 설정

Supabase 프로젝트를 만든 뒤 SQL Editor에서 아래 파일 내용을 실행하세요.

```text
supabase/migrations/0001_ai_rundown_schema.sql
supabase/migrations/0002_sentence_summary_fields.sql
```

이미 `0001`을 실행했다면 `0002_sentence_summary_fields.sql`만 추가로 실행하면 됩니다.

그 다음 `.env`에 아래 값을 채웁니다. `SERVICE_ROLE_KEY`는 앱에 넣으면 안 되고 노트북 `.env`에만 둡니다.

```text
STORAGE_BACKEND=supabase
SUPABASE_URL=https://프로젝트-ref.supabase.co
SUPABASE_ANON_KEY=Supabase anon 또는 publishable key
SUPABASE_SERVICE_ROLE_KEY=Supabase service_role key
```

앱에는 `SUPABASE_URL`과 `SUPABASE_ANON_KEY`만 입력합니다.

## 3. 백엔드/worker 실행

노트북에서 백엔드를 계속 켜두려면:

```powershell
python backend\app.py
```

놓친 메일을 따라잡고 종료하려면:

```powershell
python backend\app.py --sync-once
```

현재 설정은 `FETCH_DAYS=14`라서 실행할 때마다 최근 14일치 `AI rundown` 폴더를 훑고, Supabase에 이미 있는 메일 UID는 건너뜁니다. 그래서 7시에 노트북이 꺼져 있어도 다음에 켜졌을 때 밀린 메일을 처리합니다.

처음 테스트할 때는 `MAX_ARTICLES_PER_SYNC=1`로 두는 것을 추천합니다. 안정적으로 돌아가는 것을 확인한 뒤 `3`, `5`처럼 늘리면 됩니다.

청크 해석 형식이 바뀐 뒤 기존 기사는 새 형식으로 자동 변환되지 않습니다. 새 형식으로 보려면 노트북 백엔드가 켜진 상태에서 앱의 `Re-analyze`를 누르거나, Supabase의 해당 기사 상태를 `failed`로 바꾼 뒤 `--sync-once`를 다시 실행하세요.

처음 테스트할 때 실제 메일 대신 샘플 기사를 만들 수 있습니다.

```powershell
python backend\app.py --seed-sample
```

## 4. 노트북 IP 확인

Supabase를 앱에 설정하면 집 밖에서는 노트북 IP가 필요 없습니다. 다만 `Sync`, `Sample`, `Re-analyze` 같은 분석 작업은 노트북 백엔드가 켜져 있을 때만 됩니다.

같은 와이파이에서 노트북 백엔드에 직접 붙고 싶으면 `ipconfig`로 IPv4 주소를 확인하세요.

```powershell
ipconfig
```

예를 들어 IPv4 주소가 `192.168.0.12`라면 앱의 Backend URL은 아래처럼 넣습니다.

```text
http://192.168.0.12:8787
```

## 5. APK 받기

GitHub에 푸시한 뒤 Actions 탭에서 `Build Android APK` 워크플로를 실행하거나 main 브랜치에 푸시하면 APK artifact가 생깁니다.

앱을 새로 설치해도 Supabase URL과 anon key가 자동으로 들어가게 하려면 GitHub 저장소에서 아래 Secrets를 추가하세요.

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

추가할 이름:

```text
APP_SUPABASE_URL
APP_SUPABASE_ANON_KEY
```

`APP_SUPABASE_URL`에는 `https://psywgcagllmkffwaflkq.supabase.co`처럼 `/rest/v1` 없는 URL을 넣고, `APP_SUPABASE_ANON_KEY`에는 Supabase publishable key를 넣습니다. `service_role` 키는 절대 넣지 마세요.

다운로드할 artifact 이름:

```text
ai-rundown-reader-debug-apk
```

압축을 풀고 `app-debug.apk`를 폰에서 설치하면 됩니다.

## 6. 핸드폰 설치 순서

1. GitHub 저장소의 `Actions` 탭을 엽니다.
2. 최신 `Build Android APK` 실행 결과를 엽니다.
3. 아래쪽 `Artifacts`에서 `ai-rundown-reader-debug-apk`를 다운로드합니다.
4. 압축을 풀어 `app-debug.apk`를 폰으로 옮기거나 폰에서 직접 다운로드합니다.
5. Android가 "알 수 없는 앱 설치"를 묻는 경우 현재 브라우저/파일 앱에 설치 권한을 허용합니다.
6. `app-debug.apk`를 실행해 설치합니다.
7. 앱을 열고 Supabase URL과 anon key를 입력한 뒤 저장합니다.

## 7. 앱 사용 순서

1. 노트북에서 `python backend\app.py --sync-once`를 실행해 메일을 분석하고 Supabase에 올립니다.
2. 앱에서 Supabase URL과 anon key를 저장합니다.
3. 앱에서 `Refresh`를 눌러 Supabase의 기사 목록을 불러옵니다.
4. 기사 문장을 먼저 읽고 `Reveal`로 청크 해석을 확인합니다.
5. 단어는 `Save Word`로 저장하고 `Share TSV` 또는 `Copy TSV`로 Anki에 넣습니다.
