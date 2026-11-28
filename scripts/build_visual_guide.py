"""Build a self-contained guide from real screenshots and SVG red boxes."""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / 'docs/setup-images'


def picture(name, crop):
    meta = json.loads((IMAGES/'annotations.json').read_text())[name]
    data = base64.b64encode((IMAGES/(name+'.png')).read_bytes()).decode()
    rects = ''.join(f'<rect x="{b["x"]-5}" y="{b["y"]-5}" width="{b["width"]+10}" height="{b["height"]+10}" rx="5" fill="none" stroke="#f03243" stroke-width="4"/>' for b in meta['boxes'])
    return f'<svg viewBox="{crop}" role="img" aria-label="빨간 박스로 표시한 클릭 위치"><image width="{meta["width"]}" height="{meta["height"]}" href="data:image/png;base64,{data}"/>{rects}</svg>'


def main():
    first = picture('01-developer-load', '0 0 1180 125')
    reload = picture('02-existing-reload', '500 194 440 235')
    details = picture('03-details', '500 194 440 235')
    private = picture('04-allow-incognito', '310 375 695 170')
    picker = picture('05-folder-picker', '0 0 946 266')
    html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OCI Companion 설치 안내</title><style>
*{box-sizing:border-box}body{margin:0;padding:24px 16px;background:#f5f4f9;color:#272332;font:14px/1.6 system-ui,'Malgun Gothic',sans-serif}main{max-width:960px;margin:auto}header{display:flex;align-items:center;gap:12px}header b{font-size:20px}header span{color:#81758f}h1{font-size:27px;margin:18px 0 6px}p{margin:6px 0 14px;color:#70677b}.tools,.steps{display:flex;gap:8px;flex-wrap:wrap}button{cursor:pointer;border:1px solid #ddd5e8;border-radius:9px;background:#fff;color:#544860;padding:9px 14px;font:inherit}button.active,.primary{background:#8e65d7;color:#fff;border-color:#8e65d7}section,.path-card{background:#fff;border:1px solid #e1dce8;border-radius:13px;padding:18px;margin:16px 0}.path-card{position:sticky;top:10px;z-index:2;box-shadow:0 4px 18px #29233510}textarea{display:block;resize:none;width:100%;height:42px;border:1px solid #e1dce8;border-radius:8px;background:#faf9fc;padding:10px;font:13px Consolas,monospace;margin:8px 0}h2{font-size:18px;margin:0 0 10px}.number{display:inline-grid;place-items:center;width:27px;height:27px;background:#eee7fa;color:#875cce;border-radius:8px;margin-right:8px}svg{display:block;width:100%;height:auto;border-radius:8px;border:1px solid #e2deea;background:#fff}.small-shot{max-width:600px;margin:0 auto}.caption{font-size:13px;margin-top:10px;color:#71667e}.keys{display:flex;align-items:center;gap:8px;margin:12px 0}kbd{background:#eeebf3;border:1px solid #d3ccdf;border-radius:6px;padding:5px 9px;font:14px Consolas,monospace}.hidden{display:none!important}.finish{text-align:center;background:#eee7fa}details{font-size:12px;color:#82778e}a{color:#8059bd}#copy-status{padding-left:10px;color:#8059bd}footer{padding:8px 0 30px;color:#93889e;font-size:12px}@media(max-width:560px){body{padding:12px 8px}section,.path-card{padding:13px}h1{font-size:23px}.path-card{position:static}button{padding:8px 10px}}
</style><main><header><b>OCI Companion</b><span>2.0.0 설치 도우미</span></header><h1>빨간 박스를 따라 설정하세요.</h1><p id="mode-hint"></p><div class="tools"><button id="new-mode">처음 설치</button><button id="update-mode">기존 사용자</button><span style="flex:1"></span><button class="browser active" data-scheme="chrome">Chrome</button><button class="browser" data-scheme="brave">Brave</button><button class="browser" data-scheme="prisma">Prisma</button></div>
<p id="prisma-notice" class="caption hidden">Prisma에서는 관리자 정책이 확장 등록과 팀 파일 접근을 허용해야 합니다. 등록 화면은 prisma://extensions/ 입니다. 아래 이미지는 Chromium 예시입니다.</p><div class="path-card"><b>선택할 확장 폴더</b><textarea id="extension-path" readonly>{{EXTENSION_PATH}}</textarea><button class="primary" id="copy-path">폴더 경로 복사</button><span id="copy-status" role="status"></span></div>
<section class="new-only"><h2><span class="number">1</span>확장 관리 → 개발자 모드 → 압축해제된 확장 프로그램 로드</h2><div class="keys"><button id="copy-manager">chrome://extensions 복사</button></div>__FIRST__</section>
<section class="new-only"><h2><span class="number">2</span>폴더 선택 창에 경로 붙여넣기</h2>__PICKER__<p class="caption">위에서 복사한 경로를 주소창에 붙여넣으세요. 예시 화면은 공통 경로 표기입니다.</p></section>
<section class="update-only hidden"><h2><span class="number">1</span>기존 카드에서 새로고침</h2><div class="keys"><button class="copy-manager">chrome://extensions 복사</button></div><div class="small-shot">__RELOAD__</div><p class="caption">설치했던 같은 브라우저와 같은 프로필에서 진행하세요. 기존 카드를 삭제하거나 새로 추가하지 마세요.</p></section>
<section><h2><span class="number">3</span>세부정보 열기</h2><div class="small-shot">__DETAILS__</div></section>
<section><h2><span class="number">4</span>시크릿 모드에서 허용 켜기</h2>__PRIVATE__</section>
<section class="finish"><h2>이제 시크릿 창에서도 사용할 수 있습니다.</h2><div class="keys" style="justify-content:center"><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd><span>새 시크릿 창</span></div><div class="keys" style="justify-content:center"><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd><span>OCI Companion 열기</span></div><p>단축키가 안 되면 브라우저의 확장 프로그램 메뉴에서 OCI Companion을 선택하세요.</p></section>
<details><summary>공식 안내와 촬영 정보</summary><p>계정이 없는 Chromium 145 테스트 프로필의 실제 확장 관리 화면입니다. 폴더 선택은 Windows 화면의 주소창과 버튼만 표시했습니다. 빨간 박스는 SVG로 덧붙였습니다.</p><a href="https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world">Chrome 확장 등록 안내</a><br><a href="https://support.google.com/chrome/answer/2664769?hl=ko">시크릿 모드 허용 안내</a></details><footer>설치 파일은 준비됐습니다. 브라우저의 마지막 등록과 시크릿 허용은 위 화면에서 직접 진행하세요.</footer></main>
<script>let scheme='chrome';const path=document.querySelector('#extension-path');async function copy(text,status){try{await navigator.clipboard.writeText(text)}catch{const field=document.createElement('textarea');field.value=text;document.body.appendChild(field);field.select();if(!document.execCommand('copy')){field.remove();throw Error('copy')}field.remove()}if(status)status.textContent='복사했습니다.'}document.querySelector('#copy-path').onclick=()=>copy(path.value,document.querySelector('#copy-status')).catch(()=>{path.focus();path.select();document.querySelector('#copy-status').textContent='Ctrl+C로 복사하세요.'});function mode(value){for(const v of ['new','update']){document.querySelector('#'+v+'-mode').classList.toggle('active',v===value);document.querySelectorAll('.'+v+'-only').forEach(e=>e.classList.toggle('hidden',v!==value))}document.querySelector('#mode-hint').textContent=value==='update'?'기존 계정을 유지한 채 업데이트했습니다.':'확장 파일 준비가 끝났습니다.'}document.querySelector('#new-mode').onclick=()=>mode('new');document.querySelector('#update-mode').onclick=()=>mode('update');document.querySelectorAll('.browser').forEach(b=>b.onclick=()=>{scheme=b.dataset.scheme;document.querySelector('#prisma-notice').classList.toggle('hidden',scheme!=='prisma');document.querySelectorAll('.browser').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('#copy-manager,.copy-manager').forEach(x=>x.textContent=scheme+'://extensions 복사')});document.querySelectorAll('#copy-manager,.copy-manager').forEach(b=>b.onclick=()=>copy(scheme+'://extensions'+(scheme==='prisma'?'/':''),null));mode('{{INSTALL_MODE}}'==='update'?'update':'new');</script></html>'''
    for key, value in [('FIRST',first),('RELOAD',reload),('DETAILS',details),('PRIVATE',private),('PICKER',picker)]:
        html=html.replace('__'+key+'__', value)
    out=ROOT/'windows/setup-visual/Guide.template.html'; out.parent.mkdir(exist_ok=True)
    out.write_text(html,encoding='utf-8')
    print(json.dumps({'selfContainedGuideBytes':out.stat().st_size,'realScreenshots':5,'remoteAssets':False}))


if __name__=='__main__':main()
