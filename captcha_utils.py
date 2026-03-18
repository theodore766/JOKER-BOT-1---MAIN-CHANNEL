import random
import string
from captcha.image import ImageCaptcha


def generate_captcha(user_id):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    image = ImageCaptcha(width=280, height=100)
    image_path = f"captcha_{user_id}.png"
    image.write(code, image_path)
    return code, image_path
