from typing import List

from daz_import.Elements.Assets import Asset
from daz_import.Elements.Texture.Map import Map
from daz_import.Lib.Settings import Settings


class Images(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        self.maps: List[Map] = []

    def __repr__(self):
        return ("<Images %s r: %s>" % (self.id, self.maps))

    def parse(self, struct):
        Asset.parse(self, struct)

        mapSize = None
        for key in struct.keys():
            if key == "map":
                for mstruct in struct["map"]:
                    if "mask" in mstruct.keys():
                        self.maps.append(Map(mstruct["mask"], True))
                    self.maps.append(Map(mstruct, False))
            elif key == "map_size":
                mapSize = struct[key]
        if mapSize is not None:
            for map_ in self.maps:
                map_.size = mapSize
        self.parseGamma(struct)

    def update(self, struct):
        self.parseGamma(struct)

    def parseGamma(self, struct):
        if "map_gamma" in struct.keys():
            gamma = struct["map_gamma"]
            for map_ in self.maps:
                Settings.gammas_[map_.url] = gamma

    def build(self):
        images = []
        for map_ in self.maps:
            img = map_.build()
            images.append(img)
        return images
