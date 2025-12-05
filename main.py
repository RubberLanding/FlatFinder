from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # Important: headless=True is required for GitHub Actions
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto("https://example.com")
        print(page.title())
        
        # Example: Save data to a file so we can download it later
        with open("results.txt", "w") as f:
            f.write(f"Scraped Title: {page.title()}")
            
        browser.close()

if __name__ == "__main__":
    run()