from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os
load_dotenv()


class Encryption:

    def __init__(self, key: bytes = None):

        self.key = os.getenv('ENC_KEY')
        self.fernet = Fernet(self.key)

    def encrypt(self, plaintext: str) -> bytes:
        return self.fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self.fernet.decrypt(ciphertext).decode()
        except Exception:
            return ""

    def get_key(self) -> str:
        return self.key.decode()

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()



if __name__ == "__main__":
    encrypt = Encryption()
    print(encrypt.encrypt('Hello'))