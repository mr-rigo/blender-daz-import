from __future__ import annotations
from mathutils import Vector, Matrix
from typing import Dict, Any, List, Tuple
from daz_import.Lib.Settings import Settings
from .Asset import Asset
from .Assets import Assets
from .Accessor import Accessor

from daz_import.Lib.Files.Json import Json
from daz_import.Collection import Collection, DazPath

from copy import deepcopy


class FileAsset(Asset):

    def __init__(self, fileref, toplevel: bool):
        from daz_import.Elements.Modifier import Morph
        from daz_import.geometry import Uvset
        from daz_import.Elements.Node import Node, Instance
        from daz_import.Elements.Material import Material

        super().__init__(fileref)

        self.nodes: List[Tuple[Node, Instance]] = []
        self.modifiers: List[Tuple[Morph, Instance]] = []
        self.uvs: List[Uvset] = []
        self.materials: List[Material] = []
        self.animations: List[Asset] = []
        self.instances: Dict[str, Node] = {}
        self.toplevel = toplevel

        self.caller = None
        self.camera = None

        if toplevel:
            self.caller = self

    def __repr__(self):
        return ("<File %s>" % self.id)

    def parse(self, data: Dict[str: Any]):
        # return AssetParser.parse_file(self, data)
        msg = ("+FILE %s" % self.fileref)

        Settings.theTrace_.append(msg)

        if Settings.verbosity > 4:
            print(msg)

        if info := data.get("asset_info"):
            super().parse(info)

        if Settings.useUV_:
            for ustruct in data.get("uv_set_library", []):
                asset = self.get_children(data=ustruct, key='Uvset')
                self.uvs.append(asset)

        if Settings.useGeometries_:
            for gstruct in data.get("geometry_library", []):
                asset = self.get_children(data=gstruct, key='Geometry')

        if Settings.useNodes_:
            for nstruct in data.get("node_library", []):
                asset = self.parse_node(self, nstruct)

        if Settings.useModifiers_:
            for mstruct in data.get("modifier_library", []):
                asset = self.parse_modifier(mstruct)

        if Settings.useImages_:
            for mstruct in data.get("image_library", []):
                asset = self.get_children(data=mstruct, key='Images')

        if Settings.useMaterials_:
            for mstruct in data.get("material_library", []):
                asset = self.get_children(data=mstruct, key='CyclesMaterial')

        scene: dict = data.get("scene", {})

        for nstruct in scene.get("nodes", []):
            asset = self.get_children(data=nstruct)

            if not asset or asset.is_instense('Geometry'):
                print(f"Bug: expected node not geometry {asset}")
                continue

            inst = asset.makeInstance(self.fileref, nstruct)
            self.instances[inst.id] = inst
            self.nodes.append((asset, inst))

        if Settings.useMaterials_:
            for mstruct in scene.get("materials", []):
                asset = self.create_by_key('CyclesMaterial', self.fileref)
                asset.parse(mstruct)

                if url := mstruct.get('url'):
                    if base := self.get_children(url=url):
                        asset.channelsData.channels = deepcopy(
                            base.channelsData.channels)

                asset.update(mstruct)
                self.materials.append(asset)

        if Settings.useModifiers_:
            for mstruct in scene.get("modifiers", []):
                asset = self.get_children(data=mstruct)
                if asset is None:
                    continue

                inst = None
                if par_dict := mstruct.get("parent"):
                    if par := self.get_children(url=par_dict):
                        inst = par.getInstance(par_dict, self)

                self.modifiers.append((asset, inst))

        if self.toplevel:
            self.parseRender(scene)

        msg = f"-FILE {self.fileref}"

        Settings.theTrace_.append(msg)

        if Settings.verbosity > 4:
            print(msg)

        return self

    def makeLocalNode(self, struct: dict):
        preview = struct.get("preview")

        if not preview:
            return

        key = 'Node'
        classes = {"figure": 'Figure', "bone": 'Bone'}

        for type_key, class_key in classes.items():
            if preview["type"] != type_key:
                continue
            key = class_key

        asset = self.create_by_key(key, self.fileref)

        head = asset.attributes["center_point"] = Vector(
            preview["center_point"])

        tail = asset.attributes["end_point"] = Vector(preview["end_point"])
        xaxis = (tail-head).normalized()
        yaxis = Vector((0, 1, 0))
        zaxis = -xaxis.cross(yaxis).normalized()
        omat = Matrix((xaxis, yaxis, zaxis)).transposed()

        orient = Vector(omat.to_euler())
        tail = asset.attributes["orientation"] = orient
        asset.rotation_order = preview["rotation_order"]

        asset.parse(struct)
        asset.update(struct)

        Assets.save(self, struct, asset)

        if url := struct.get('struct'):
            Assets.push(asset, url)

        if geos := struct.get("geometries"):
            geos: Dict
            
            for n, geonode in enumerate(asset.geometries):
                Assets.push(geonode, geonode.id)
                inst = geonode.makeInstance(self.fileref, geos[n])
                self.instances[inst.id] = inst
                self.nodes.append((geonode, inst))

                geo = geonode.data

                if not geo:
                    continue

                for mname in geo.polygon_material_groups:
                    ref = self.fileref + "#" + mname

                    dmat = self.get_children(url=ref)

                    if dmat and dmat not in self.materials:
                        self.materials.append(dmat)

        return asset

    def parseRender(self, scene):
        if "current_camera" in scene.keys():
            self.camera = self.get_children(url=scene["current_camera"])

        backdrop = {}

        if "backdrop" in scene.keys():
            backdrop = scene["backdrop"]

        if "extra" in scene.keys():
            sceneSettings = renderSettings = {}
            for extra in scene["extra"]:
                if extra["type"] == "studio_scene_settings":
                    sceneSettings = extra
                elif extra["type"] == "studio_render_settings":
                    renderSettings = extra
            if renderSettings:
                from daz_import.Elements.Render import RenderStatic

                RenderStatic.parse_options(renderSettings,
                                           sceneSettings,
                                           backdrop,
                                           self.fileref)

    def build(self, context):
        print("BUILD FILE?", self)        
        for asset in self.assets:
            if asset.type == "figure":
                asset.build(context)

    def parse_modifier(self, data: Dict) -> Asset:
        classes = {
            "skin": 'SkinBinding',
            "legacy_skin": 'LegacySkinBinding',
            "morph": 'Morph',
            "formulas": 'FormulaAsset',
            "dform": 'DForm',
            "extra": 'ExtraAsset'
        }

        for key, type_key in classes.items():
            if key not in data.keys():
                continue

            return self.get_children(data=data, key=type_key)

        if "channel" in data.keys():
            return self.parse_channel(data)

        #print("WARNING: Modifier asset %s not implemented" % asset.fileref)
        #asset = Modifier(asset.fileref)
        raise NotImplementedError(
            f"Modifier asset not implemented in file {self.fileref}:\n  {list(data.keys())}")

    def parse_channel(self, data: dict) -> Asset:
        key_type = data.get('channel', {}).get("type")

        if key_type == "alias":
            key = 'Alias'
        else:
            key = 'ChannelAsset'
        return self.get_children(data=data, key=key)

    @classmethod
    def parse_morph(cls, asset: Asset, data: dict):
        for inner_data in data.get("modifier_library", []):
            if "morph" in inner_data.keys():
                return asset.get_children(data=inner_data, key='Morph')
            elif "formulas" in inner_data.keys():
                return asset.get_children(data=inner_data, key='FormulaAsset')
            elif "channel" in inner_data.keys():
                return cls.parse_channel(asset, inner_data)

    @classmethod
    def parse_node(cls, asset: Asset, struct: dict):
        classes = {
            "figure": 'Figure',
            "legacy_figure": 'LegacyFigure',
            "bone": 'Bone',
            "node": 'Node',
            "camera": 'Camera',
            "light": 'Light'
        }

        type_key = struct.get("type")
        for key, class_key in classes.items():
            if type_key == key:
                return asset.get_children(data=struct, key=class_key)

        print("Not implemented node asset type type_key")
        #raise NotImplementedError(msg)
        return None

    @classmethod
    def create_by_url(cls, url: str, toplevel=False, fileref=None) -> FileAsset:
        return cls.parse_file(Json.load(url),
                              toplevel=toplevel,
                              fileref=fileref)

    @classmethod
    def parse_file(cls, dict_: dict, toplevel=False, fileref=None) -> Accessor:
        if fileref is None and "asset_info" in dict_.keys():
            ainfo = dict_["asset_info"]

            if "id" in ainfo.keys():
                fileref = DazPath.id(ainfo["id"], "")

        if fileref is None:
            return None

        asset = Assets.get_direct(DazPath.normalize(fileref))

        if asset is None:
            asset = cls.create_by_key('FileAsset', fileref, toplevel)
            Assets.push(asset, fileref)

        if asset is None:
            return None
        elif Settings.useMorphOnly_:
            return cls.parse_morph(asset, dict_)
        else:
            return asset.parse(dict_)

    @classmethod
    def get_new(cls, id_: str, ref: str, strict=True):  # -> Asset
        fileref = id_.split("#")[0]
        filepath = Collection.path(fileref)
        file = None

        if filepath:
            file = FileAsset.create_by_url(filepath, fileref=fileref)
            if asset_ := Assets.get_direct(ref):
                return asset_
        else:
            ref = DazPath.unquote(fileref)
            if ref.startswith("name:/@selection"):
                return None
            msg = ("Cannot open file:\n '%s'            " % ref)
            # ErrorsStatic.report(msg, warnPaths=True, trigger=(3, 4))
            return None

        Settings.missingAssets_[ref] = True

        if strict and Settings.useStrict:
            msg = ("Missing asset:\n  '%s'\n" % ref +
                   "Fileref\n   %s\n" % fileref +
                   "Filepath:\n  '%s'\n" % filepath +
                   "File asset:\n  %s\n" % file)
            # ErrorsStatic.report(msg, warnPaths=True, trigger=(3, 4))
        return None
