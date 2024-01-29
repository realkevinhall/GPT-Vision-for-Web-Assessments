import os
import asyncio

from openai import OpenAI
import pandas as pd
from playwright.async_api import async_playwright, Page
from utilities import capture_user_input, image_b64

# Import Assessment Framework
def setup_assessment_framework(framework_path):
    return pd.read_excel(framework_path, sheet_name="Sheet1")

# Setup OpenAI
def setup_openai() -> OpenAI:
    client = OpenAI()
    client.api_key = os.environ['OPENAI_API_KEY']
    return client

# Highlight links and clickable items on the page
async def highlight_links(page: Page):
    elements = await page.query_selector_all('.gpt-clickable')
    for element in elements:
        await element.evaluate('(element) => { element.classList.remove("gpt-clickable"); }').all()

    # TODO: Avoid double highlighting button and links (in nav bars, etc.)
    # TODO: Consider adding better detection for hidden / visible elements
    for element in await page.get_by_role("button", include_hidden=False).all():
        await element.evaluate("element => { element.style.border = '1px solid red'; element.classList.add('gpt-clickable');}")

    for element in await page.get_by_role("link", include_hidden=False).all():
        await element.evaluate("element => { element.style.border = '1px solid red'; element.classList.add('gpt-clickable');}")

    for element in await page.get_by_role("textarea", include_hidden=False).all():
        await element.evaluate("element => { element.style.border = '1px solid red'; element.classList.add('gpt-clickable');}")

    for element in await page.get_by_role("treeitem", include_hidden=False).all():
        await element.evaluate("element => { element.style.border = '1px solid red'; element.classList.add('gpt-clickable');}")

async def main():
    # Setup App Data
    client = setup_openai()
    # assessment_framework = setup_assessment_framework("example-digital-assessment-framework.xlsx")
    continue_dialogue = True
    
    # Provide OpenAI with system prompt
    messages = [
        {
            "role": "system",
            "content": """You are a research tool to support the evaluation of digital e-commerce experiences. You will be given a framework with specific dimensions to evaluate each website, and a scoring guide that you can use as a standard for your assessment.
            
            You are connected to a web browser and you will be given the screenshot of the website you are on. The links on the website will be highlighted in red in the screenshot. Always read what is in the screenshot. Don't guess link names.

            You can go to a specific URL by answering with the following JSON format:
            {"url": "url goes here"}

            You can click links on the website by referencing the text inside of the link/button, by answering in the following JSON format:
            {"click": "Text in link"}

            Once you are on a URL and feel confident in your answer for evaluating a certain dimension of the website, you can answer with a regular message.

            Use google search by set a sub-page like 'https://google.com/search?q=search' if necessary. Prefer to use Google for simple queries. If the user provides a direct URL, go to that one. Do not make up links"""
        }
    ]
    
    # Setup Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.set_viewport_size({
            "width": 1200,
            "height": 1200
        })
    
        # Start main application loop
        print("I am a research tool designed to help you evaluate digital experiences. How can I assist you today?")

        prompt, continue_dialogue = capture_user_input("You: ")

        messages.append({
            "role": "user",
            "content": prompt
        })

        url = ""
        screenshot_taken = False

        while continue_dialogue:
            # URL Available
            if url != "":
                await page.goto(
                    url,
                    wait_until="domcontentloaded"
                )
                
                await page.screenshot(
                    full_page=True,
                    path="screenshot.png"
                )

                await highlight_links(page)
                
                await page.screenshot(
                    full_page=True,
                    path="screenshot_highlighted.png"
                )
                screenshot_taken = True
                url = ""

            # Screenshot Available
            if screenshot_taken:
                base64_image = image_b64("screenshot.png")
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": f"data:image/jpeg;base64,{base64_image}"
                        },
                        {
                            "type": "text",
                            "text": "Here's the screenshot of the website you are on right now. You can click on links with {\"click\": \"Link text\"} or you can crawl to another URL if this one is incorrect. If you find the answer to the user's question, you can respond normally."
                        }
                    ]
                })
                screenshot_taken = False
            
            # Query OpenAI services with user's most recent messages
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                max_tokens=1024,
                messages=messages
            )

            # Extract text from OpenAI response
            message = response.choices[0].message
            message_text = message.content

            messages.append({
                "role": "assistant",
                "content": message_text
            })
            
            # Display OpenAI response to user
            print("GPT: ", message_text)

            if message_text.find('{"click": "') != -1:
                parts = message_text.split('{"click": "')
                parts = parts[1].split('"}')
                link_text = parts[0].replace("/[^a-zA-Z0-9 ]/g", '')

                try:
                    found_element = await page.query_selector(f'.gpt-clickable:has-text("{link_text}")')

                    if found_element:
                        await found_element.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await page.screenshot(
                            full_page=True,
                            path="screenshot_after_click.png"  
                        )
                        await highlight_links(page)
                        await page.screenshot(
                            full_page=True,
                            path="screenshot_highlighted_after_click.png"  
                        )
                        screenshot_taken = True
                    else:
                        raise Exception("Can't find link")
                except Exception as e:
                    print("ERROR: Clicking failed", e)
                    messages.append({
                        "role": "user",
                        "content": "ERROR: I was unable to click that element",
                    })
                continue

            elif message_text.find('{"url": "') != -1:
                parts = message_text.split('{"url": "')
                parts = parts[1].split('"}')
                url = parts[0]
                continue

            # Accept new input from user
            user_message, continue_dialogue = capture_user_input("You: ")

            messages.append({
                "role": "user",
                "content": user_message
            })

        # Close browser / open streams
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())