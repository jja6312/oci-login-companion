# OCI Login Companion

Chrome과 Brave에서 테넌시를 검색해 OCI 로그인을 시작하는 브라우저 확장입니다.

**[Install.cmd 다운로드](https://github.com/jja6312/oci-login-companion/releases/latest/download/Install.cmd)**

CMD 하나로 처음 설치와 기존 관리형 설치 업데이트를 처리합니다. Python과 관리자 권한은 필요하지 않습니다.
파일을 준비한 뒤 **실제 화면과 빨간 박스로 된 안내**를 엽니다. 탐색기 폴더는 자동으로 열지 않습니다.

## 처음 설치

안내의 **폴더 경로 복사**를 누른 뒤 확장 관리에서 개발자 모드를 켭니다.
**압축해제된 확장 프로그램 로드**를 누르고 폴더 선택 창에 경로를 붙여넣습니다.
마지막으로 **세부정보 → 시크릿 모드에서 허용**을 켜세요.

## 기존 사용자

설치했던 **같은 브라우저와 같은 프로필**에서 기존 카드의 새로고침을 누릅니다.
같은 확장 폴더를 유지하므로 기존 계정과 설정을 계속 사용합니다. 카드를 삭제하거나 새로 추가하지 마세요.
확장 파일과 업데이트 영수증은 백업하며, 사용자가 수정한 설치는 덮어쓰지 않습니다.

## 사용

**Ctrl+Shift+Space**로 열고 테넌시를 검색합니다. 계정, 사용자, 비밀번호와 Bypass Code를 등록할 수 있습니다.
Excel에서 복사한 여러 행의 일괄 등록, 고객 별칭, 테마와 시크릿 창을 지원합니다.
확장은 OCI의 확인된 로그인 흐름에서 동작하며 필요한 사이트 접근 권한을 브라우저에서 요청합니다.

계정 데이터는 사용자 브라우저에 저장합니다. 배포본과 스크린샷에는 실제 계정이나 인증값이 없습니다.
시크릿 허용은 사용자가 직접 켜야 합니다. 설치기는 브라우저 정책이나 프로필 파일을 수정하지 않습니다.

## 개발

```powershell
node --test tests/*.test.mjs
python scripts/build_visual_guide.py
python scripts/build_visual_installer.py
python -m unittest discover -s tests -p test_visual_installer.py -q
```

일반 빌드는 Python 표준 라이브러리만 사용합니다. 화면 재촬영과 브라우저 보존 시험에는 Playwright가 필요합니다.
현재 앱은 **1.2.3**, 설치기는 **r8**입니다. r8은 설치와 안내를 변경하며 확장 파일은 r7과 동일합니다.
전달 폴더의 최상위에는 `Install.cmd`만 두고 ZIP과 개발 자료는 `_support`에 보관합니다.
실제 사용자 OCI 인증과 브라우저의 수동 등록 완료는 자동 시험의 범위에 포함하지 않습니다.
기존 버전 검증 스크립트는 `tests`와 `windows`에 보존했습니다.
