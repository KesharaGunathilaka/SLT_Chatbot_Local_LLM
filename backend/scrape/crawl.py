import asyncio
from urllib.parse import urldefrag
from crawl4ai import (
    AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode,
    MemoryAdaptiveDispatcher
)


async def crawl_recursive_batch(start_urls, max_depth=5, max_concurrent=4):
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        stream=False
    )
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=70.0,
        check_interval=1.0,
        max_session_permit=max_concurrent
    )

    visited = set()

    def normalize_url(url):
        return urldefrag(url)[0]
    current_urls = set([normalize_url(u) for u in start_urls])

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for depth in range(max_depth):
            print(f"\n=== Crawling Depth {depth+1} ===")
            urls_to_crawl = [normalize_url(
                url) for url in current_urls if normalize_url(url) not in visited]

            if not urls_to_crawl:
                break

            results = await crawler.arun_many(
                urls=urls_to_crawl,
                config=run_config,
                dispatcher=dispatcher
            )

            next_level_urls = set()

            for result in results:
                norm_url = normalize_url(result.url)
                visited.add(norm_url)  # Mark as visited (no fragment)
                if result.success:
                    print(
                        f"[OK] {result.url} | Markdown: {len(result.markdown) if result.markdown else 0} chars")
                    # Collect all new internal links for the next depth
                    for link in result.links.get("internal", []):
                        next_url = normalize_url(link["href"])
                        if next_url not in visited:
                            next_level_urls.add(next_url)
                else:
                    print(f"[ERROR] {result.url}: {result.error_message}")

            # Move to the next set of URLs for the next recursion depth
            current_urls = next_level_urls

# if __name__ == "__main__":
#     asyncio.run(crawl_recursive_batch(
#         ["https://www.slt.lk/home"], max_depth=5, max_concurrent=4))

if __name__ == "__main__":
    timeout_seconds = 300
    try:
        asyncio.run(asyncio.wait_for(
            crawl_recursive_batch(
                ["https://www.slt.lk/home"], max_depth=5, max_concurrent=4),
            timeout=timeout_seconds
        ))
    except asyncio.TimeoutError:
        print(f"❌ Crawl timed out after {timeout_seconds} seconds.")
