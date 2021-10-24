import bpy
import collections
import os

from daz_import.Elements.Assets import Assets
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Elements.Formula import Formula
from daz_import.Lib.Errors import ErrorsStatic
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Utility import UtilityStatic

from .Modifier import Modifier
from .static import *


class ChannelAsset(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)

        self.type = "float"
        self.value = 0
        self.min = None
        self.max = None

    def __repr__(self):
        return ("<Channel %s %s>" % (self.id, self.type))

    def parse(self, data: dict):
        super().parse(data)

        if not Settings.useMorph_:
            return

        for key, value in data.get("channel", {}).items():
            if key == "value":
                self.value = value
            elif key == "min":
                self.min = value
            elif key == "max":
                self.max = value
            elif key == "type":
                self.type = value

    def update(self, data):
        super().update(data)
        value = data.get("channel", {})
        value = value.get("current_value")

        if value is None:
            return
        self.value = value


class Alias(ChannelAsset):

    def __init__(self, fileref):
        ChannelAsset.__init__(self, fileref)
        self.alias = None
        self.parent = None
        self.value = 0.0

    def __repr__(self):
        return ("<Alias %s\n  %s>" % (self.id, self.alias))

    def parse(self, struct):
        ChannelAsset.parse(self, struct)
        channel = struct["channel"]
        #self.parent = self.getAsset(struct["parent"])
        self.alias = self.get_children(url=channel["target_channel"])

    def update(self, struct):
        if self.alias:
            self.alias.update(struct)
            if hasattr(self.alias, "value"):
                self.value = self.alias.value

    def build(self, context, inst):
        if self.alias:
            self.alias.build(context)


class SkinBinding(Modifier):

    def __init__(self, fileref):
        Modifier.__init__(self, fileref)

        self.parent = None
        self.skin = None

    def __repr__(self):
        return ("<SkinBinding %s>" % (self.id))

    def parse(self, data: dict):
        from daz_import.geometry import Geometry
        from daz_import.figure import Figure
        super().parse(data)

        self.skin = data.get("skin")
        self.parent = self.get_children(url=data.get('parent'))

        if not (isinstance(self.parent, Geometry) or
                isinstance(self.parent, Figure)):
            msg = "Parent of %s\nshould be a geometry or a figure but is\n%s" % (
                self, self.parent)
            ErrorsStatic.report(msg, trigger=(2, 3))

    def parseSource(self, url):
        asset = self.get_children(url=url)
        if not asset:
            return

        if (self.parent is None or
                self.parent.type != asset.type):
            msg = ("SkinBinding source bug:\n" +
                   "URL: %s\n" % url +
                   "Skin: %s\n" % self +
                   "Asset: %s\n" % asset +
                   "Parent: %s\n" % self.parent)
            ErrorsStatic.report(msg, trigger=(2, 3))

        if asset != self.parent:
            self.parent.source = asset
            asset.sourcing = self.parent

        Assets.push(self.parent, url)

    def build(self, context, inst):
        ob, rig, geonode = self.getGeoRig(context, inst)

        if ob is None or rig is None or ob.type != 'MESH':
            return

        if "selection_map" in self.skin.keys():
            selmap = self.skin["selection_map"]
            geonode.addMappings(selmap[0])

        makeArmatureModifier(self.name, context, ob, rig)
        self.addVertexGroups(ob, geonode, rig)
        hdob = geonode.hdobject

        if not (hdob and
                hdob != ob and
                hdob.DazMultires and
                Settings.useMultires):
            return

        hdob.parent = ob.parent
        makeArmatureModifier(self.name, context, hdob, rig)

        if len(hdob.data.vertices) == len(ob.data.vertices):
            copyVertexGroups(ob, hdob)
        else:
            Settings.hdWeights_.append(hdob.name)

    def addVertexGroups(self, ob, geonode, rig):
        bones = geonode.figure.bones

        for joint in self.skin.get("joints"):

            bname = joint["id"]

            if bname in bones.keys():
                vgname = bones[bname]
            else:
                vgname = bname

            weights = None

            if "node_weights" in joint.keys():
                weights = joint["node_weights"]

            elif "local_weights" in joint.keys():

                if bname in rig.data.bones.keys():
                    calc_weights = self.calcLocalWeights(bname, joint, rig)
                    weights = {"values": calc_weights}
                else:
                    print("Settings weights missing bone:", bname)

                    for comp in ["x", "y", "z"]:
                        if comp in joint["local_weights"].keys():
                            weights = joint["local_weights"][comp]
                            break
            elif "scale_weights" in joint.keys():
                weights = joint["scale_weights"]
            else:
                ErrorsStatic.report("No weights for %s in %s" %
                                    (bname, ob.name), trigger=(2, 5))
                continue

            buildVertexGroup(ob, vgname, weights["values"])

    def calcLocalWeights(self, bname, joint, rig):
        local_weights = joint["local_weights"]
        bone = rig.data.bones[bname]
        head = bone.head_local
        tail = bone.tail_local
        # find longitudinal axis of the bone and take the other two into consideration
        consider = []

        x_delta = abs(head[0] - tail[0])
        y_delta = abs(head[1] - tail[1])
        z_delta = abs(head[2] - tail[2])

        max_delta = max(x_delta, y_delta, z_delta)

        if x_delta < max_delta:
            consider.append("x")
        if y_delta < max_delta:
            consider.append("z")
        if z_delta < max_delta:
            consider.append("y")

        # create deques sorted in descending order
        weights = [collections.deque(local_weights[letter]["values"]) for letter in consider if
                   letter in local_weights]
        for w in weights:
            w.reverse()
        target = []
        calc_weights = []
        if len(weights) == 1:
            calc_weights = weights[0]
        elif len(weights) > 1:
            self.mergeWeights(weights[0], weights[1], target)
            calc_weights = target
        if len(weights) > 2:
            # this happens mostly with zero length bones
            calc_weights = []
            self.mergeWeights(target, weights[2], calc_weights)
        return calc_weights

    def mergeWeights(self, first, second, target):
        # merge the two local_weight groups and calculate arithmetic mean for vertices that are present in both groups

        while len(first) > 0 and len(second) > 0:
            a = first.pop()
            b = second.pop()

            if a[0] == b[0]:
                target.append([a[0], (a[1] + b[1]) / 2.0])
            elif a[0] < b[0]:
                target.append(a)
                second.append(b)
            else:
                target.append(b)
                first.append(a)

        while len(first) > 0:
            a = first.pop()
            target.append(a)

        while len(second) > 0:
            b = second.pop()
            target.append(b)


