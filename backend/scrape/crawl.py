import asyncio
import os
import json
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig, LLMContentFilter, DefaultMarkdownGenerator
from crawl4ai import JsonCssExtractionStrategy
from dotenv import load_dotenv
from crawl4ai import LLMExtractionStrategy
from pydantic import BaseModel
from typing import Optional

load_dotenv()


class PackageInfo(BaseModel):
    package_name: str
    monthly_rental: Optional[str]
    installation_fee: Optional[str]
    channels: Optional[str]
    tariff_code: Optional[str]
    validity: Optional[str]


async def main():

    # 1. Browser configuration
    browser_config = BrowserConfig()

    # 2. LLM extraction strategy
#     llm_strategy = LLMExtractionStrategy(
#         llm_config=LLMConfig(provider="gemini/gemini-2.0-flash",
#                              api_token=os.getenv("GEMINI_API_KEY")),
#         schema=PackageInfo.model_json_schema(),  # Or use model_json_schema()
#         extraction_type="schema",

#         instruction="""
#         Focus on extracting the *core package information* from the SLT PEO TV "Packages & Charges" page.

# Include:
# - Package name (e.g. PEO Lite, PEO Titanium)
# - Monthly rental
# - Installation or connection charges (if shown)
# - Any channel‑count or bundled features present (like number of channels)
# - Tariff names and TRC approval details (if in listing)
# - Validity (monthly, annual, etc.)

# Exclude:
# - All navigation, header, sidebar, footer, site menus, cookie notices
# - Advertisements or “Buy” buttons
# - Images, page branding, icons, irrelevant promotion
# - Download links or PDFs (unless package info visible in main content)

# Output as clean Markdown:
# - Use headings like `## Package: PEO Lite`
# - Present each package as a section
# - Provide key fields in a bullet list
# - Wrap any code or tabular content in Markdown code blocks or tables
#         """,
#         chunk_token_threshold=1000,
#         overlap_rate=0.0,
#         apply_chunking=True,
#         input_format="markdown",   # or "html", "fit_markdown"
#         extra_args={"temperature": 0.0, "max_tokens": 800}
#     )

    # 3) Crawler run config: skip cache, use extraction
    run_config = CrawlerRunConfig(
        # Content filtering
        # extraction_strategy=llm_strategy,
        # excluded_tags=['form', 'header', 'footer'],
        # enable_rate_limiting=False,
        # rate_limit_config=None,
        # memory_threshold_percent=70.0,
        # check_interval=1.0,
        # max_session_permit=20,
        # wait_for="js:() => window.loaded === true",
        # display_mode=None,
        # exclude_external_links=True,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:

        url = "https://www.slt.lk/en/personal/peo-tv/packages-and-charges"

        result = await crawler.arun(
            url=url,
            config=run_config
        )

        if result.success:
            # Print clean content
            print("Content:", result.markdown)

            # llm_strategy.show_usage()

        # ✅ Save result.markdown to a JSON file
            scraped_data = {
                "url": url,
                "content": result.markdown
            }

            # Save to JSON file
            output_path = "../data/slt.json"

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)

            print(f"✅ Markdown saved to: {output_path}")

        else:
            print(f"Crawl failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
