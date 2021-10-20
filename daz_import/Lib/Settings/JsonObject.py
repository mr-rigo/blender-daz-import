from typing import List, Dict, Any
import os
from .Json import Json


class JsonObject:
    def __init__(self, path):
        self.__settingsPath = path
        self.load()

    def load(self):
        path = self.__settingsPath

        if not os.path.exists(path):
            return
        self.deserialize(Json.load(path))

    def save(self):
        path = self.__settingsPath
        Json.save(self.serialize(), path)
        print(f"Settings file {path} saved")

    def serialize(self) -> Dict[str, Any]:
        data = {}
        for key, value in self.__dict__.items():
            if key[-1] == '_' or key[0] == '_':
                continue
            data[key] = value
        return data

    def deserialize(self, settings: Dict[str, Any]):
        if not isinstance(settings, dict):
            raise ValueError('JsonObject:type error')

        for key, value in settings.items():
            self.__dict__[key] = value

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    # def deserialize(self, settings: Dict):
    #     from daz_import.Lib.ObjectDict import ObjectDict
    #     if not isinstance(settings, dict):
    #         raise ValueError('JsonObject:type error')
    #     data = ObjectDict(self)

    #     for key, value in settings.items():
    #         if not data.exists(key):
    #             continue
    #         data[key] = value
