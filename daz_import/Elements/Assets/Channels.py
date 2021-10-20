from __future__ import annotations
import copy
from typing import List, Dict, Any
from daz_import.Lib.Settings import Settings
from daz_import.Lib.VectorStatic import VectorStatic
from mathutils import Vector
from .Asset import Asset

# -------------------------------------------------------------
#   Channels class
# -------------------------------------------------------------


class Channels:
    def __init__(self, asset: Asset):
        self.__asset: Asset = asset
        self.channels = {}
        self.extra = []

    def parse(self, data: Dict[str, Any]):
        if url := data.get("url"):
            asset = self.__asset.get_children(url=url)
            if asset and hasattr(asset, "channels"):
                self.channels = copy.deepcopy(asset.channels)

        for key, value in data.items():
            if key == "extra":
                self.setExtraData(value)
            if not isinstance(value, dict):
                continue
            if channel := value.get("channel"):
                self.setChannel(channel)

    def setChannel(self, data: dict):
        if not data.get("visible", True):
            return
        self.channels[data.get('id')] = data

        # if False and "label" in channel.keys():
        #     self.channels[channel["label"]] = channel

    def update(self, data: dict):
        for key, data in data.items():
            if key == "extra":
                self.setExtraData(data)
            elif isinstance(data, dict) and "channel" in data.keys():
                self.replaceChannel(data["channel"])

    def replaceChannel(self, data: Dict, key: str = None):
        if not data.get("visible", True):
            return

        if key is None:
            key = data.get("id")

        if oldchannel := self.channels.get(key):
            self.channels[key] = data

            for name, value in oldchannel.items():
                if name not in data.keys():
                    data[name] = value
        else:
            self.channels[key] = copy.deepcopy(data)
        # if False and "label" in channel.keys():
        #     self.channels[channel["label"]] = self.channels[key]

    def getChannel(self, attrs: List[str], onlyVisible=True):
        if isinstance(attrs, str):
            return self.get_component(attrs)
        return self.get_channel(*attrs, onlyVisible=onlyVisible)

    def get_channel(self, *keys, onlyVisible=True):
        for key in keys:
            if channel := self.channels.get(key):
                if channel.get("visible", True) \
                        or not onlyVisible:
                    return channel

    def get_component(self, key):
        if channel := self.__asset.object_dict.get(key):
            return channel()

    def equal(self, other: Channels) -> bool:
        for key, value in self.channels.items():
            if key not in other.channels.keys()\
                    or other.channels[key] != value:
                return False
        return True

    def copy(self, other: Channels):
        for key, value in other.channels.items():
            self.channels[key] = value

    def getValue(self, key: str, default: Any, onlyVisible=True):
        channel = self.getChannel(key, onlyVisible)
        return self.getChannelValue(channel, default)

    # def getValueImage(self, key: str, default):
    #     channel = self.getChannel(key)
    #     value = self.getChannelValue(channel, default)
    #     return value, channel.get("image_file")

    @classmethod
    def getChannelValue(cls, channel, default, warn=True):
        if channel is None:
            return default

        if not cls.getImageFile(channel)\
                and "invalid_without_map" in channel.keys()\
                and channel["invalid_without_map"]:
            return default

        for key in ["color", "strength", "current_value", "value"]:
            if key not in channel.keys():
                continue
            value = channel[key]

            if VectorStatic.is_vector(default):
                if not VectorStatic.is_vector(value):
                    value = Vector((value, value, value))
                return value
            if VectorStatic.is_vector(value):
                value = (value[0] + value[1] + value[2])/3
            return value

        if warn and Settings.verbosity > 2:
            print("Did not find value for channel %s" % channel["id"])
            print("Keys: %s" % list(channel.keys()))
        return default

    @staticmethod
    def getImageFile(channel: Dict):
        if cache := channel.get("image_file"):
            return cache
        elif cache := channel.get("literal_image"):
            return cache

    def setExtraData(self, list_: List[Dict]):
        if not isinstance(list_, list):
            list_ = [list_]

        self.extra = list_

        for extra in list_:
            self.__asset.setExtra(extra)
            for cstruct in extra.get("channels", []):
                if not isinstance(cstruct, dict):
                    continue
                if channel := cstruct.get("channel"):
                    self.replaceChannel(channel)
    def values(self):
        return self.channels.values()
