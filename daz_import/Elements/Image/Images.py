from typing import Dict, List

from daz_import.Elements.Assets import Asset
from daz_import.Elements.Texture.Map import Map
# from daz_import.Lib.Settings import Settings


class Images(Asset):
    def __init__(self, fileref):
        super().__init__(fileref)
        self.maps: List[Map] = []

    def __repr__(self):
        return ("<Images %s r: %s>" % (self.id, self.maps))

    def parse(self, data: dict):
        super().parse(data)

        mapSize = data.get("map_size")

        for inner_data in data.get("map", []):
            inner_data: Dict

            if mask := inner_data.get("mask"):
                self.maps.append(Map(mask, True))

            self.maps.append(Map(inner_data, False))

        if mapSize is not None:
            for map_ in self.maps:
                map_.size = mapSize

        # self.parseGamma(struct)

    def update(self, struct: Dict):
        ...
        # self.parseGamma(struct)

    # def parseGamma(self, struct: Dict):
    #     gamma = struct.get("map_gamma")
    #     if not gamma:
    #         return

    #     for map_ in self.maps:
    #         Settings.gammas_[map_.url] = gamma

    # def build(self, _=None):
    #     images = []

    #     for map_ in self.maps:
    #         images.append(map_.get_image())

    #     # import pdb
    #     # pdb.set_trace()

    #     return images
