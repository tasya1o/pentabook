import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key')
    DATABASE = os.getenv('DATABASE', 'penta_book.db')
    DEBUG = os.getenv('DEBUG', 'false').lower() in ['true', '1', 't', 'y', 'yes']
