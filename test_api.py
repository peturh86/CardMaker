import requests
import os

# Test the endpoint with a simple image
url = "http://127.0.0.1:8082/generate-card"

# Create a simple test image
from PIL import Image

test_image = Image.new("RGB", (200, 200), color="red")
test_image.save("test_photo.jpg")

# Prepare the form data
files = {"photo": open("test_photo.jpg", "rb")}
data = {
    "name": "Test User",
    "kt": "1234567-1234",
    "title": "Test Engineer",
    "remove_bg": False,
}

try:
    response = requests.post(url, files=files, data=data)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        with open("generated_card.jpg", "wb") as f:
            f.write(response.content)
        print("Card generated successfully!")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error making request: {e}")
finally:
    files["photo"].close()
    if os.path.exists("test_photo.jpg"):
        os.remove("test_photo.jpg")
