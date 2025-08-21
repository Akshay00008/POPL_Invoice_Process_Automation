from Vendor_Portal.test import process_invoice_ocr_kra_portal
import asyncio
from playwright.async_api import async_playwright

async def visit_and_validate_invoice_number(combined_data: dict):
    print("line number 6 ")
    print(combined_data)
    result_status = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for pdf_file, data in combined_data.items():
            urls = data.get("urls", [])
            invoice_number = data.get("invoice_data", {}).get("control_unit_invoice_number", "").strip()

            for url in urls:
                print(f"\n🌐 Visiting invoice URL from '{pdf_file}':\n   🔗 {url}")
                try:
                    await page.goto(url, timeout=30000)

                    await page.wait_for_selector("text=Control Unit Invoice Number", timeout=10000)
                    print("   ✅ Invoice page loaded.")

                    home_button = page.locator("input[type='button'][value='Home']")
                    if await home_button.is_visible():
                        await home_button.click()
                        await page.wait_for_load_state("load")
                        print("   🏠 Navigated to Home.")

                        await page.wait_for_selector('a[onclick="javascript:invoiceNumberchecker();"]', timeout=5000)
                        await page.locator('a[onclick="javascript:invoiceNumberchecker();"]').click()
                        await page.wait_for_load_state("load")
                        print("   🔎 Navigated to Invoice Number Checker page.")

                        await page.wait_for_selector("#invoiceNumber", timeout=5000)
                        await page.fill("#invoiceNumber", invoice_number)
                        print(f"   🧾 Entered CUIN: {invoice_number}")

                        await page.click("#validate")
                        print("   ✅ Clicked Validate button.")

                        await page.wait_for_selector("#dtlTblDiv", state="visible", timeout=10000)
                        # print("   📄 Invoice details section is now visible.")

                        ## For-indepth Debugging
                        # html_content = await page.content()
                        # html_filename = f"debug_html_{pdf_file.replace('/', '_').replace(' ', '_')}.html"
                        # with open(html_filename, "w", encoding="utf-8") as f:
                        #     f.write(html_content)
                        # print(f"   🪵 Saved debug HTML to '{html_filename}'")

                        # ✅ Try to extract "Buyer Name"
                        try:
                            await page.wait_for_selector("#buyerName", timeout=5000)
                            buyer_name = await page.locator("#buyerName").text_content()
                            buyer_name = buyer_name.strip() if buyer_name else "N/A"
                            print(f"   🧾 Buyer Name: {buyer_name}")

                            result_status[pdf_file] = {
                                "status": "validated",
                                "url": url,
                                "cuin": invoice_number,
                                "buyer_name": buyer_name,
                                "final_page": await page.title()
                            }


                        except Exception as e:
                            print("   ⚠️ Could not extract Buyer Name:", e)
                            result_status[pdf_file] = {
                                "status": "validated_but_no_buyer",
                                "url": url,
                                "cuin": invoice_number,
                                "error": "Buyer Name not found",
                                "debug_html": html_filename
                            }

                    else:
                        print("   ⚠️ Home button not found.")
                        result_status[pdf_file] = {
                            "status": "home_not_found",
                            "url": url
                        }

                except Exception as e:
                    print(f"   ❌ Error with URL from '{pdf_file}': {e}")
                    result_status[pdf_file] = {
                        "status": "error",
                        "url": url,
                        "error": str(e)
                    }

        await browser.close()
    return result_status



async def Buyer_validation(final_details):
    result = await visit_and_validate_invoice_number(final_details)
    for pdf_file, result in result.items():
        buyer = result.get("buyer_name", "").strip().upper()
        if buyer == "PWANI OIL PRODUCTS LTD":
            print(f"✅ Validated: {pdf_file}")
        else:
            print(f"❌ Not validated: {pdf_file} (Buyer: {buyer})")


# if __name__ == "__main__":
    # final_details=asyncio.run(process_invoice_ocr_kra_portal("INVOICES/ALL_PACKS/ALLPACK 266900.pdf"))
    # print(final_details)

    # asyncio.run(main(final_details))