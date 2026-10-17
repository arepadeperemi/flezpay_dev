import urllib.parse

import requests
from dotenv import load_dotenv
import os
import warnings
# from urllib3.exceptions import NotOpenSSLWarning

# warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
load_dotenv()



def sms_sender(message, mobiles, sender='FlezPay'):
    data = {
        'username': os.getenv('SMS_API_USERNAME'),
        'password': os.getenv('SMS_API_PASSWORD'),
        'message': message,
        'sender': sender,
        'mobiles': mobiles
    }
    params = urllib.parse.urlencode(data)

    url = f"https://portal.nigeriabulksms.com/api/?{params}"
    request = requests.request('get', url)
    if request.status_code == 200:
        response = request.json()
        return response
    else:
        raise Exception(request.text)
