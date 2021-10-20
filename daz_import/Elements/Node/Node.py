import bpy
# import math
from urllib.parse import unquote

from mathutils import Vector
from daz_import.Elements.Formula import Formula

from daz_import.Elements.Assets import Asset, Assets
from daz_import.Lib.Settings import Settings
from daz_import.Elements.Assets.Channels import Channels
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Utility import UtilityStatic
from daz_import.Lib.Errors import ErrorsStatic
from .NodeStatic import *
from .Instance import Instance


class Node(Asset, Formula):

    def __init__(self, fileref):
        Asset.__init__(self, fileref)
        Formula.__init__(self)
        
        self.formulaData: Formula = self
        self.channelsData: Channels = Channels(self)

        self.instances = {}
        self.ninstances = 0
        self.count = 0

        self.data = None
        self.center = None
        self.geometries = []

        self.rotation_order = 'XYZ'

        self.attributes = self.defaultAttributes()
        self.origAttrs = self.defaultAttributes()
        self.figure = None
        self.rigtype = ""

    def defaultAttributes(self):
        return {
            "center_point": Vector((0, 0, 0)),
            "end_point": Vector((0, 0, 0)),
            "orientation": Vector((0, 0, 0)),
            "translation": Vector((0, 0, 0)),
            "rotation": Vector((0, 0, 0)),
            "scale": Vector((1, 1, 1)),
            "general_scale": 1
        }

    def clearTransforms(self):
        default = self.defaultAttributes()
        for key in ["translation", "rotation", "scale", "general_scale"]:
            self.attributes[key] = default[key]

    def __repr__(self):
        pid = (self.parent.id if self.parent else None)
        return ("<Node %s %s P: %s Settings: %s>" % (self.id, self.label, pid, self.geometries))

    def errorWrite(self, ref, fp):
        Asset.errorWrite(self, ref, fp)
        for iref, inst in self.instances.items():
            inst.errorWrite(iref, fp)

    def postTransform(self):
        ...

    def makeInstance(self, fileref, struct):
        return Instance(fileref, self, struct)

    def getInstance(self, ref, caller=None):
        if caller is None:
            caller = self

        iref = UtilityStatic.inst_ref(ref)

        if iref in caller.instances.keys():
            return caller.instances[iref]

        iref = unquote(iref)

        if iref in caller.instances.keys():
            return caller.instances[iref]
        else:
            msg = ("Node: Did not find instance %s in %s" % (iref, caller))
            insts = caller.instances
            ErrorsStatic.report(msg, insts, trigger=(2, 4))

        return None

    def parse(self, data: dict):
        Asset.parse(self, data)
        self.channelsData.parse(data)

        for key, data in data.items():
            if key == "formulas":
                self.formulaData.formulas = data
            elif key == "inherits_scale":
                ...
            elif key == "rotation_order":
                self.rotation_order = data
            elif key in self.attributes.keys():
                self.setAttribute(key, data)

        for key in self.attributes.keys():
            self.origAttrs[key] = self.attributes[key]

        return self

    def setExtra(self, extra):
        ...

    Indices = {"x": 0, "y": 1, "z": 2}

    def setAttribute(self, channel, data):
        if isinstance(data, list):
            for comp in data:
                idx = self.Indices[comp["id"]]
                value = UtilityStatic.get_current_value(comp)
                if value is not None:
                    self.attributes[channel][idx] = value
        else:
            self.attributes[channel] = UtilityStatic.get_current_value(data)

    def update(self, data: dict):
        from daz_import.geometry import GeoNode

        Asset.update(self, data)
        self.channelsData.update(data)

        for channel, inner_data in data.items():
            if channel == "geometries":

                for geostruct in inner_data:
                    if "url" in geostruct.keys():
                        geo = self.get_children(data=geostruct, key='Geometry')
                        geonode = GeoNode(self, geo, geostruct["id"])
                    else:
                        print("No geometry URL")
                        geonode = GeoNode(self, None, geostruct["id"])
                        Assets.save(self, geostruct, geonode)

                    geonode.parse(geostruct)
                    geonode.update(geostruct)

                    geonode.channelsData.extra = self.channelsData.extra
                    self.geometries.append(geonode)

            elif channel in self.attributes.keys():
                self.setAttribute(channel, inner_data)

        if Settings.useMorph_ and "preview" in data.keys():
            preview = data["preview"]
            pcenter = Vector(preview["center_point"])
            pend = Vector(preview["end_point"])
            bcenter = self.attributes["center_point"]
            bend = self.attributes["end_point"]
            self.attributes["center_point"] = bcenter + \
                Settings.morphStrength_*(pcenter-bcenter)
            self.attributes["end_point"] = bend + \
                Settings.morphStrength_*(pend-bend)

        self.count += 1

    def build(self, context, inst):
        center = VectorStatic.scaled(inst.attributes["center_point"])

        if inst.ignore:
            print("Ignore", inst)
        elif inst.geometries:
            for geonode in inst.geometries:
                geonode.buildObject(context, inst, center)
                inst.rna = geonode.rna
        else:
            self.buildObject(context, inst, center)

        if inst.channelsData.extra:
            inst.buildExtra(context)

    def buildObject(self, context, inst, center):
        # scn = context.scene

        if isinstance(self.data, Asset):
            if self.data.shstruct and Settings.mergeShells:
                return
            ob = self.data.buildData(context, self, inst, center)
            if not isinstance(ob, bpy.types.Object):
                ob = bpy.data.objects.new(inst.name, self.data.rna)
        else:
            ob = bpy.data.objects.new(inst.name, self.data)

        self.rna = inst.rna = ob
        Settings.objects_[Settings.rigname_].append(ob)

        self.arrangeObject(ob, inst, context, center)
        self.subdivideObject(ob, inst, context)

    def arrangeObject(self, ob, inst, _, center):
        blenderRotMode = {
            'XYZ': 'XZY',
            'XZY': 'XYZ',
            'YXZ': 'ZXY',
            'YZX': 'ZYX',
            'ZXY': 'YXZ',
            'ZYX': 'YZX',
        }

        ob.rotation_mode = blenderRotMode[self.rotation_order]

        ob.DazRotMode = self.rotation_order
        ob.DazMorphPrefixes = False

        inst.collection.objects.link(ob)

        ob.DazId = self.id
        ob.DazUrl = unquote(self.url)
        ob.DazScene = Settings.scene_
        ob.DazScale = Settings.scale_
        ob.DazOrient = inst.attributes["orientation"]

        self.subtractCenter(ob, inst, center)

    def subtractCenter(self, ob, inst, center):
        ob.location = -center
        inst.center = center

    def subdivideObject(self, ob, inst, context):
        ...
