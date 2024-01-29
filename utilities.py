import base64

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