class LegacySkinBinding(SkinBinding):

    def __repr__(self):
        return ("<LegacySkinBinding %s>" % (self.id))

    def parse(self, struct):
        struct["skin"] = struct["legacy_skin"]
        SkinBinding.parse(self, struct)


class FormulaAsset(Formula, ChannelAsset):

    def __init__(self, fileref):
        ChannelAsset.__init__(self, fileref)
        Formula.__init__(self)
        # self.formulas_: Formula = self
        self.group = ""

    def __repr__(self):
        return ("<Formula %s %f>" % (self.id, self.value))

    def parse(self, struct):
        ChannelAsset.parse(self, struct)

        if not Settings.useMorphOnly_:
            return
        if "group" in struct.keys():
            words = struct["group"].split("/")
            if (len(words) > 2 and
                words[0] == "" and
                    words[1] == "Pose Controls"):
                self.group = words[2]

        Formula.parse(self, struct)

    def build(self, context, inst):
        if Settings.useMorphOnly_:
            Formula.build(self, context, inst)

    def postbuild(self, context, inst):
        if Settings.useMorphOnly_:
            Formula.postbuild(self, context, inst)


class Morph(FormulaAsset):

    def __init__(self, fileref):
        super().__init__(fileref)

        self.vertex_count = 0
        self.deltas = []
        self.hd_url = None

    def __repr__(self):
        return ("<Morph %s %f %d %d %s>" % (self.name, self.value, self.vertex_count, len(self.deltas), self.rna))

    def parse(self, data: dict):
        super().parse(data)

        if not Settings.useMorph_:
            return

        self.parent = data["parent"]
        morph = data.get("morph", {})

        deltas = morph.get("deltas", {})
        deltas = deltas.get("values", {})

        if deltas is not None:
            self.deltas = deltas
        else:
            print(f"Morph without deltas: {self.name}")

        if count := morph.get("vertex_count"):
            self.vertex_count = count

        if url := morph.get("hd_url"):
            self.hd_url = url

    def parseSource(self, _):
        ...

    def update(self, data: dict):
        from daz_import.geometry import GeoNode, Geometry
        from daz_import.figure import Figure, FigureInstance

        FormulaAsset.update(self, data)
        if not Settings.useMorph_:
            return

        parent = self.get_children(url=self.parent)

        if "parent" not in data.keys():
            return

        if isinstance(parent, Geometry):
            ref = UtilityStatic.inst_ref(data["parent"])

            if ref in parent.nodes:
                geonode = parent.nodes[ref]
            else:
                ErrorsStatic.report("Missing geonode %s in\n %s" %
                                    (ref, parent), trigger=(2, 4))
                return
        elif isinstance(parent, GeoNode):
            geonode = parent
        elif isinstance(parent, Figure) and parent.instances:
            ref = list(parent.instances.keys())[0]
            inst = parent.getInstance(ref, self.caller)
            geonode = inst.geometries[0]
        elif isinstance(parent, FigureInstance):
            geonode = parent.geometries[0]
        else:
            msg = ("Strange morph parent.\n  %s\n  %s" % (self, parent))
            return ErrorsStatic.report(msg)
        geonode.morphsValues[self.name] = self.value

    def build(self, context, inst, value=-1):
        from daz_import.geometry import GeoNode, Geometry
        from daz_import.figure import FigureInstance
        from daz_import.Elements.Bone import BoneInstance

        if not Settings.useMorph_:
            return self

        if len(self.deltas) == 0:
            print("Morph without deltas: %s" % self.name)
            return self

        Formula.build(self, context, inst)
        Modifier.build(self, context)

        if isinstance(inst, FigureInstance):
            geonodes = inst.geometries
        elif isinstance(inst, GeoNode):
            geonodes = [inst]
        elif isinstance(inst, BoneInstance):
            geonodes = inst.figure.geometries
        else:
            asset = self.get_children(url=self.parent)
            print("BMO", inst)
            print("  ", asset)
            inst = None

            if asset:
                geonodes = list(asset.nodes.values())
                if len(geonodes) > 0:
                    inst = geonodes[0]

        if inst is None:
            msg = ("Morph not found:\n  %s\n  %s\n  %s" %
                   (self.id, self.parent, asset))
            ErrorsStatic.report(msg, trigger=(2, 3))
            return None

        for geonode in geonodes:
            ob = geonode.rna

            if value >= 0:
                self.value = value
                if self not in geonode.modifiers:
                    geonode.modifiers.append(self)
                geonode.morphsValues[self.name] = value
            elif self.name in geonode.morphsValues.keys():
                self.value = geonode.morphsValues[self.name]
            else:
                if Settings.verbosity > 3:
                    print("MMMO", self.name)
                    print("  ", geonode)
                    print("  ", geonode.morphsValues.keys())
                self.value = 0.0

            if ob is None:
                continue
            elif Settings.applyMorphs_:
                self.addMorphToVerts(ob.data)
            elif self.value > 0.0:
                self.buildMorph(ob, strength=Settings.morphStrength_)

        return self

    def addMorphToVerts(self, me):
        if self.value == 0.0:
            return
        scale = self.value * Settings.scale_
        for delta in self.deltas:
            vn = delta[0]
            me.vertices[vn].co += scale * VectorStatic.create_vector(delta[1:])

    def buildMorph(self, ob, useBuild=True, strength=1):
        sname = self.getName()

        rig = ob.parent
        skey = addShapekey(ob, sname)
        skey.value = self.value
        self.rna = (skey, ob, sname)

        if useBuild:
            self.__buildShapeKey(ob, skey, strength)

    def __buildShapeKey(self, ob, skey, strength):
        if strength != 1:
            scale = Settings.scale_
            Settings.scale_ *= strength
        
        for v in ob.data.vertices:
            skey.data[v.index].co = v.co

        if Settings.zup:

            if isModifiedMesh(ob):
                pgs = ob.data.DazOrigVerts
                for delta in self.deltas:
                    vn0 = delta[0]
                    vn = pgs[str(vn0)].a
                    if vn >= 0:
                        skey.data[vn].co += VectorStatic.scaled_v2(
                            delta[1:])
            else:
                for delta in self.deltas:
                    vn = delta[0]
                    skey.data[vn].co += VectorStatic.scaled_v2(delta[1:])
        else:
            for delta in self.deltas:
                vn = delta[0]
                skey.data[vn].co += VectorStatic.scaled_and_convert_vector(
                    delta[1:])

        if strength != 1:
            Settings.scale_ = scale
