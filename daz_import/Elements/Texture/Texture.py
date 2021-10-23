from __future__ import annotations
import bpy
from bpy.types import Texture as BlenderTexture

from typing import List, Dict
from daz_import.utils import *
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import *


class Texture:
    _textures: Dict[str, Texture] = {}

    def __init__(self, map_):
        from .Map import Map
        self.rna: BlenderTexture = None
        self.map: Map = map_
        self.built: Dict[str, bool] = {"COLOR": False, "NONE": False}
        self.images: Dict[str, Any] = {"COLOR": None, "NONE": None}

    def __repr__(self):
        return ("<Texture %s %s %s>" % (self.map.url, self.map.image, self.rna))

    def getName(self):
        if self.map.url:
            return self.map.url
        elif self.map.image:
            return self.map.image.name
        else:
            return ""

    def buildInternal(self):
        if self.built["COLOR"]:
            return self

        key = self.getName()

        if key:
            img = self.images["COLOR"] = self.map.build()
            if img:
                tex = self.rna = bpy.data.textures.new(img.name, 'IMAGE')
                tex.image = img
            else:
                tex = None

            self._textures[key] = self
        else:
            tex = self.rna = bpy.data.textures.new(self.map.label, 'BLEND')
            tex.use_color_ramp = True
            color = tuple(*self.map.color, 1)

            for elt in tex.color_ramp.elements:
                elt.color = color

        self.built["COLOR"] = True
        return self

    def buildCycles(self, colorSpace):
        if self.built[colorSpace]:
            return self.images[colorSpace]
        elif colorSpace == "COLOR" and self.images["NONE"]:
            img = self.images["NONE"].copy()
        elif colorSpace == "NONE" and self.images["COLOR"]:
            img = self.images["COLOR"].copy()
        elif self.map.url:
            img = self.map.build()
        elif self.map.image:
            img = self.map.image
        else:
            img = None
        if img:
            if colorSpace == "COLOR":
                img.colorspace_settings.name = "sRGB"
            elif colorSpace == "NONE":
                img.colorspace_settings.name = "Non-Color"
            else:
                img.colorspace_settings.name = colorSpace
        self.images[colorSpace] = img
        self.built[colorSpace] = True
        return img

    def hasMapping(self, map_):  # : Map
        if map_:
            return (map_.size is not None)
        else:
            return (self.map and self.map.size is not None)

    def getMapping(self, mat, map_):  # : Map
        # mapping scale x = texture width / lie document size x * (lie x scale / 100)
        # mapping scale y = texture height / lie document size y * (lie y scale / 100)
        # mapping location x = udim place + lie x position * (lie y scale / 100) / lie document size x
        # mapping location y = (lie document size y - texture height * (lie y scale / 100) - lie y position) / lie document size y

        if self.images["COLOR"]:
            img = self.images["COLOR"]
        elif self.images["NONE"]:
            img = self.images["NONE"]
        else:
            ErrorsStatic.report(
                "BUG: getMapping finds no image", trigger=(3, 5))
            return (0, 0, 1, 1, 0)

        tx, ty = img.size
        mx, my = map_.size
        kx, ky = tx/mx, ty/my
        ox, oy = map_.xoffset/mx, map_.yoffset/my
        rz = map_.rotation

        ox += mat.channelsData.getValue("getChannelHorizontalOffset", 0)
        oy += mat.channelsData.getValue("getChannelVerticalOffset", 0)
        kx *= mat.channelsData.getValue("getChannelHorizontalTiles", 1)
        ky *= mat.channelsData.getValue("getChannelVerticalTiles", 1)

        sx = map_.xscale*kx
        sy = map_.yscale*ky

        if rz == 0:
            dx = ox
            dy = 1 - sy - oy
            if map_.xmirror:
                dx = sx + ox
                sx = -sx
            if map_.ymirror:
                dy = 1 - oy
                sy = -sy
        elif rz == 90:
            dx = ox
            dy = 1 - oy
            if map_.xmirror:
                dy = 1 - sy - oy
                sy = -sy
            if map_.ymirror:
                dx = sx + ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 270*VectorStatic.D
        elif rz == 180:
            dx = sx + ox
            dy = 1 - oy
            if map_.xmirror:
                dx = ox
                sx = -sx
            if map_.ymirror:
                dy = 1 - sy - oy
                sy = -sy
            rz = 180*VectorStatic.D
        elif rz == 270:
            dx = sx + ox
            dy = 1 - sy - oy
            if map_.xmirror:
                dy = 1 - oy
                sy = -sy
            if map_.ymirror:
                dx = ox
                sx = -sx
            tmp = sx
            sx = sy
            sy = tmp
            rz = 90*VectorStatic.D

        return (dx, dy, sx, sy, rz)

    @classmethod
    def create(cls, map_) -> Texture:
        if tex := cls._textures.get(map_.url):
            return tex

        tex = cls(map_)
        if map_.url:
            cls._textures[map_.url] = tex

        return tex
