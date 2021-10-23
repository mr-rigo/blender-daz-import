from __future__ import annotations

import bpy
from bpy.types import Material as BlenderMat

from typing import List, Dict, Tuple
from collections import OrderedDict, defaultdict
from daz_import.Elements.Assets.Channels import Channels
from daz_import.Lib.Settings import Settings
from mathutils import Vector
from urllib.parse import unquote
from daz_import.Lib.Errors import DazError, ErrorsStatic
from daz_import.Lib.Utility import UtilityStatic
from daz_import.Elements.Assets import Asset
from daz_import.Elements.Texture import Texture, Map
from daz_import.Elements.UDIM import UDimStatic
from daz_import.Elements.Color import ColorStatic
from daz_import.geometry import GeoNode, Uvset

class Material(Asset):
    loaded: Dict[str, BlenderMat] = {}

    def __init__(self, fileref: str):        
        super().__init__(fileref)
        self.channelsData: Channels = Channels(self)

        self.scene = None
        self.shader = 'UBER_IRAY'
        self.channelsData.channels = OrderedDict()
        self.textures = OrderedDict()

        self.groups = []
        self.ignore = False
        self.force = False
        self.shells = {}

        self.geometry: GeoNode = None
        self.geoemit = []
        self.geobump = {}

        self.uv_set: Uvset = None
        self.uv_sets: Dict[str, Uvset] = {}

        self.useDefaultUvs = True
        self.udim = 0
        self.basemix = 0
        self.thinWall = False
        self.refractive = False
        self.shareGlossy = False
        self.metallic = False
        self.dualLobeWeight = 0
        self.translucent = False
        self.isHair = False
        self.isShellMat = False

        self.enabled: Dict[str, str] = {}

        self.rna: BlenderMat = None

    def __repr__(self):
        return ("<Material %s %s %s>" % (self.id, self.geometry.name, self.rna))

    def parse(self, data: dict):
        super().parse(data)
        self.channelsData.parse(data)

    @staticmethod
    def getMatName(index: str) -> str:
        index = unquote(index)

        key = index.split("#")[-1]
        words = key.rsplit("-", 1)

        if len(words) == 2 and words[1].isdigit():
            return words[0]
        else:
            return key

    def addToGeoNode(self, geonode: GeoNode, key: str):                
        if key in geonode.materials.keys():
            msg = ("Duplicate geonode material: %s\n" % key +
                   "  %s\n" % geonode +
                   "  %s\n" % geonode.materials[key] +
                   "  %s" % self)
            ErrorsStatic.report(msg, trigger=(2, 3))
        geonode.materials[key] = self
        self.geometry = geonode

    def update(self, struct: Dict):
        super().update(struct)

        self.channelsData.update(struct)

        geo = geonode = None

        if ref := struct.get("geometry"):
            geo = self.get_children(url=ref, strict=True)

            if not geo:
                ...
            elif geo.is_instense('GeoNode'):
                geonode = geo
                geo = geonode.data
            elif geo.is_instense('Geometry'):
                iref = UtilityStatic.inst_ref(ref)
                if cache := geo.nodes.get(iref):
                    geonode = cache

            if geonode:
                key = self.getMatName(self.id)
                self.addToGeoNode(geonode, key)

        if uvset := struct.get("uv_set"):
            if uvset := self.get_children(url=uvset, key='Uvset'):
                uvset.material = self
                if geo and uvset != geo.default_uv_set:
                    geo.uv_sets[uvset.name] = uvset
                    self.useDefaultUvs = False

                self.uv_set = uvset

        self.basemix = self.channelsData.getValue(["Base Mixing"], 0)

        if self.basemix == 2:
            self.basemix = 0
        elif self.basemix not in [0, 1]:
            raise DazError(
                f"Unknown Base Mixing: {self.material.basemix}             ")

        # self.enabled = self.get_enabled("")
        self.enabled = self.get_enabled(self.shader)

        self.thinWall = self.channelsData.getValue(["Thin Walled"], False)
        self.refractive = (self.channelsData.getValue("getChannelRefractionWeight", 0) > 0.01 or
                           self.channelsData.getValue("getChannelOpacity", 1) < 0.99)
        self.shareGlossy = self.channelsData.getValue(
            ["Share Glossy Inputs"], False)
        self.metallic = (self.channelsData.getValue(
            ["Metallic Weight"], 0) > 0.5 and self.enabled["Metallicity"])
        self.dualLobeWeight = self.channelsData.getValue(
            ["Dual Lobe Specular Weight"], 0)
        self.translucent = (self.enabled["Translucency"] and self.channelsData.getValue(
            "getChannelTranslucencyWeight", 0) > 0.01)
        self.isHair = (
            "Root Transmission Color" in self.channelsData.channels.keys())

    def setExtra(self, data: Dict):
        type_ = data.get("type")

        if type_ == "studio/material/uber_iray":
            self.shader = 'UBER_IRAY'
        elif type_ == "studio/material/daz_brick":
            if self.url.split("#")[-1] == "PBRSkin":
                self.shader = 'PBRSKIN'
            else:
                self.shader = '3DELIGHT'
        elif type_ == "studio/material/daz_shader":
            self.shader = 'DAZ_SHADER'

    def build(self, context):
        if self.dontBuild():
            return

        mat = self.rna

        if mat is None:
            mat = self.rna = bpy.data.materials.new(self.name)
            self.loaded[mat.name] = mat

        scn = self.scene = context.scene
        mat.DazRenderEngine = scn.render.engine
        mat.DazShader = self.shader

        if self.uv_set:
            self.uv_sets[self.uv_set.name] = self.uv_set

        geonode = self.geometry
        if geonode \
                and geonode.is_instense('GeoNode')\
                and geonode.data\
                and geonode.data.uv_sets:
            for uv, uvset in geonode.data.uv_sets.items():
                if not uvset:
                    continue
                self.uv_sets[uv] = self.uv_sets[uvset.name] = uvset

        for shell in self.shells.values():
            shell.material.shader = self.shader

    def dontBuild(self) -> bool:
        if self.ignore:
            return True
        elif self.force:
            return False
        elif Settings.reuseMaterials and self.name in bpy.data.materials.keys():
            self.rna = bpy.data.materials[self.name]
            return True
        elif self.geometry:
            return not self.geometry.isVisibleMaterial(self)
        return False

    def postbuild(self):
        if Settings.useMaterials_:
            self.guessColor()

    def guessColor(self):
        return

    def getUvKey(self, key: str, struct: Dict):
        if key not in struct.keys():
            print(
                f"Missing UV for '{self.getLabel()}', '{key}' not in {list(struct.keys())}")

        return key

    def getUvSet(self, uv):
        key = self.getUvKey(uv, self.uv_sets)
        if key is None:
            return self.uv_set
        elif key not in self.uv_sets.keys():
            uvset = Asset(None)
            uvset.name = key
            self.uv_sets[key] = uvset
        return self.uv_sets[key]

    def fixUdim(self, _, udim):
        mat = self.rna
        if mat is None:
            return

        try:
            mat.DazUDim = udim
        except ValueError:
            print("UDIM out of range: %d" % udim)

        mat.DazVDim = 0

        UDimStatic.add(mat, udim, 0)

    # @classmethod
    # def getGamma(cls, channel):
    #     url = cls.getImageFile(channel)
    #     # url = cls.channelsData.getImageFile(channel)

    #     gamma = 0
    #     if url in Settings.gammas_.keys():
    #         gamma = Settings.gammas_[url]
    #     elif "default_image_gamma" in channel.keys():
    #         gamma = channel["default_image_gamma"]

    #     return gamma

