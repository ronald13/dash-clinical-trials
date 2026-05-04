import os
from dotenv import load_dotenv

load_dotenv()
print(f"Проверка ключа: {os.getenv('AWS_ACCESS_KEY_ID')[:5]}***") # Должно вывести AKIA...