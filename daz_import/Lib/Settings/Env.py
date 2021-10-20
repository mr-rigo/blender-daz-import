import os


class Env:
    @staticmethod
    def get(key: str, default=None):
        return os.environ.get(key, default)

    @staticmethod
    def set(key: str, value):
        os.environ[value] = key

