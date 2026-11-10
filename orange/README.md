# Orange 웹 (아이패드용)

진짜 Orange3 3.41을 웹브라우저 안에서 돌리는 사이트입니다. 흉내 낸 프로그램이 아니라 오렌지 원본 코드가 그대로 돌아갑니다(파이썬과 Qt를 WebAssembly로 빌드). 서버가 필요 없어서 GitHub Pages 같은 정적 호스팅에 파일만 올리면 됩니다.

주소: https://dev-jihoon.github.io/orange/

## 다른 곳에 올리기 (GitHub Pages)

1. GitHub에서 새 저장소를 만듭니다. 예: `orange` (Public)
2. 이 폴더 안의 파일을 **전부** 저장소 맨 위에 올립니다. 숨김 파일인 `.nojekyll`도 꼭 같이 올려야 합니다.
   - 파일이 모두 15MB 이하라서 웹 업로드(Add file → Upload files)로도 올라갑니다.
3. Settings → Pages → Branch를 `main`, 폴더를 `/ (root)`로 정하고 저장합니다.
4. 1~2분 뒤 `https://<아이디>.github.io/orange/` 로 접속합니다.

## 쓰는 법 (아이패드 사파리)

- 처음 접속하면 약 65MB를 받아서 1~2분 걸립니다. 그다음부터는 브라우저 캐시 덕분에 빨라집니다.
- 가로 화면을 추천합니다. 공유 → "홈 화면에 추가"를 하면 주소창 없이 넓게 쓸 수 있습니다.
- 위젯 추가: 왼쪽 목록에서 아이콘을 **탭**하거나 캔버스로 **끌어다** 놓습니다.
- 연결: 위젯의 오른쪽 가장자리에서 다른 위젯까지 끌어서 놓습니다. 빈 곳에 놓으면 연결할 위젯 목록이 뜹니다.
- 위젯 열기: 위젯을 **두 번 탭**합니다.
- 위젯·연결 지우기: 위젯이나 연결선을 **길게 누르면** 메뉴가 뜹니다 → Remove. 또는 위젯을 탭해서 고른 뒤 Edit 메뉴 → Remove.
- File 위젯에서 Type/Role 바꾸기: 칸을 탭하면 목록이 뜨고, 원하는 항목을 탭한 뒤 Apply.
- 목록·표는 손가락으로 끌어서 스크롤합니다.
- 탭한 곳과 다른 데가 눌리는 것 같으면 주소 끝에 `?touchdebug`를 붙여 열어 보세요. 파란 원(손가락)과 빨간 점(오렌지가 받은 위치)이 어긋나는지 보입니다.
- 내 데이터 열기: File 위젯 → `...` 버튼 → Choose File → 아이패드 파일 앱에서 고르기 (csv, xlsx, tab 등)
- 예제 데이터: File 위젯 → "Browse documentation datasets" (iris, titanic, heart_disease, housing, zoo 등)
- 작업 저장: File 메뉴 → Save → `.ows` 파일이 다운로드됩니다. 데스크톱 오렌지에서도 그대로 열립니다. 다시 열 때는 File → Open.
- 저장하지 않은 작업이 있을 때 New/Open을 누르거나 탭을 닫으려 하면 저장할지 물어봅니다.
- 블루투스 마우스나 트랙패드가 있으면 훨씬 편합니다.

## 안 되는 것

- (t-SNE도 이제 됩니다), Python Script, SQL Table, Datasets(온라인 데이터 목록) 위젯
- 인터넷 주소(URL)로 데이터 불러오기, 도움말(Help) 문서
- 계산은 백그라운드가 아니라 화면 스레드에서 돌아서, 큰 데이터로 학습할 때는 잠깐 멈춘 것처럼 보일 수 있습니다.
- 크롬(컴퓨터)과 터치 에뮬레이션으로 확인했고, 실제 아이패드 사파리에서는 아직 확인 전입니다.

## 라이선스

Orange3, PyQt6는 GPL-3.0, Qt는 LGPL-3.0/GPL, Pyodide는 MPL-2.0, 나눔고딕은 OFL-1.1입니다. 수정한 내용과 빌드 스크립트는 `build-notes/` 폴더에 있습니다.

## 화면
- 윈도우 11에서 Orange를 연 것과 같은 모양으로 보이게 했습니다 (버튼, 콤보박스, 메뉴, 창 제목 줄).
- 저장(Save Data, Save Workflow Image as SVG 등)을 하면 파일이 다운로드됩니다.

글꼴: Selawik (Microsoft, SIL OFL 1.1), 아이콘: Fluent UI System Icons (Microsoft, MIT). 라이선스 파일은 winfonts.tar 안에 있습니다.
