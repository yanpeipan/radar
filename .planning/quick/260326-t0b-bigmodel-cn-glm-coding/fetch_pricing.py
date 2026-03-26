#!/usr/bin/env python3
"""Fetch glm-coding pricing from bigmodel.cn using Playwright."""

import asyncio
import json
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)


async def fetch_glm_coding_pricing():
    """Fetch pricing information for glm-coding from bigmodel.cn."""

    # Try multiple URLs that might contain glm-coding pricing
    urls_to_try = [
        "https://bigmodel.cn/price",
        "https://bigmodel.cn/pricing",
        "https://open.bigmodel.cn/user-center/home",
        "https://bigmodel.cn/dev/guide?service=glm-4",
    ]

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"CONSOLE {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

        for url in urls_to_try:
            print(f"\n{'='*60}")
            print(f"Trying: {url}")
            print('='*60)

            try:
                await page.goto(url, timeout=30000, wait_until="networkidle")
                await asyncio.sleep(3)  # Wait for any lazy-loaded content

                # Get page content
                content = await page.content()

                # Try to extract pricing-related content
                # Look for common pricing indicators
                pricing_keywords = ["glm", "coding", "price", "pricing", "cost", "token", "package", "plan", "subscription", "收费", "价格", "套餐"]

                found_lines = []
                for keyword in pricing_keywords:
                    # Search in visible text
                    try:
                        elements = await page.query_selector_all(f"text={keyword}")
                        for elem in elements[:5]:  # Limit to 5 per keyword
                            text = await elem.inner_text()
                            if text and len(text.strip()) > 2:
                                found_lines.append(f"[{keyword}] {text.strip()[:200]}")
                    except:
                        pass

                # Get all headings (potential pricing tiers)
                headings = await page.query_selector_all("h1, h2, h3, h4")
                heading_texts = []
                for h in headings[:10]:
                    try:
                        text = await h.inner_text()
                        if text and len(text.strip()) > 2:
                            heading_texts.append(text.strip()[:100])
                    except:
                        pass

                # Get any price elements
                price_elements = await page.query_selector_all("[class*='price'], [class*='cost'], [class*='plan'], [class*='tier']")
                prices = []
                for elem in price_elements[:10]:
                    try:
                        text = await elem.inner_text()
                        if text and len(text.strip()) > 1:
                            prices.append(text.strip()[:100])
                    except:
                        pass

                result = {
                    "url": url,
                    "title": await page.title(),
                    "headings": heading_texts,
                    "pricing_elements": prices,
                    "keyword_matches": found_lines[:20],
                    "content_length": len(content)
                }

                results.append(result)
                print(f"Title: {result['title']}")
                print(f"Headings: {result['headings']}")
                print(f"Prices: {result['pricing_elements']}")
                print(f"Content length: {result['content_length']} chars")

            except Exception as e:
                results.append({"url": url, "error": str(e)})
                print(f"ERROR: {e}")

        await browser.close()

    return results


async def main():
    output_file = Path(__file__).parent / "pricing_results.json"

    print("Starting Playwright to fetch bigmodel.cn glm-coding pricing...")
    results = await fetch_glm_coding_pricing()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")

    # Also print summary
    for r in results:
        print(f"\n--- {r.get('url', 'unknown')} ---")
        if "error" in r:
            print(f"ERROR: {r['error']}")
        else:
            print(f"Title: {r.get('title', 'N/A')}")
            if r.get('pricing_elements'):
                print(f"Pricing elements: {r['pricing_elements']}")


if __name__ == "__main__":
    asyncio.run(main())
