"""Capture real Chromium settings in an isolated, empty test profile.

Images remain original. Red-box annotations are HTML/SVG overlays in the guide.
Never use a personal browser profile or add account credentials here.
"""
import asyncio
import json
from pathlib import Path
import tempfile

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "setup-images"


async def run():
    OUT.mkdir(parents=True, exist_ok=True)
    annotations = {}
    with tempfile.TemporaryDirectory(prefix="oci-guide-") as profile:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(profile, channel="chromium", headless=True,
                locale="ko-KR", viewport={"width": 1180, "height": 820},
                args=["--lang=ko", "--disable-extensions-except=" + str(ROOT / "extension"),
                      "--load-extension=" + str(ROOT / "extension")])
            worker = context.service_workers[0] if context.service_workers else await context.wait_for_event("serviceworker")
            extension_id = worker.url.split("/")[2]
            page = await context.new_page()
            await page.goto("chrome://extensions")
            await page.wait_for_selector("extensions-manager")
            await page.locator("extensions-toolbar #devMode").click()
            await page.wait_for_timeout(300)

            async def capture(name, selectors):
                boxes = []
                for selector in selectors:
                    locator = page.locator(selector)
                    await locator.wait_for(state="visible")
                    box = await locator.bounding_box()
                    boxes.append({k: round(box[k], 2) for k in ("x", "y", "width", "height")})
                await page.screenshot(path=str(OUT / (name + ".png")))
                annotations[name] = {"width": 1180, "height": 820, "boxes": boxes}

            await capture("01-developer-load", ["extensions-toolbar #devMode", "extensions-toolbar #loadUnpacked"])
            card = f"extensions-item[id='{extension_id}']"
            await capture("02-existing-reload", [card + " #dev-reload-button"])
            await capture("03-details", [card + " #detailsButton"])
            await page.locator(card + " #detailsButton").click()
            await page.wait_for_selector("extensions-detail-view #allow-incognito")
            await page.locator("extensions-detail-view #allow-incognito").scroll_into_view_if_needed()
            await page.wait_for_timeout(250)
            await capture("04-allow-incognito", ["extensions-detail-view #allow-incognito"])
            await context.close()
    (OUT / "annotations.json").write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"real_settings_screenshots": len(annotations), "personal_profile_used": False}))


if __name__ == "__main__":
    asyncio.run(run())
