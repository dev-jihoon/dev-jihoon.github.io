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
- patches/pyqt6-qaction-setmenu.txt: QAction.setMenu 함수 타입 불일치 수정
- patches/anyqt-fixes.patch: ctypes로 Qt 공유 라이브러리를 못 찾을 때 대체 구현
- web/boot.py: 스레드 대체(QThread/QThreadPool/ThreadPoolExecutor를 동기 실행), 없는 Qt 모듈 스텁, 한글 폰트, exec() 없이 캔버스 시작
- web/webpatches.py: 퀵메뉴·위젯 끌어놓기·파일 열기/저장을 비동기(브라우저 업로드/다운로드)로 바꿈.
  확인창(저장할까요?, 연결 편집, 워크플로 정보, 설정)도 exec() 대신 open()+finished로 이어서 실행
- patches/orange-widgets-dialogs.patch: Feature Constructor, Edit Domain(값 합치기), Color(색 고르기) 대화상자를 같은 방식으로 수정
- Orange의 Cython 확장은 numpy 2.2 헤더로 다시 cythonize 후 emcc로 side module 빌드

## 로딩 시간 줄인 것 (make_deploy.sh)
- 표준 라이브러리, 패키지, 오렌지를 전부 .pyc로 미리 컴파일 (브라우저에서 컴파일 안 함)
- 위젯 목록(widget-registry.pck)을 미리 만들어 두고 --no-discovery로 시작 (위젯 모듈 100여 개를 시작할 때 import 안 함)
- matplotlib 빼고(patches/orangewidget-matplotlib-optional.patch), networkx는 화면이 뜬 뒤 백그라운드로 로드
- 파이썬 로딩과 동시에 오렌지/폰트/위젯 목록 다운로드 시작
- 모든 파일을 빌드별로 Cache Storage에 저장해서 두 번째 접속부터는 네트워크를 거의 안 씀

## 터치 기기 (webpatches.apply_touch_tweaks)
- 목록·표·설정 패널을 손가락으로 끌어서 스크롤 (QScroller)
- 글자 입력칸은 직접 탭할 때만 포커스 (창이 열릴 때 키보드가 뜨지 않게)
- 스핀박스 화살표를 탭하면 값만 바뀌고 키보드는 안 뜸, 숫자 부분을 탭하면 입력
- 메인 창을 맨 아래로 고정해서 캔버스를 탭해도 위젯 창이 뒤로 숨지 않음 (모든 기기)
