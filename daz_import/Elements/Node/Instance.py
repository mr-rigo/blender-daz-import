import bpy
import math

from mathutils import Matrix, Vector, Euler

from daz_import.Collection import DazPath
from daz_import.Elements.Assets import Accessor
from daz_import.Elements.Assets.Asset import Asset
from daz_import.Lib.Settings import Settings
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Elements.Assets.Channels import Channels
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Utility import UtilityStatic
from .NodeStatic import NodeStatic
from .Dupli import Dupli


class Instance(Accessor):

    U3 = Matrix().to_3x3()

    def __init__(self, fileref, node, data: dict):
        super().__init__(fileref)
        self.channelsData: Channels = Channels(self)

        self.dyngenhair = None
        self.dynsim = None
        self.dynhairflw = None
        self.lintess = None
        self.simsets = []

        self.node = node
        self.index = node.ninstances
        node.ninstances += 1

        self.figure = None

        self.id = DazPath.normalize(data["id"])
        self.id = self.getSelfId()

        self.label = node.label
        node.label = None

        self.name = node.getLabel(self)

        node.instances[self.id] = self
        node.instances[self.name] = self

        self.geometries = node.geometries
        node.geometries = []

        self.rotation_order = node.rotation_order
        self.collection = Settings.collection_

        self.parent: Asset = None

        if parent := data.get("parent"):
            if node.parent is not None:
                self.parent = node.parent.getInstance(parent, node.caller)
                if self.parent == self:
                    print("Self-parent", self)
                    self.parent = None
                if self.parent:
                    self.parent.children[self.id] = self
                    self.collection = self.parent.collection
        node.parent = None

        self.children = {}
        self.target = None

        if target := data.get("target"):
            self.target = target

        self.visible = node.visible
        node.visible = True

        self.channelsData.extra = node.channelsData.extra
        node.channelsData.extra = []

        self.channelsData.channels = node.channelsData.channels
        node.channelsData.channels = {}

        self.shstruct = {}
        self.center = Vector((0, 0, 0))
        self.cpoint = Vector((0, 0, 0))

        self.wmat = self.wrot = self.wscale = Matrix()
        self.refcoll = None

        self.isGroupNode = False
        self.isStrandHair = False

        self.ignore = False
        self.isNodeInstance = False
        self.node2 = None
        self.hdobject = None
        self.modifiers = {}

        self.attributes = NodeStatic.copyElements(node.attributes)
        self.restdata = None
        self.wsmat = self.U3
        self.lsmat = None
        self.rigtype = node.rigtype
        node.clearTransforms()

    def __repr__(self):
        pname = (self.parent.id if self.parent else None)
        return "<Instance %s %d N: %s P: %s R: %s>" % (self.label, self.index, self.node.name, pname, self.rna)

    def errorWrite(self, ref, fp):
        fp.write('  "%s": %s\n' % (ref, self))
        for geonode in self.geometries:
            geonode.errorWrite("     ", fp)

    def getSelfId(self):
        return self.id

    def isMainFigure(self, _):
        par = self.parent

        while par and not par.is_instense('FigureInstance'):
            par = par.parent

        return par is None

    def preprocess(self, context):
        self.updateMatrices()
        for channel in self.channelsData.channels.values():
            if "type" not in channel.keys():
                continue
            elif channel["type"] == "node" and "node" in channel.keys():
                ref = channel["node"]
                node = self.get_children(url=ref)
                if node:
                    self.node2 = node.getInstance(ref)
            elif channel["type"] == "bool":
                words = channel["id"].split("_")
                if len(words) > 2 and words[1] == "group" and words[-1] == "vis":
                    if words[0] == "material" and "label" in channel.keys():
                        label = channel["label"]
                        value = UtilityStatic.get_current_value(channel)
                        for geonode in self.geometries:
                            geonode.data.material_group_vis[label] = value
                    elif words[0] == "facet":
                        pass

        for extra in self.channelsData.extra:
            if "type" not in extra.keys():
                continue
            elif extra["type"] == "studio/node/shell":
                self.shstruct = extra
            elif extra["type"] == "studio/node/group_node":
                self.isGroupNode = True
            elif extra["type"] == "studio/node/instance":
                self.isNodeInstance = True
            elif extra["type"] == "studio/node/strand_hair":
                self.isStrandHair = True
                for geonode in self.geometries:
                    geonode.isStrandHair = True
            elif extra["type"] == "studio/node/environment":
                self.ignore = True
            elif extra["type"] == "studio/node/tone_mapper":
                self.ignore = True

        for geonode in self.geometries:
            geonode.preprocess(context, self)

    def preprocess2(self, _):
        if self.isGroupNode:
            coll = bpy.data.collections.new(name=self.label)
            self.collection.children.link(coll)
            self.collection = coll
            self.groupChildren(self.collection)

    def groupChildren(self, coll):
        for child in self.children.values():
            child.collection = coll
            child.groupChildren(coll)

    def buildChannels(self, ob):
        for channel in self.channelsData.channels.values():
            if self.ignoreChannel(channel):
                continue
            key = channel["id"]
            value = UtilityStatic.get_current_value(channel)
            if key == "Visible in Viewport":
                self.hideViewport(value, ob)
            elif key == "Renderable":
                self.hideRender(value, ob)
            elif key == "Visible":
                self.hideViewport(value, ob)
                self.hideRender(value, ob)
            elif key == "Selectable":
                self.hideSelect(value, ob)
            elif key == "Visible in Simulation":
                ob.DazCollision = value
            elif key == "Cast Shadows":
                pass
            elif key == "Instance Mode":
                #print("InstMode", ob.name, value)
                pass
            elif key == "Instance Target":
                #print("InstTarg", ob.name)
                pass
            elif key == "Point At":
                pass

    def hideViewport(self, value, ob):
        if not (value or Settings.showHiddenObjects):
            ob.hide_set(True)
            for geonode in self.geometries:
                if geonode.rna:
                    geonode.rna.hide_set(True)

    def hideRender(self, value, ob):
        if not (value or Settings.showHiddenObjects):
            ob.hide_render = True
            for geonode in self.geometries:
                if geonode.rna:
                    geonode.rna.hide_render = True

    def hideSelect(self, value, ob):
        if not (value or Settings.showHiddenObjects):
            ob.hide_select = True
            for geonode in self.geometries:
                if geonode.rna:
                    geonode.rna.hide_select = True

    def ignoreChannel(self, channel):
        return ("id" not in channel.keys() or
                ("visible" in channel.keys() and not channel["visible"]))

    def buildExtra(self, _):
        for extra in self.channelsData.extra:
            if "type" not in extra.keys():
                continue
            elif extra["type"] == "studio/node/environment":
                if Settings.useWorld_ != 'NEVER':
                    if not Settings.render_:
                        from daz_import.Elements.Render.RenderOptions import RenderOptions
                        
                        Settings.render_ = RenderOptions(self.fileref)
                        Settings.render_.channelsData.channels = self.channelsData.channels
                    else:
                        Settings.render_.channelsData.copy(self.channelsData)

    def postbuild(self, context):
        self.parentObject(context, self.rna)
        for geonode in self.geometries:
            geonode.postbuild(context, self)

    def buildInstance(self, context):
        if self.isNodeInstance and Settings.useInstancing:
            if self.node2 is None:
                print('Instance "%s" has no node' % self.name)
            elif self.rna is None:
                print('Instance "%s" has not been built' % self.name)
            elif self.rna.type != 'EMPTY':
                print('Instance "%s" is not an empty' % self.name)
            elif self.node2.rna is None:
                ...
                # print('Instance "%s" node2 "%s" not built' %
                #       (inst.name, inst.node2.name))
            else:
                self.buildNodeInstance(context)

    def buildNodeInstance(self, context):
        parent = self.node2
        ob = parent.rna
        if parent.refcoll:
            refcoll = parent.refcoll
        else:
            refcoll = self.getInstanceColl(ob)
        if refcoll is None:
            refcoll = self.makeNewRefColl(context, ob, parent.collection)
            parent.refcoll = refcoll
        empty = self.rna
        empty.instance_type = 'COLLECTION'
        empty.instance_collection = refcoll
        NodeStatic.addToCollection(empty, parent.collection)

    def makeNewRefColl(self, context, ob, parcoll):
        refname = ob.name + " REF"
        refcoll = bpy.data.collections.new(name=refname)
        if Settings.refColls_ is None:
            Settings.refColls_ = bpy.data.collections.new(
                name=Settings.collection_.name + " REFS")
            context.scene.collection.children.link(Settings.refColls_)
        Settings.refColls_.children.link(refcoll)
        Settings.duplis_[refname] = Dupli(ob, refcoll, parcoll)
        return refcoll

    def getInstanceColl(self, ob):
        if ob.instance_type == 'COLLECTION':
            # for ob1 in ob.instance_collection.objects:
            #    coll = self.getInstanceColl(ob1)
            #    if coll:
            #        return coll
            return ob.instance_collection
        return None

    def poseRig(self, context):
        pass

    def finalize(self, context):
        ob = self.rna
        if ob is None:
            return
        for geonode in self.geometries:
            geonode.finalize(context, self)
        self.buildChannels(ob)
        if self.dynsim:
            self.dynsim.build(context)
        if self.dyngenhair:
            self.dyngenhair.build(context)
        if self.dynhairflw:
            self.dynhairflw.build(context)

    def formulate(self, key, value):
        pass

    def updateMatrices(self):
        # From http://docs.daz3d.com/doku.php/public/dson_spec/object_definitions/node/start
        #
        # center_offset = center_point - parent.center_point
        # global_translation = parent.global_transform * (center_offset + translation)
        # global_rotation = parent.global_rotation * orientation * rotation * (orientation)-1
        # global_scale for nodes that inherit scale = parent.global_scale * orientation * scale * general_scale * (orientation)-1
        # global_scale for nodes = parent.global_scale * (parent.local_scale)-1 * orientation * scale * general_scale * (orientation)-1
        # global_transform = global_translation * global_rotation * global_scale

        trans = VectorStatic.scaled_and_convert_vector(
            self.attributes["translation"])
        rotation = Vector(self.attributes["rotation"])*VectorStatic.D
        genscale = self.attributes["general_scale"]
        scale = Vector(self.attributes["scale"]) * genscale
        orientation = Vector(self.attributes["orientation"])*VectorStatic.D
        self.cpoint = VectorStatic.scaled_and_convert_vector(
            self.attributes["center_point"])

        lrot = Euler(rotation, self.rotation_order).to_matrix().to_4x4()

        self.lscale = Matrix()
        for i in range(3):
            self.lscale[i][i] = scale[i]

        orient = Euler(orientation).to_matrix().to_4x4()

        par = self.parent
        if par:
            coffset = self.cpoint - self.parent.cpoint
            self.wtrans = par.wmat @ (coffset + trans)
            self.wrot = par.wrot @ orient @ lrot @ orient.inverted()
            oscale = orient @ self.lscale @ orient.inverted()
            if True:  # self.inherits_scale:
                self.wscale = par.wscale @ oscale
            else:
                self.wscale = par.wscale @ par.lscale.inverted() @ oscale
        else:
            self.wtrans = self.cpoint + trans
            self.wrot = orient @ lrot @ orient.inverted()
            self.wscale = orient @ self.lscale @ orient.inverted()

        transmat = Matrix.Translation(self.wtrans)
        self.wmat = transmat @ self.wrot @ self.wscale
        if Settings.zup:
            self.worldmat = self.RXP @ self.wmat @ self.RXN
        else:
            self.worldmat = self.wmat

    RXP = Matrix.Rotation(math.pi/2, 4, 'X')
    RXN = Matrix.Rotation(-math.pi/2, 4, 'X')

    def parentObject(self, _, ob: Asset):
        if ob is None:
            return

        if self.parent is None:
            ob.parent = None
        elif self.parent.rna == ob:
            print("Warning: Trying to parent %s to itself" % ob)
            ob.parent = None
        elif self.parent.is_instense('FigureInstance'):
            for geonode in self.geometries:
                geonode.setHideInfo()
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        elif self.parent.is_instense('BoneInstance'):
            if self.parent.figure is None:
                print("No figure found:", self.parent)
                return
            rig = self.parent.figure.rna
            ob.parent = rig
            bname = self.parent.node.name
            if bname in rig.pose.bones.keys():
                ob.parent_bone = bname
                ob.parent_type = 'BONE'
        elif self.parent.is_instense('Instance'):
            ob.parent = self.parent.rna
            ob.parent_type = 'OBJECT'
        else:
            raise RuntimeError("Unknown parent %s %s" % (self, self.parent))

        BlenderStatic.world_matrix(ob, self.worldmat)
        self.node.postTransform()

    def getLocalMatrix(self, wsmat, orient):
        # global_rotation = parent.global_rotation * orientation * rotation * (orientation)-1
        lsmat = self.wsmat = wsmat
        if self.parent:
            try:
                lsmat = self.parent.wsmat.inverted() @ wsmat
            except ValueError:
                print("Failed to invert parent matrix")
        return orient.inverted() @ lsmat @ orient
