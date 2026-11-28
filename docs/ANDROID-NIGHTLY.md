# OCI Companion 2.0.0 — Android Brave Nightly 시험 설치2

2026-11-28 기준. 기존 PC용 2.0.0와 같은 확장 코드입니다.
휴대폰 설치와 실제 OCI 인증은 아직 실기기에서 검증하지 않았습니다.
일반 Brave와 Windows Install.cmd를 위한 모바일 설치 파일은 아닙니다.

## 1. Brave Nightly 준비

Google Play에서 Brave Software의 Brave Nightly를 설치하거나 업데이트합니다.
https://play.google.com/store/apps/details?id=com.brave.browser_nightly

기존 일반 Brave와 함께 설치할 수 있습니다. 데이터는 별도입니다.
Nightly 주소창에 다음 주소를 직접 입력합니다.

brave://flags/#brave-android-extensions

Brave Android Extensions를 Enabled로 바꾸고 Relaunch를 누릅니다.
이 항목은 1.102 계열 Nightly에 추가된 실험 기능입니다.
검색 결과에 해당 항목이 없다면 그 빌드에는 설치 경로가 준비되지 않은 것입니다.
확장이 이 설정을 자동으로 켜거나 승인하지 않습니다.

## 2. 확장 파일 설치

시험 배포:
https://github.com/jja6312/oci-login-companion/releases/tag/android-nightly-v2.0.0-test2

OCI-Companion-2.0.0-Android-Nightly-test2.crx를 Nightly에서 다운로드합니다.
이 파일은 APK나 Windows 실행 파일이 아닌 서명된 브라우저 확장입니다.

Nightly 주소창에 brave://extensions 를 입력합니다.
개발자 모드를 켜고 해당 빌드의 CRX 파일 설치/불러오기 기능에서 다운로드한 CRX를 선택합니다.
버전에 따라 설치 UI가 다릅니다. CRX가 다운로드만 되거나 선택할 메뉴가 없다면
설치 성공이 아닙니다. 아래 ZIP 경로를 확인하거나 현재 Nightly 버전과 화면을 알려 주세요.
설치 확인 창의 확장 이름과 권한을 확인한 뒤 사용자가 직접 승인합니다.

ZIP 경로: 같은 배포의 .zip을 다운로드하고 휴대폰 파일 앱에서 새 폴더로 압축 해제합니다.
brave://extensions 의 압축해제된 확장 로드가 제공되면 manifest.json이 있는 폴더를 선택합니다.
폴더 선택이 제공되지 않으면 해당 빌드에서는 이 방법도 사용할 수 없습니다.
CRX와 ZIP 중 한 방식으로만 등록하세요. 둘 다 등록하면 별도 금고가 생길 수 있습니다.

## 3. 휴대폰에서 열기

초기 Android 지원은 태블릿 중심이며 휴대폰의 확장 툴바 메뉴는 개발 중입니다.
brave://extensions 에서 OCI Login Companion 카드의 세부정보와 확장 프로그램 옵션을 엽니다.
옵션 화면에도 PC와 같은 검색, 계정 추가, 로그인, 설정 기능이 있습니다.
PC 팝업 단축키를 누를 필요는 없습니다.

CRX 설치의 옵션 화면 주소:
chrome-extension://{{EXTENSION_ID}}/options.html

설치가 완료된 Nightly의 주소창에서 위 주소를 엽니다. 정상적으로 열린 뒤 북마크하면
다음부터 북마크로 접근할 수 있습니다. 확장 ID와 주소는 CRX 설치 기준입니다.
압축해제 방식은 카드의 옵션 버튼을 사용하세요.

## 4. 계정과 로그인

처음에는 로컬 저장소와 개인 금고 암호를 설정해 가상 계정으로 추가와 검색부터 확인하세요.
PC 개인 목록은 자동으로 스마트폰에 동기화되지 않습니다.
필요하면 PC의 설정 → 데이터에서 개인 목록을 내보내고 휴대폰에서 가져올 수 있습니다.
내보내기는 암호화된 .vault.json이며 원래 금고 암호로 열 수 있습니다. 암호는 파일과 별도로 보관하세요. 구버전 평문 JSON을 가져오면 원본 파일은 그대로 남습니다.

목록에서 계정을 선택하고 로그인 버튼을 누릅니다. 최초 사이트 접근 권한은 직접 승인합니다.
계정은 Oracle 공식 테넌시 입력 페이지부터 같은 Nightly의 새 탭에서 로그인합니다.
개인 모드에서 사용하려면 확장 카드의 시크릿 모드 허용과 해당 옵션 화면 진입을
실기기에서 별도로 확인해야 합니다. 시험 배포가 이 설정을 자동 변경하지 않습니다.

## 5. 팀 파일

파일 선택과 쓰기 API, 선택한 Android 문서 공급자의 권한이 모두 있어야 합니다.
API가 제공되는지와 OneDrive 문서를 지속적으로 읽고 쓸 수 있는지는 별개입니다.
현재 시험 배포에서 휴대폰 팀 파일의 재열기·편집·OneDrive 왕복 동기화는 미검증입니다.
브라우저나 공급자가 파일 연결을 지원하지 않으면 자동 동기화로 표시하지 않습니다.
파일을 한 번 가져오는 것은 스냅샷이며 팀 공유 파일에 계속 연결되는 기능이 아닙니다.
다운로드 폴더의 사본을 골랐다고 OneDrive 원본이 자동으로 갱신되는 것도 아닙니다.

## 검증 범위

CRX3는 Chromium 공식 패키저로 생성하고 별도 OpenSSL로 서명을 검증합니다.
CRX의 ZIP 본문과 배포 ZIP은 같으며 모든 실행 파일은 PC용 2.0.0의 검토된 바이트와 대조합니다.
고객 계정·개인 금고·서명 개인키는 배포 파일에 포함하지 않습니다.
PC 금고·설정·설치 경로·정식 Install.cmd 배포를 변경하지 않습니다.
서명은 배포 파일의 출처와 무결성을 위한 것이며 금고 암호화를 의미하지 않습니다.
개인/팀 목록은 암호화 금고입니다. 처음 암호를 설정하고 브라우저 재시작·5분 미사용 후에는 다시 잠금 해제합니다. 비밀번호와 복호화 키는 디스크에 저장하지 않습니다. 복호화 키는 유효한 동안 브라우저 메모리(chrome.storage.session)에만 보관합니다. 암호를 분실하면 복구할 수 없습니다. 이전 평문 목록은 금고 화면에서 먼저 이전해야 합니다.

Android 실기기에서의 설치, 권한 창, 창/탭 API, OCI 로그인과 OneDrive 동기화는
확인 전까지 지원 완료라고 보고하지 않습니다. 모바일 폭의 데스크톱 브라우저 검사는
Android 실기기 검사와 구분합니다. 문제 발생 시 Nightly 버전, 멈춘 화면 또는
확장의 진단 정보를 알려 주세요. 비밀번호와 Bypass Code는 보내지 마세요.

공식 근거:
https://github.com/brave/brave-browser/issues/59354
https://github.com/brave/brave-core/pull/40844
https://brave.com/download-nightly/
