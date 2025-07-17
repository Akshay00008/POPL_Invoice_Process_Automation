from playwright.async_api import async_playwright
import asyncio


async def visit_and_validate_invoice_number(invoice_number: str):
    url = "https://itax.kra.go.ke/KRA-Portal/main.htm?actionCode=showHomePageLnclick"
    result_status = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Navigate to the site
            await page.goto(url, timeout=30000)
            print("   🌐 Opened the invoice portal.")

            # Click invoice checker link
            await page.wait_for_selector('a[onclick="javascript:invoiceNumberchecker();"]', timeout=5000)
            await page.locator('a[onclick="javascript:invoiceNumberchecker();"]').click()
            await page.wait_for_load_state("load")
            print("   🔎 Navigated to Invoice Number Checker page.")

            # Fill invoice number
            await page.wait_for_selector("#invoiceNumber", timeout=5000)
            await page.fill("#invoiceNumber", invoice_number)
            print(f"   🧾 Entered CUIN: {invoice_number}")

            # Click validate
            await page.click("#validate")
            print("   ✅ Clicked Validate button.")

            # Wait for results
            await page.wait_for_selector("#dtlTblDiv", state="visible", timeout=10000)

            # Save HTML debug
            # html_content = await page.content()
            # html_filename = f"debug_html_{invoice_number}.html"
            # with open(html_filename, "w", encoding="utf-8") as f:
            #     f.write(html_content)

            # Extract buyer name
            try:
                await page.wait_for_selector("#buyerName", timeout=5000)
                buyer_name = await page.locator("#buyerName").text_content()
                buyer_name = buyer_name.strip() if buyer_name else "N/A"
                print(f"   🧾 Buyer Name: {buyer_name}")

                result_status[invoice_number] = {
                    "status": "validated",
                    "url": url,
                    "cuin": invoice_number,
                    "buyer_name": buyer_name,
                    "final_page": await page.title()
                }

            except Exception as e:
                print("   ⚠️ Could not extract Buyer Name:", e)
                result_status[invoice_number] = {
                    "status": "validated_but_no_buyer",
                    "url": url,
                    "cuin": invoice_number,
                    "error": "Buyer Name not found",
                    "debug_html": html_filename
                }

        except Exception as e:
            print(f"   ❌ Error with invoice number '{invoice_number}': {e}")
            result_status[invoice_number] = {
                "status": "error",
                "url": url,
                "error": str(e)
            }

        await browser.close()

    return result_status



