import os
import boto3
from dotenv import load_dotenv

load_dotenv()


def get_boto3_session():
    # 1. Проверяем, загрузились ли переменные из .env
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION', 'eu-west-3')

    if not access_key or not secret_key:
        print("⚠️ ВНИМАНИЕ: AWS ключи не найдены в переменных окружения или .env файле!")

    try:
        # Пытаемся создать сессию
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        # Проверяем, валидны ли учетные данные (вызов STS)
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Успешное подключение! ARN: {identity['Arn']}")
        return session
    except Exception as e:
        print(f"❌ Ошибка аутентификации AWS: {e}")
        return None


def setup_duckdb_s3(con):
    session = get_boto3_session()
    if session is None:
        raise Exception("Не удается настроить DuckDB: сессия AWS не создана.")

    credentials = session.get_credentials()
    if credentials is None:
        raise Exception("Критическая ошибка: Boto3 нашел сессию, но не нашел ключи. Проверьте .env!")

    creds = credentials.get_frozen_credentials()

    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute(f"SET s3_access_key_id='{creds.access_key}';")
    con.execute(f"SET s3_secret_access_key='{creds.secret_key}';")
    if creds.token:
        con.execute(f"SET s3_session_token='{creds.token}';")
    con.execute(f"SET s3_region='{session.region_name}';")
    print("🚀 DuckDB настроен для работы с S3.")


