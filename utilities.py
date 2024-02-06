import base64
import json
import os
import pandas as pd
import regex
from playwright.async_api import Page
from openai import OpenAI

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

# Allow user to send messages or exit the program
def capture_user_input(prompt_text):
    want_to_quit = False
    while want_to_quit == False:
        user_input = input(prompt_text)
        if user_input == "exit":
            confirmation = input("Are you sure you want to quit? Type y (yes) or n (no)\n")
            if confirmation == "y":
                return "", False
        else:
            return user_input, True
        

# Convert Images to Base64 for use by GPT Vision API
def image_b64(image):
    with open(image, "rb") as f:
        return base64.b64encode(f.read()).decode()
    
# Configure Assessment Framework
def setup_assessment_framework(framework_path, sheet_name):
    framework = pd.read_excel(framework_path, sheet_name=sheet_name)
    # print(framework)
    return framework
    
# Return usable JSON from potential API action messages
def parse_json_objects_from_text(text):
    # Define the regular expression pattern to match JSON objects
    pattern = r'\{(?:[^{}]*|(?R))*\}'
    
    # Find all JSON objects in the text using the regular expression
    json_strings = regex.findall(pattern, text)
    
    # Initialize an empty list to store parsed JSON objects
    json_objects = []
    
    # Parse each JSON string and append the resulting object to the list
    for json_str in json_strings:
        try:
            json_objects.append(json.loads(json_str))
        except json.JSONDecodeError:
            print(f"Error decoding JSON: {json_str}")
    
    return json_objects