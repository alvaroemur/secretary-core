"""Render a single HTML element to a transparent PNG at 2×."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="HTML file or loopback preview URL")
    parser.add_argument("output", type=Path, help="Output PNG path")
    parser.add_argument("selector", nargs="?", default="#capture")
    args = parser.parse_args()

    url = urlsplit(args.source)
    if url.scheme in {"http", "https"}:
        if url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            parser.error("preview URL must use a loopback host")
        source = args.source
    else:
        path = Path(args.source).resolve()
        if not path.is_file():
            parser.error(f"HTML file does not exist: {path}")
        source = path.as_uri()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(device_scale_factor=2)
                page.goto(source, wait_until="load")
                target = page.locator(args.selector)
                target.wait_for(state="visible")
                page.evaluate("document.fonts.ready")
                target.screenshot(
                    path=args.output, type="png", omit_background=True,
                    animations="disabled", scale="device",
                )
            finally:
                browser.close()
    except Error as error:
        parser.exit(1, f"Render failed: {error}\n")


if __name__ == "__main__":
    main()