# -------------------------------------------------------------
#   Get channels
# -------------------------------------------------------------

    def getChannelDiffuse(self):
        return self.channelsData.get_channel("diffuse", "Diffuse Color")

    def getDiffuse(self):
        return self.getColor("getChannelDiffuse", ColorStatic.BLACK)

    def getChannelDiffuseStrength(self):
        return self.channelsData.getChannel(["diffuse_strength", "Diffuse Strength"])

    def getChannelDiffuseRoughness(self):
        return self.channelsData.getChannel(["Diffuse Roughness"])

    def getChannelGlossyColor(self):
        return self.getTexChannel(["Glossy Color", "specular", "Specular Color"])

    def getChannelGlossyLayeredWeight(self):
        return self.getTexChannel(["Glossy Layered Weight", "Glossy Weight", "specular_strength", "Specular Strength"])

    def getChannelGlossyReflectivity(self):
        return self.channelsData.get_channel("Glossy Reflectivity")

    def getChannelGlossyRoughness(self):
        return self.channelsData.get_channel("Glossy Roughness")

    def getChannelGlossySpecular(self):
        return self.channelsData.get_channel("Glossy Specular")

    def getChannelGlossiness(self):
        channel = self.channelsData.get_channel("glossiness", "Glossiness")
        if channel:
            return channel, False
        else:
            return self.channelsData.get_channel("Glossy Roughness"), True

    def getChannelOpacity(self):
        return self.channelsData.get_channel("opacity", "Opacity Strength")

    def getChannelCutoutOpacity(self):
        return self.channelsData.get_channel("Cutout Opacity", "transparency")

    def getChannelAmbientColor(self):
        return self.channelsData.getChannel(["ambient", "Ambient Color"])

    def getChannelAmbientStrength(self):
        return self.channelsData.getChannel(["ambient_strength", "Ambient Strength"])

    def getChannelEmissionColor(self):
        return self.channelsData.getChannel(["emission", "Emission Color"])

    def getChannelReflectionColor(self):
        return self.channelsData.getChannel(["reflection", "Reflection Color"])

    def getChannelReflectionStrength(self):
        return self.channelsData.getChannel(["reflection_strength", "Reflection Strength"])

    def getChannelRefractionColor(self):
        return self.channelsData.getChannel(["refraction", "Refraction Color"])

    def getChannelRefractionWeight(self):
        return self.channelsData.getChannel(["Refraction Weight", "refraction_strength"])

    def getChannelIOR(self):
        return self.channelsData.getChannel(["ior", "Refraction Index"])

    def getChannelTranslucencyWeight(self):
        return self.channelsData.getChannel(["translucency", "Translucency Weight"])

    def getChannelSSSColor(self):
        return self.channelsData.getChannel(["SSS Color", "Subsurface Color"])

    def getChannelSSSAmount(self):
        return self.channelsData.getChannel(["SSS Amount", "Subsurface Strength"])

    def getChannelSSSScale(self):
        return self.channelsData.getChannel(["SSS Scale", "Subsurface Scale"])

    def getChannelScatterDist(self):
        return self.channelsData.getChannel(["Scattering Measurement Distance"])

    def getChannelSSSIOR(self):
        return self.channelsData.getChannel(["Subsurface Refraction"])

    def getChannelTopCoatRoughness(self):
        return self.channelsData.getChannel(["Top Coat Roughness"])

    def getChannelNormal(self):
        return self.channelsData.getChannel(["normal", "Normal Map"])

    def getChannelBump(self):
        return self.channelsData.getChannel(["bump", "Bump Strength"])

    def getChannelBumpMin(self):
        return self.channelsData.getChannel(["bump_min", "Bump Minimum", "Negative Bump"])

    def getChannelBumpMax(self):
        return self.channelsData.getChannel(["bump_max", "Bump Maximum", "Positive Bump"])

    def getChannelDisplacement(self):
        return self.channelsData.getChannel(["displacement", "Displacement Strength"])

    def getChannelDispMin(self):
        return self.channelsData.getChannel(["displacement_min", "Displacement Minimum", "Minimum Displacement"])

    def getChannelDispMax(self):
        return self.channelsData.getChannel(["displacement_max", "Displacement Maximum", "Maximum Displacement"])

    def getChannelHorizontalTiles(self):
        return self.channelsData.getChannel(["u_scale", "Horizontal Tiles"])

    def getChannelHorizontalOffset(self):
        return self.channelsData.getChannel(["u_offset", "Horizontal Offset"])

    def getChannelVerticalTiles(self):
        return self.channelsData.getChannel(["v_scale", "Vertical Tiles"])

    def getChannelVerticalOffset(self):
        return self.channelsData.getChannel(["v_offset", "Vertical Offset"])

    def getColor(self, attr, default):
        return self.getChannelColor(self.channelsData.getChannel(attr), default)

    def getTexChannel(self, channels):
        for key in channels:
            channel = self.channelsData.get_channel(key)
            if channel and self.hasTextures(channel):
                return channel
        return self.channelsData.get_channel(*channels)

    def hasTexChannel(self, channels) -> bool:
        for key in channels:
            channel = self.channelsData.get_channel(key)
            if channel and self.hasTextures(channel):
                return True
        return False

    def getChannelColor(self, channel, default, warn=True):
        color = self.channelsData.getChannelValue(channel, default, warn)

        if isinstance(color, int) or isinstance(color, float):
            color = (color, color, color)

        if channel and channel["type"] == "color":
            return self.srgbToLinearCorrect(color)
        else:
            return self.srgbToLinearGamma22(color)

    @staticmethod
    def srgbToLinearCorrect(srgb) -> Vector:
        lin = []
        for s in srgb:
            if s < 0:
                l = 0
            elif s < 0.04045:
                l = s/12.92
            else:
                l = ((s+0.055)/1.055)**2.4

            lin.append(l)
        return Vector(lin)

    @staticmethod
    def srgbToLinearGamma22(srgb) -> Vector:
        lin = []
        for s in srgb:
            if s < 0:
                l = 0
            else:
                l = round(s**2.2, 6)
            lin.append(l)
        return Vector(lin)

    def getImageMod(self, attr, key: str):
        channel: dict = self.channelsData.get_channel(*attr)

        if not channel:
            return

        if mod := channel.get("image_modification", {}):
            return mod.get(key)

    def getTextures(self, channel: Dict) -> Tuple[List[Texture], List[Map]]:
        textures = []
        maps = []

        for map_ in self.get_maps(channel):
            if map_.url:
                # tex = map_.getTexture()
                tex = Texture.create(map_)
            elif map_.literal_image:
                tex = Texture(map_)
                tex.image = map_.literal_image

            if not tex:
                continue

            textures.append(tex)
            maps.append(map_)

        return textures, maps

    def hasTextures(self, channel) -> bool:
        return self.getTextures(channel)[0] != []

    def hasAnyTexture(self):
        for channel in self.channelsData.channels.values():
            if channel and self.getTextures(channel)[0]:
                return True
        return False

    def sssActive(self):
        if not self.enabled.get("Subsurface"):
            return False
        if self.refractive or self.thinWall:
            return False
        return True

    def get_maps(self, channel: Dict) -> List[Map]:
        if isinstance(channel, tuple):
            channel = channel[0]

        maps = []

        if channel is None:
            ...
        elif image := channel.get("image"):
            asset = self.get_children(url=image)
            if asset.maps:
                maps = asset.maps
        elif image_file := channel.get("image_file"):
            map_ = Map({}, False)
            map_.url = image_file
            maps = [map_]
        # elif "map" in channel.keys():
        #     maps = Maps(self.fileref)
        #     maps.parse(channel["map"])
        #     halt
        elif cache := channel.get("literal_image"):
            map_ = Map(channel, False)
            map_.image = cache
            maps = [map_]
        elif cache := channel.get("literal_maps"):
            for data in cache.get("map", []):
                if mask := data.get("mask"):
                    mask = Map(mask, True)
                    maps.append(mask)

                map_ = Map(data, False)
                maps.append(map_)

        return maps

    def get_enabled(self, shader: str) -> Dict:
        if shader == 'UBER_IRAY':
            return {
                "Diffuse": True,
                "Subsurface": True,
                "Bump": True,
                "Normal": True,
                "Displacement": True,
                "Metallicity": True,
                "Translucency": True,
                "Transmission": True,
                "Dual Lobe Specular": True,
                "Top Coat": True,
                "Makeup": False,
                "Specular Occlusion": False,
                "Detail": False,
                "Metallic Flakes": True,
                "Velvet": False,
            }
        elif shader == 'PBRSKIN':
            return {
                "Diffuse": self.channelsData.getValue(["Diffuse Enable"], False),
                "Subsurface": self.channelsData.getValue(["Sub Surface Enable"], False),
                "Bump": self.channelsData.getValue(["Bump Enable"], False),
                "Normal": self.channelsData.getValue(["Bump Enable"], False),
                "Displacement": True,
                "Metallicity": self.channelsData.getValue(["Metallicity Enable"], False),
                "Translucency": self.channelsData.getValue(["Translucency Enable"], False),
                "Transmission": self.channelsData.getValue(["Transmission Enable"], False),
                "Dual Lobe Specular": self.channelsData.getValue(["Dual Lobe Specular Enable"], False),
                "Top Coat": self.channelsData.getValue(["Top Coat Enable"], False),
                "Makeup": self.channelsData.getValue(["Makeup Enable"], False),
                "Specular Occlusion": self.channelsData.getValue(["Specular Occlusion Enable"], False),
                "Detail": self.channelsData.getValue(["Detail Enable"], False),
                "Metallic Flakes": self.channelsData.getValue(["Metallic Flakes Enable"], False),
                "Velvet": False,
            }
        elif shader == 'DAZ_SHADER':
            return {
                "Diffuse": self.channelsData.getValue(["Diffuse Active"], False),
                "Subsurface": self.channelsData.getValue(["Subsurface Active"], False),
                "Bump": self.channelsData.getValue(["Bump Active"], False),
                "Normal": False,
                "Displacement": self.channelsData.getValue(["Displacement Active"], False),
                "Metallicity": self.channelsData.getValue(["Metallicity Active"], False),
                "Translucency": self.channelsData.getValue(["Translucency Active"], False),
                "Transmission": not self.channelsData.getValue(["Opacity Active"], False),
                "Dual Lobe Specular": False,
                "Top Coat": False,
                "Makeup": False,
                "Specular Occlusion": False,
                "Detail": False,
                "Metallic Flakes": False,
                "Velvet": not self.channelsData.getValue(["Velvet Active"], False),
            }
        elif shader == '3DELIGHT':
            return {
                "Diffuse": True,
                "Subsurface": True,
                "Bump": True,
                "Normal": True,
                "Displacement": True,
                "Metallicity": False,
                "Translucency": True,
                "Transmission": True,
                "Dual Lobe Specular": False,
                "Top Coat": False,
                "Makeup": False,
                "Specular Occlusion": False,
                "Detail": False,
                "Metallic Flakes": False,
                "Velvet": True,
            }
        else:
            data = defaultdict()
            data.default_factory = lambda: False
            print('-- Undefined shader', shader)
            return data
