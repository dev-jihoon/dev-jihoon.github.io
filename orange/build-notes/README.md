# Orange3 웹 빌드 기록

브라우저(WebAssembly)에서 진짜 Orange3 3.41을 돌리기 위해 쓴 스크립트와 패치 모음.

구성: Pyodide 0.29.3(소스 빌드) + Qt 6.10.2 wasm(정적, 스레드 없음) + PyQt6 6.10.2(정적 링크)
툴체인: conda-forge emscripten 4.0.9 / clang 21 / binaryen 121
PyQt6를 Pyodide에 정적으로 넣는 방법은 github.com/JarrettSJohnson/pyodide-with-pyqt6 (GPL)을 참고해 이 환경에 맞게 고쳤다.

순서: build_qt.sh → (Pyodide CPython 빌드) → build_pyqt.sh → build_link.sh → build_orange_ext.sh → getreg.py(위젯 목록 미리 만들기) → make_deploy.sh

## 고친 것
- patches/qtbase-6.10.2-orange-web.patch
  - 일반 창을 전체화면이 아니라 떠 있는 창으로 열기 (ShowIsFullScreen=false)
  - 중첩 이벤트 루프(dialog.exec(), menu.exec())에서 앱을 죽이지 않고 바로 반환
  - QDrag::exec()는 바로 IgnoreAction 반환
  - 터치 기기에서는 창 포커스용 숨은 요소를 contenteditable로 만들지 않음 (아이패드 키보드가 계속 뜨던 문제)
  - 두 번 탭 인정 거리 30px, 더블클릭 간격 500ms
  - 터치 기기에서 목록·표(QAbstractItemView)에 포커스가 가도 키보드를 띄우지 않음
  - 숨겨 둔 위젯 창이 다른 창 변화 때문에 저절로 다시 나타나지 않게, 창을 보일 때 활성화
  - 더블클릭 판정에 두 번째 누름이 첫 누름 근처인지도 확인 (터치에서는 서로 다른 곳을 빨리 두 번 탭해도 더블클릭이 되던 문제)
  - 브라우저가 손가락 뗌을 다른 요소로 보내서 남은 터치 점을 모든 창에서 정리 (남은 점 위치로 탭이 잘못 가는 것 방지)
  - 누른 위치를 offsetX/offsetY 대신 clientX/clientY와 요소 위치로 계산 (WebKit은 그림자 DOM·포인터 캡처에서 offsetX 기준이 달라짐)
- patches/pyqt6-qaction-setmenu.txt: QAction.setMenu 함수 타입 불일치 수정
- patches/anyqt-fixes.patch: ctypes로 Qt 공유 라이브러리를 못 찾을 때 대체 구현
- web/boot.py: 스레드 대체(QThread/QThreadPool/ThreadPoolExecutor를 동기 실행), 없는 Qt 모듈 스텁, 한글 폰트, exec() 없이 캔버스 시작
- web/webpatches.py: 퀵메뉴·위젯 끌어놓기·파일 열기/저장을 비동기(브라우저 업로드/다운로드)로 바꿈.
  확인창(저장할까요?, 연결 편집, 워크플로 정보, 설정)도 exec() 대신 open()+finished로 이어서 실행
- patches/orange-domaineditor-touch.patch: File 위젯 Type/Role 콤보에서 마우스 hover 없이 탭한 항목으로 값 바꾸기 (전에는 None이 들어가 Apply가 아무 일도 안 함)
- patches/orange-widgets-dialogs.patch: Feature Constructor, Edit Domain(값 합치기), Color(색 고르기) 대화상자를 같은 방식으로 수정
- Orange의 Cython 확장은 numpy 2.2 헤더로 다시 cythonize 후 emcc로 side module 빌드

## 로딩 시간 줄인 것 (make_deploy.sh)
- 표준 라이브러리, 패키지, 오렌지를 전부 .pyc로 미리 컴파일 (브라우저에서 컴파일 안 함)
- 위젯 목록(widget-registry.pck)을 미리 만들어 두고 --no-discovery로 시작 (위젯 모듈 100여 개를 시작할 때 import 안 함)
- matplotlib 빼고(patches/orangewidget-matplotlib-optional.patch), networkx는 화면이 뜬 뒤 백그라운드로 로드
- 파이썬 로딩과 동시에 오렌지/폰트/위젯 목록 다운로드 시작
- 모든 파일을 빌드별로 Cache Storage에 저장해서 두 번째 접속부터는 네트워크를 거의 안 씀

## 터치 기기 (webpatches.apply_touch_tweaks)
- 목록·표를 손가락으로 끌면 스크롤. 누름은 손을 뗄 때까지 미뤘다가 움직이지 않았으면 그때 클릭으로 전달 (스크롤하다 행이 선택되지 않게)
- 콤보 목록이 열린 직후 0.4초 동안의 탭은 무시 (두 번 탭의 두 번째 탭이 바로 항목을 골라 버리지 않게)
- 길게 누르기(0.55초) = 오른쪽 클릭 → 위젯/연결의 메뉴에서 Remove 등
- 글자 입력칸은 직접 탭할 때만 포커스 (창이 열릴 때 키보드가 뜨지 않게)
- 스핀박스 화살표를 탭하면 값만 바뀌고 키보드는 안 뜸, 숫자 부분을 탭하면 입력
- 메인 창을 맨 아래로 고정해서 캔버스를 탭해도 위젯 창이 뒤로 숨지 않음 (모든 기기)
- 터치 기기에서는 파일 열기/저장을 작은 상자의 진짜 버튼으로 (브라우저가 탭 안에서만 파일 창·다운로드를 허락)
- 주소 뒤에 ?touchdebug 를 붙이면 손가락 위치(파랑)와 Qt가 받은 위치(빨강/초록)를 점으로 표시
- 사파리 두 번 탭/핀치 확대 막기, 키보드 때문에 밀린 페이지 스크롤 되돌리기 (web/orange.html)
- 확인용 스크립트: tests/touch3.py, tests/touch4.py (크롬 터치 에뮬레이션, 35개 항목)
