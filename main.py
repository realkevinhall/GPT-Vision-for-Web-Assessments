import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from utilities import capture_user_input, image_b64, setup_assessment_framework, extract_json, highlight_links, setup_openai

from playwright.async_api import async_playwright

async def main():
    # Setup App Data
    client = setup_openai()
    assessment_framework = setup_assessment_framework(os.environ['FRAMEWORK_INPUT_PATH'])
    continue_dialogue = True
    
    # Provide OpenAI with system prompt
    messages = [
        {
            "role": "system",
            "content": """You are a research tool to support the evaluation of digital e-commerce experiences. I want you to be as brief as possible when communicating with me, unless I specifically ask for a more detailed explanation.
            
            You are connected to a web browser and you will be given the screenshot of the website you are on. The links on the website will be highlighted in red in the screenshot. Always read what is in the screenshot. Don't guess link names.

            You can go to a specific URL by answering with the following JSON format:
            {"url": "url goes here"}

            You can click links on the website by referencing the text inside of the link/button, by answering in the following JSON format:
            {"click": "Text in link"}

            You have permission to navigate around the site on your own to gather information. Once you get started on your tasks, if you get stuck on any task or need me to provide additional information, include the following JSON in your answer:
            {"user_input_needed": "true"}

            You will be given a framework with specific dimensions to evaluate each website, and a scoring guide that you can use as a standard for your assessment. Always use the content of the website and in your screenshots for completing the evaluation.

            The framework is organized in a logical way to support your analysis.
            
            The first column has row numbers, these will be the unique identifiers for your messaging (framework_row_index). Count should begin at 0 and increment for each L2 that is evaluated.
            L1 is a top level category that maps to a phase of the digital experience.
            L2 is a specific dimension to be evaluated. All L2s map to an L1, so when you evaluate all the L2s, you get a full understanding of the performance at the L1 level.
            Description is a short text explaining what the L2 is measuring.
            There are 4 columns for maturity scores, from 1 to 4. A score of 1 should indicate that a capability is minimally functional, while a 4 would be an example of industry-leading functionality. Each L2 has its own maturity scoring guide. Use these scoring definitions for your evaluation.

            Start by understanding the full content of the evaluation framework so that you know what to look for when scanning the websites. Before you begin the evaluation look at the home page, navigate to a few PLPs, and then the PDPs.

            Once you are on a URL and feel confident in your answer for evaluating a certain dimension of the website, you can answer with a message in the following JSON format:
            {"score_ready": "true", "framework_row_index": row # of the L2 being evaluated, "score": score between 1 and 4, based on the scoring guide for each L2, "scoring_notes": "Less than 3 sentences of rationale for scoring", "relevant_link": "url of site that has information to justify the score"}

            When providing a relevant_url for scoring, please be as specific as possible with the URL. Provide the full path to the site page that justifies the scoring. This could be the home page, PLP, PDP, or other brand page depending on the L2 being evaluated. 

            Although you may have some prior knowledge about the site's content from your training data, only use information from the screenshots provided when conducting scoring in the evaluation framework.

            Use google search by setting a sub-page like 'https://google.com/search?q=search' if necessary. Prefer to use Google for simple queries. If the user provides a direct URL, go to that one. Do not make up links"""
        },
        {
            "role": "system",
            "content": f"""The assessment framework you should use for your analysis is available here: {assessment_framework}"""
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
        # TODO: Correct file names for highlight / clean and by framework area
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
                base64_image = image_b64("screenshot_highlighted.png")
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
            
            action_message_found, clean_json = extract_json(message_text)
            if action_message_found:
                if "click" in clean_json:
                    link_text = clean_json["click"].strip()

                    try:
                        found_element = await page.query_selector(f'.gpt-clickable:has-text("{link_text}")')

                        if found_element:
                            await found_element.click()
                            await page.wait_for_load_state("domcontentloaded")
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
                        else:
                            raise Exception("Can't find link")
                    except Exception as e:
                        print("ERROR: Clicking failed", e)
                        messages.append({
                            "role": "user",
                            "content": "ERROR: I was unable to click that element",
                        })
                    continue

                elif "url" in clean_json:
                    url = clean_json["url"].strip()
                    continue

                elif "score_ready" in clean_json:
                    framework_row_index = int(clean_json["framework_row_index"])
                    score = int(clean_json["score"])
                    scoring_notes = clean_json["scoring_notes"]
                    relevant_url = clean_json["relevant_link"]
                    columns_to_update = ["Capability Score", "Scoring Notes", "Example URL"]
                    scoring_data = {"Capability Score": score, "Scoring Notes": scoring_notes, "Example URL": relevant_url}
                    assessment_framework.loc[framework_row_index, columns_to_update] = scoring_data
                    # TODO: Do I want users to be prompted after each scoring?
                    # Investigate if it's a better UX to allow GPT to run without interruption, or allow users to confirm action each time
                    # Is there a better way to control this flow? Can we indicate the beginning / end of a processing task?
                    print("GPT: Do you have any questions about the scoring? Type y to ask a question or n to proceed")
                    user_message, continue_dialogue = capture_user_input("You: ")
                    if not continue_dialogue:
                        break
                    if user_message.strip().lower() == "y" or user_message.strip().lower() == "yes":
                        user_message, continue_dialogue = capture_user_input("You: ")
                        messages.append({
                            "role": "user",
                            "content": user_message
                        })
                    continue
               
            user_message, continue_dialogue = capture_user_input("You: ")

            messages.append({
                "role": "user",
                "content": user_message
            })

        # Close browser / open streams
        await browser.close()
        assessment_framework.to_excel(os.environ["FRAMEWORK_OUTPUT_PATH"], index=False)
        

if __name__ == "__main__":
    asyncio.run(main())