"""Render only generic address/buttons from the private native dialog capture."""
import asyncio
import base64
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


async def main():
    raw = ROOT / 'work/guide/folder-dialog-private.png'
    encoded = base64.b64encode(raw.read_bytes()).decode()
    html = f'''<style>*{{box-sizing:border-box}}body{{margin:0;background:#202020;width:946px;color:#eee;font:18px "Malgun Gothic"}}.crop{{height:113px;overflow:hidden;position:relative}}img{{position:absolute;left:0;top:0;width:946px}}.bottom{{height:83px}}.bottom img{{top:-450px}}p{{margin:0;padding:20px 24px;background:#29252f}}kbd{{background:#444;padding:4px 7px;border-radius:5px}}</style><div class="crop"><img src="data:image/png;base64,{encoded}"></div><p><kbd>Ctrl+L</kbd> → <kbd>Ctrl+V</kbd> → <kbd>Enter</kbd> → <b>폴더 선택</b></p><div class="crop bottom"><img src="data:image/png;base64,{encoded}"></div>'''
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width':946,'height':266},device_scale_factor=1)
        await page.set_content(html)
        await page.screenshot(path=str(ROOT/'docs/setup-images/05-folder-picker.png'),full_page=True)
        await browser.close()
    file=ROOT/'docs/setup-images/annotations.json'
    data=json.loads(file.read_text())
    data['05-folder-picker']={'width':946,'height':266,'boxes':[{'x':137,'y':38,'width':584,'height':39},{'x':733,'y':221,'width':98,'height':31}]}
    file.write_text(json.dumps(data,indent=2)+'\n')
    print('Published crop contains only generic address and folder-selection controls; private sidebar excluded.')


if __name__=='__main__':asyncio.run(main())
