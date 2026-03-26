#!/usr/bin/env python3
"""Fetch specific glm-coding pricing from bigmodel.cn using Playwright."""

import asyncio
import json
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)


async def fetch_glm_coding_pricing():
    """Fetch specific glm-coding pricing information."""

    # Try the pricing page with specific navigation
    urls_to_try = [
        "https://bigmodel.cn/pricing",
        "https://bigmodel.cn/price",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        all_content = []

        for url in urls_to_try:
            print(f"\n{'='*60}")
            print(f"Fetching: {url}")
            print('='*60)

            try:
                await page.goto(url, timeout=30000, wait_until="networkidle")
                await asyncio.sleep(5)  # Extra wait for JS rendering

                # Get full page text
                body = await page.query_selector("body")
                if body:
                    full_text = await body.inner_text()
                    all_content.append({
                        "url": url,
                        "full_text": full_text[:50000]  # First 50k chars
                    })

                # Look for coding-related elements
                print("\nSearching for coding-related content...")

                # Try to find any elements with "coding" or "glm-coding" or "编码"
                selectors = [
                    "text=coding",
                    "text=编码",
                    "text=GLM-4",
                    "text=GLM-5",
                    "[class*=coding]",
                    "[class*=Coding]",
                ]

                for sel in selectors:
                    try:
                        elements = await page.query_selector_all(sel)
                        print(f"  Selector '{sel}': {len(elements)} elements")
                        for i, elem in enumerate(elements[:3]):
                            text = await elem.inner_text()
                            if text and len(text.strip()) > 5:
                                print(f"    [{i}] {text.strip()[:150]}")
                    except Exception as e:
                        print(f"  Selector '{sel}': Error - {e}")

                # Take a screenshot
                screenshot_path = Path(__file__).parent / f"screenshot_{url.replace('://', '_').replace('/', '_')}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"\nScreenshot saved to: {screenshot_path}")

            except Exception as e:
                print(f"ERROR: {e}")

        await browser.close()

    return all_content


async def main():
    output_file = Path(__file__).parent / "glm_coding_full.json"

    print("Starting Playwright to fetch bigmodel.cn glm-coding pricing...")
    results = await fetch_glm_coding_pricing()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nFull results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
