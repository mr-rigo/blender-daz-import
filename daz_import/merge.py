import os
import json
import bpy

from daz_import.utils import *
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.Elements.Material.Operators import MaterialMerger
from daz_import.driver import DriverUser
from daz_import.Lib import Registrar

# -------------------------------------------------------------
#   Merge geografts
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_MergeGeografts(DazPropsOperator, MaterialMerger, DriverUser):
    pool = IsMesh.pool
    
    bl_idname = "daz.merge_geografts"
    bl_label = "Merge Geografts"
    bl_description = "Merge selected geografts to active object"
    bl_options = {'UNDO'}

    useMergeUvLayers: BoolProperty(
        name="Merge UV Layers",
        description="Merge active render UV layers to a single layer",
        default=True)

    useVertexTable: BoolProperty(
        name="Add Vertex Table",
        description=(
            "Add a table with vertex numbers before and after merge.\n" +
            "Makes it possible to add morphs after merge,\n" +
            "but affects viewport performance"),
        default=True)

    def draw(self, context):
        self.layout.prop(self, "useMergeUvLayers")
        self.layout.prop(self, "useVertexTable")

    def __init__(self):
        DriverUser.__init__(self)

    def run(self, context):
        from daz_import.Elements.Finger import isCharacter
        cob = context.object
        ncverts = len(cob.data.vertices)
        chars = {ncverts: cob}
        prio = {ncverts: False}
        for ob in BlenderStatic.selected_meshes(context):
            nverts = len(ob.data.vertices)
            if nverts not in chars.keys() or isCharacter(ob):
                chars[nverts] = ob
                prio[nverts] = (not (not ob.data.DazGraftGroup))

        grafts = dict([(ncverts, []) for ncverts in chars.keys()])
        ngrafts = 0
        for aob in BlenderStatic.selected_meshes(context):
            if aob.data.DazGraftGroup:
                ncverts = aob.data.DazVertexCount
                if ncverts in grafts.keys():
                    grafts[ncverts].append(aob)
                    ngrafts += 1
                else:
                    print("No matching mesh found for geograft %s" % aob.name)
        if ngrafts == 0:
            raise DazError("No geograft selected")

        for ncverts, cob in chars.items():
            if prio[ncverts]:
                self.mergeGeografts(context, ncverts, cob, grafts[ncverts])
        for ncverts, cob in chars.items():
            if not prio[ncverts]:
                self.mergeGeografts(context, ncverts, cob, grafts[ncverts])

    def mergeGeografts(self, context, ncverts, cob, anatomies):
        if not anatomies:
            return
        try:
            cob.data
        except ReferenceError:
            print("No ref")
            return

        auvnames = []
        for aob in anatomies:
            uvname = self.getActiveUvLayer(aob)[1]
            auvnames.append(uvname)
            self.copyBodyPart(aob, cob)
        cname = self.getUvName(cob.data)
        drivers = {}

        # Select graft group for each anatomy
        for aob in anatomies:
            BlenderStatic.activate(context, aob)
            self.moveGraftVerts(aob, cob)
            self.getShapekeyDrivers(aob, drivers)
            self.replaceTexco(aob)

        # For the body, setup mask groups
        BlenderStatic.activate(context, cob)
        nverts = len(cob.data.vertices)
        vfaces = dict([(vn, []) for vn in range(nverts)])
        for f in cob.data.polygons:
            for vn in f.vertices:
                vfaces[vn].append(f.index)

        nfaces = len(cob.data.polygons)
        fmasked = dict([(fn, False) for fn in range(nfaces)])
        for aob in anatomies:
            for face in aob.data.DazMaskGroup:
                fmasked[face.a] = True

        # If cob is itself a geograft, make sure to keep tbe boundary
        if cob.data.DazGraftGroup:
            cgrafts = [pair.a for pair in cob.data.DazGraftGroup]
        else:
            cgrafts = []

        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        BlenderStatic.set_mode('OBJECT')

        # Select body verts to delete
        vdeleted = dict([(vn, False) for vn in range(nverts)])
        for aob in anatomies:
            paired = [pair.b for pair in aob.data.DazGraftGroup]
            for face in aob.data.DazMaskGroup:
                fverts = cob.data.polygons[face.a].vertices
                vdelete = []
                for vn in fverts:
                    if vn in cgrafts:
                        pass
                    elif vn not in paired:
                        vdelete.append(vn)
                    else:
                        mfaces = [fn for fn in vfaces[vn] if fmasked[fn]]
                        if len(mfaces) == len(vfaces[vn]):
                            vdelete.append(vn)
                for vn in vdelete:
                    cob.data.vertices[vn].select = True
                    vdeleted[vn] = True

        # Build association tables between new and old vertex numbers
        assoc = {}
        vn2 = 0
        for vn in range(nverts):
            if not vdeleted[vn]:
                assoc[vn] = vn2
                vn2 += 1

        # Original vertex locations
        if self.useVertexTable:
            origlocs = [v.co.copy() for v in cob.data.vertices]

        # If cob is itself a geograft, store locations
        if cob.data.DazGraftGroup:
            verts = cob.data.vertices
            locations = dict([(pair.a, verts[pair.a].co.copy())
                              for pair in cob.data.DazGraftGroup])

        # Delete the masked verts
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.delete(type='VERT')
        BlenderStatic.set_mode('OBJECT')

        # Select nothing
        for aob in anatomies:
            BlenderStatic.activate(context, aob)
            BlenderStatic.set_mode('EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            BlenderStatic.set_mode('OBJECT')
        BlenderStatic.activate(context, cob)
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        BlenderStatic.set_mode('OBJECT')

        # Select verts on common boundary
        names = []
        for aob in anatomies:
            BlenderObjectStatic.select(aob, True)
            names.append(aob.name)
            for pair in aob.data.DazGraftGroup:
                aob.data.vertices[pair.a].select = True
                if pair.b in assoc.keys():
                    cvn = assoc[pair.b]
                    cob.data.vertices[cvn].select = True

        # Also select cob graft group. These will not be removed.
        if cob.data.DazGraftGroup:
            for pair in cob.data.DazGraftGroup:
                cvn = assoc[pair.a]
                cob.data.vertices[cvn].select = True

        # Join meshes and remove doubles
        print("Merge %s to %s" % (names, cob.name))
        threshold = 0.001*cob.DazScale
        bpy.ops.object.join()
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        BlenderStatic.set_mode('OBJECT')
        selected = dict([(v.index, v.co.copy())
                         for v in cob.data.vertices if v.select])
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        BlenderStatic.set_mode('OBJECT')

        # Create graft vertex group
        vgrp = cob.vertex_groups.new(name="Graft")
        for vn in selected.keys():
            vgrp.add([vn], 1.0, 'REPLACE')
        mod = BlenderStatic.modifier(cob, 'MULTIRES')
        if mod:
            smod = cob.modifiers.new("Graft", 'SMOOTH')
            smod.factor = 1.0
            smod.iterations = 10
            smod.vertex_group = vgrp.name

        # Update cob graft group
        if cob.data.DazGraftGroup and selected:
            for pair in cob.data.DazGraftGroup:
                x = locations[pair.a]
                dists = [((x-y).length, vn) for vn, y in selected.items()]
                dists.sort()
                pair.a = dists[0][1]

        # Create a vertex table
        if self.useVertexTable:
            vn = 0
            eps = 1e-3*cob.DazScale
            for vn0, r in enumerate(origlocs):
                item = cob.data.DazOrigVerts.add()
                item.name = str(vn0)
                v = cob.data.vertices[vn]
                if (v.co - r).length > eps:
                    item.a = -1
                else:
                    item.a = vn
                    vn += 1
        else:
            cob.data.DazFingerPrint = ""

        # Merge UV layers
        if self.useMergeUvLayers:
            self.mergeUvLayers(cob, auvnames)
        self.copyShapeKeyDrivers(cob, drivers)
        Updating.drivers(cob)

    def getActiveUvLayer(self, ob):
        for idx, uvlayer in enumerate(ob.data.uv_layers):
            if uvlayer.active_render:
                return idx, uvlayer.name
        return 0, None

    def mergeUvLayers(self, cob, auvnames):
        idx0 = self.getActiveUvLayer(cob)[0]
        idxs = []
        for idx, uvlayer in enumerate(cob.data.uv_layers):
            if idx != idx0:
                uvname = uvlayer.name
                if uvname in auvnames:
                    idxs.append(idx)
                elif len(uvname) > 4 and uvname[-3] == "." and uvname[-3:].isdigit():
                    uvname = uvname[:-4]
                    if uvname in auvnames:
                        idxs.append(idx)
        if idxs:
            idxs.reverse()
        for idx in idxs:
            mergeUvLayers(cob.data, idx0, idx)

    def replaceTexco(self, ob):
        for uvtex in ob.data.uv_layers:
            if uvtex.active_render:
                uvrender = uvtex
        for mat in ob.data.materials:
            texco = None
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
            if texco:
                uvmap = mat.node_tree.nodes.new(type="ShaderNodeUVMap")
                uvmap.uv_map = uvrender.name
                uvmap.location = texco.location
                for link in mat.node_tree.links:
                    if link.from_node == texco:
                        mat.node_tree.link(
                            uvmap.outputs["UV"], link.to_socket)
                mat.node_tree.nodes.remove(texco)

    def copyBodyPart(self, aob, cob):
        apgs = aob.data.DazBodyPart
        cpgs = cob.data.DazBodyPart
        for sname, apg in apgs.items():
            if sname not in cpgs.keys():
                cpg = cpgs.add()
                cpg.name = sname
                cpg.s = apg.s

    def moveGraftVerts(self, aob, cob):
        cvgroups = dict([(vgrp.index, vgrp.name)
                         for vgrp in cob.vertex_groups])
        averts = aob.data.vertices
        cverts = cob.data.vertices
        for pair in aob.data.DazGraftGroup:
            avert = averts[pair.a]
            cvert = cverts[pair.b]
            avert.co = cvert.co
            for cg in cvert.groups:
                vgname = cvgroups[cg.group]
                if vgname in aob.vertex_groups.keys():
                    avgrp = aob.vertex_groups[vgname]
                else:
                    avgrp = aob.vertex_groups.new(name=vgname)
                avgrp.add([pair.a], cg.weight, 'REPLACE')

        askeys = aob.data.shape_keys
        cskeys = cob.data.shape_keys
        if askeys:
            for askey in askeys.key_blocks:
                if cskeys and askey.name in cskeys.key_blocks.keys():
                    cskey = cskeys.key_blocks[askey.name]
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cskey.data[pair.b].co
                else:
                    for pair in aob.data.DazGraftGroup:
                        askey.data[pair.a].co = cverts[pair.b].co

    def joinUvTextures(self, me):
        if len(me.uv_layers) <= 1:
            return
        for n, data in enumerate(me.uv_layers[0].data):
            if data.uv.length < 1e-6:
                for uvloop in me.uv_layers[1:]:
                    if uvloop.data[n].uv.length > 1e-6:
                        data.uv = uvloop.data[n].uv
                        break
        for uvtex in list(me.uv_layers[1:]):
            if uvtex.name not in self.keepUv:
                try:
                    me.uv_layers.remove(uvtex)
                except RuntimeError:
                    print("Cannot remove texture layer '%s'" % uvtex.name)

    def getUvName(self, me):
        for uvtex in me.uv_layers:
            if uvtex.active_render:
                return uvtex.name
        return None

    def removeMultires(self, ob):
        for mod in ob.modifiers:
            if mod.type == 'MULTIRES':
                ob.modifiers.remove(mod)


def replaceNodeNames(mat, oldname, newname):
    texco = None
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_COORD':
            texco = node
            break

    uvmaps = []
    for node in mat.node_tree.nodes:
        if isinstance(node, bpy.types.ShaderNodeUVMap):
            if node.uv_map == oldname:
                node.uv_map = newname
                uvmaps.append(node)
        elif isinstance(node, bpy.types.ShaderNodeAttribute):
            if node.attribute_name == oldname:
                node.attribute_name = newname
        elif isinstance(node, bpy.types.ShaderNodeNormalMap):
            if node.uv_map == oldname:
                node.uv_map = newname

    if texco and uvmaps:
        fromsocket = texco.outputs["UV"]
        tosockets = []
        for link in mat.node_tree.links:
            if link.from_node in uvmaps:
                tosockets.append(link.to_socket)
        for tosocket in tosockets:
            mat.node_tree.link(fromsocket, tosocket)

# -------------------------------------------------------------
#   Create graft and mask vertex groups
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_CreateGraftGroups(DazOperator):
    bl_idname = "daz.create_graft_groups"
    bl_label = "Greate Graft Groups"
    bl_description = "Create vertex groups from graft information"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.data.DazGraftGroup)

    def run(self, context):
        aob = context.object
        objects = []
        for ob in BlenderStatic.selected_meshes(context):
            if ob != aob:
                objects.append(ob)
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected.    ")
        cob = objects[0]
        gname = "Graft_" + aob.data.name
        mname = "Mask_" + aob.data.name
        self.createVertexGroup(
            aob, gname, [pair.a for pair in aob.data.DazGraftGroup])
        graft = [pair.b for pair in aob.data.DazGraftGroup]
        self.createVertexGroup(cob, gname, graft)
        mask = {}
        for face in aob.data.DazMaskGroup:
            for vn in cob.data.polygons[face.a].vertices:
                if vn not in graft:
                    mask[vn] = True
        self.createVertexGroup(cob, mname, mask.keys())

    def createVertexGroup(self, ob, gname, vnums):
        vgrp = ob.vertex_groups.new(name=gname)
        for vn in vnums:
            vgrp.add([vn], 1, 'REPLACE')
        return vgrp

# -------------------------------------------------------------
#   Merge UV sets
# -------------------------------------------------------------


def getUvLayers(scn, context):
    ob = context.object
    enums = []
    for n, uv in enumerate(ob.data.uv_layers):
        ename = "%s (%d)" % (uv.name, n)
        enums.append((str(n), ename, ename))
    return enums


@Registrar()
class DAZ_OT_MergeUvLayers(DazPropsOperator, IsMesh):
    bl_idname = "daz.merge_uv_layers"
    bl_label = "Merge UV Layers"
    bl_description = ("Merge an UV layer to the active render layer.\n" +
                      "Merging the active render layer to itself replaces\n" +
                      "any UV map nodes with texture coordinate nodes")
    bl_options = {'UNDO'}

    layer: EnumProperty(
        items=getUvLayers,
        name="Layer To Merge",
        description="UV layer that is merged with the active render layer")

    def draw(self, context):
        self.layout.label(text="Active Layer: %s" % self.keepName)
        self.layout.prop(self, "layer")

    def invoke(self, context, event):
        ob = context.object
        self.keepIdx = -1
        self.keepName = "None"
        for idx, uvlayer in enumerate(ob.data.uv_layers):
            if uvlayer.active_render:
                self.keepIdx = idx
                self.keepName = uvlayer.name
                break
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        if self.keepIdx < 0:
            raise DazError("No active UV layer found")
        mergeIdx = int(self.layer)
        mergeUvLayers(context.object.data, self.keepIdx, mergeIdx)
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        BlenderStatic.set_mode('OBJECT')


def mergeUvLayers(me, keepIdx, mergeIdx):
    def replaceUVMapNodes(me, mergeLayer):
        for mat in me.materials:
            texco = None
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_COORD':
                    texco = node
            deletes = {}
            for link in mat.node_tree.links:
                node = link.from_node
                if (node.type == 'UVMAP' and
                        node.uv_map == mergeLayer.name):
                    deletes[node.name] = node
                    if texco is None:
                        texco = mat.node_tree.nodes.new(
                            type="ShaderNodeTexCoord")
                        texco.location = node.location
                    mat.node_tree.link(
                        texco.outputs["UV"], link.to_socket)
            for node in deletes.values():
                mat.node_tree.nodes.remove(node)

    keepLayer = me.uv_layers[keepIdx]
    mergeLayer = me.uv_layers[mergeIdx]
    if not keepLayer.active_render:
        raise DazError("Only the active render layer may be the layer to keep")
    replaceUVMapNodes(me, mergeLayer)
    if keepIdx == mergeIdx:
        print("UV layer is the same as the active render layer.")
        return
    for n, data in enumerate(mergeLayer.data):
        if data.uv.length > 1e-6:
            keepLayer.data[n].uv = data.uv
    for mat in me.materials:
        if mat.use_nodes:
            replaceNodeNames(mat, mergeLayer.name, keepLayer.name)
    me.uv_layers.active_index = keepIdx
    me.uv_layers.remove(mergeLayer)
    print("UV layers joined")

# -------------------------------------------------------------
#   Get selected rigs
# -------------------------------------------------------------


def getSelectedRigs(context):
    rig = context.object
    if rig:
        BlenderStatic.set_mode('OBJECT')
    subrigs = []
    for ob in BlenderStatic.selected_armature(context):
        if ob != rig:
            subrigs.append(ob)
    return rig, subrigs

# -------------------------------------------------------------
#   Eliminate Empties
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_EliminateEmpties(DazPropsOperator):
    bl_idname = "daz.eliminate_empties"
    bl_label = "Eliminate Empties"
    bl_description = "Delete non-hidden empties, parenting its children to its parent instead"
    bl_options = {'UNDO'}

    useCollections: BoolProperty(
        name="Create Collections",
        description="Replace empties with collections",
        default=True)

    def draw(self, context):
        self.layout.prop(self, "useCollections")

    def run(self, context):
        roots = []
        for ob in BlenderStatic.selected(context):
            if ob.parent is None:
                roots.append(ob)
        for root in roots:
            if self.useCollections:
                coll = self.getCollection(root)
            else:
                coll = None
            self.eliminateEmpties(root, context, False, coll)

    def eliminateEmpties(self, ob, context, sub, coll):
        deletes = []
        elim = self.doEliminate(ob)
        if elim:
            if coll:
                subcoll = bpy.data.collections.new(ob.name)
                coll.children.link(subcoll)
                sub = True
                coll = subcoll
        elif sub and coll:
            if ob.name not in coll.objects:
                self.unlinkAll(ob)
                coll.objects.link(ob)
        for child in ob.children:
            self.eliminateEmpties(child, context, sub, coll)
        if elim:
            deletes.append(ob)
            for child in ob.children:
                wmat = child.matrix_world.copy()
                if ob.parent_type == 'OBJECT':
                    child.parent = ob.parent
                    child.parent_type = 'OBJECT'
                    BlenderStatic.world_matrix(child, wmat)
                elif ob.parent_type == 'BONE':
                    child.parent = ob.parent
                    child.parent_type = 'BONE'
                    child.parent_bone = ob.parent_bone
                    BlenderStatic.world_matrix(child, wmat)
                else:
                    raise DazError("Unknown parent type: %s %s" %
                                   (child.name, ob.parent_type))
        for empty in deletes:
            BlenderStatic.delete_list(context, [empty])

    def doEliminate(self, ob):
        if ob.type != 'EMPTY' or BlenderObjectStatic.is_hide(ob):
            return False
        return (ob.instance_type == 'NONE')

    def getCollection(self, ob):
        for coll in bpy.data.collections:
            if ob.name in coll.objects:
                return coll
        return None

    def unlinkAll(self, ob):
        for coll in bpy.data.collections:
            if ob.name in coll.objects:
                coll.objects.unlink(ob)

# -------------------------------------------------------------
#   Merge rigs
# -------------------------------------------------------------


class RigInfo:
    def __init__(self, rig, conforms, btn):
        self.name = rig.name
        self.rig = rig
        self.button = btn
        self.objects = []
        self.deletes = []
        self.addObjects(rig)
        self.conforms = conforms
        if rig.parent and rig.parent_type == 'BONE':
            self.parbone = rig.parent_bone
        else:
            self.parbone = None
        self.matrix = rig.matrix_world.copy()
        self.editbones = {}
        self.posebones = {}

    def getBoneKey(self, bname):
        if self.button.useCreateDuplicates:
            return "%s:%s" % (self.rig.name, bname)
        else:
            return bname

    def addObjects(self, ob):
        for child in ob.children:
            if BlenderObjectStatic.is_hide(child):
                continue
            elif child.type != 'ARMATURE':
                partype = child.parent_type
                parbone = child.parent_bone
                self.objects.append((child, (partype, parbone)))
                self.addObjects(child)

    def getEditBones(self, mainbones):
        BlenderStatic.set_mode('EDIT')
        for eb in self.rig.data.edit_bones:
            if eb.name not in mainbones:
                if eb.parent:
                    parent = eb.parent.name
                else:
                    parent = None
                key = self.getBoneKey(eb.name)
                self.editbones[key] = (
                    eb.head.copy(), eb.tail.copy(), eb.roll, parent)
        BlenderStatic.set_mode('OBJECT')
        for pb in self.rig.pose.bones:
            if pb.name not in mainbones:
                key = self.getBoneKey(pb.name)
                self.posebones[key] = (pb, pb.matrix.copy())
                if not self.button.useCreateDuplicates:
                    mainbones.append(pb.name)

    def addEditBones(self, rig, layers):
        ebones = rig.data.edit_bones
        for bname, data in self.editbones.items():
            eb = ebones.new(bname)
            parent = data[3]
            eb = ebones[bname]
            if parent:
                self.setParent(eb, parent, ebones)
            elif self.parbone:
                self.setParent(eb, self.parbone, ebones)
            eb.head, eb.tail, eb.roll, parent = data
            eb.layers = layers

    def setParent(self, eb, parent, ebones):
        parkey = self.getBoneKey(parent)
        if parent in ebones.keys():
            eb.parent = ebones[parent]
        elif parkey in ebones.keys():
            eb.parent = ebones[parkey]
        else:
            print("Parent not found", eb.name, parent)

    def copyPose(self, context, rig):
        from daz_import.figure import copyBoneInfo
        from daz_import.fix import copyConstraints
        for key in self.rig.data.keys():
            rig.data[key] = self.rig.data[key]
        self.copyProps(self.rig, rig)
        self.copyProps(self.rig.data, rig.data)
        self.button.copyDrivers(self.rig.data, rig.data, self.rig, rig)
        self.button.copyDrivers(self.rig, rig, self.rig, rig)
        BlenderStatic.active_object(context, rig)
        wmat = rig.matrix_world.inverted() @ self.matrix
        for bname, data in self.posebones.items():
            pb = rig.pose.bones[bname]
            subpb, pb.matrix = data
            copyBoneInfo(subpb, pb)
            copyConstraints(subpb, pb, rig)

    def copyProps(self, src, trg):
        from daz_import.driver import getPropMinMax, setPropMinMax, setFloatProp, setBoolProp
        for prop, value in src.items():
            if (prop[0] != "_" and
                prop[0:3] != "Daz" and
                    prop not in trg.keys()):
                if isinstance(value, float):
                    min, max = getPropMinMax(src, prop)
                    setFloatProp(trg, prop, value, min, max)
                elif isinstance(value, int):
                    min, max = getPropMinMax(src, prop)
                    trg[prop] = value
                    setPropMinMax(trg, prop, min, max)
                elif isinstance(value, bool):
                    setBoolProp(trg, prop, value)
                elif isinstance(value, str):
                    trg[prop] = value

    def reParent(self, rig):
        subrig = self.rig
        wmat = subrig.matrix_world.copy()
        subrig.parent = rig
        if self.parbone:
            subrig.parent_type = 'BONE'
            subrig.parent_bone = self.parbone
        else:
            subrig.parent_type = 'OBJECT'
        subrig.matrix_world = wmat

    def renameVertexGroups(self, ob):
        for key in self.editbones.keys():
            if self.button.useCreateDuplicates:
                _, bname = key.split(":", 1)
            else:
                bname = key
            if bname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[bname]
                vgrp.name = key


@Registrar()
class DAZ_OT_MergeRigs(DazPropsOperator, DriverUser, IsArmature):
    bl_idname = "daz.merge_rigs"
    bl_label = "Merge Rigs"
    bl_description = "Merge selected rigs to active rig"
    bl_options = {'UNDO'}

    clothesLayer: IntProperty(
        name="Clothes Layer",
        description="Bone layer used for extra bones when merging clothes",
        min=1, max=32,
        default=3)

    separateCharacters: BoolProperty(
        name="Separate Characters",
        description="Don't merge armature that belong to different characters",
        default=False)

    useCreateDuplicates: BoolProperty(
        name="Create Duplicate Bones",
        description="Create separate bones if several bones with the same name are found",
        default=False)

    useMergeNonConforming: BoolProperty(
        name="Merge Non-conforming Rigs",
        description="Also merge non-conforming rigs.\n(Bone parented and with no bones in common with main rig)",
        default=True)

    createMeshCollection: BoolProperty(
        name="Create Mesh Collection",
        description="Create a new collection and move all meshes to it",
        default=True)

    def draw(self, context):
        self.layout.prop(self, "clothesLayer")
        self.layout.prop(self, "separateCharacters")
        self.layout.prop(self, "useCreateDuplicates")
        self.layout.prop(self, "useMergeNonConforming")
        self.layout.prop(self, "createMeshCollection")

    def __init__(self):
        DriverUser.__init__(self)

    def run(self, context):
        if not self.separateCharacters:
            rig, subrigs = getSelectedRigs(context)
            info, subinfos = self.getRigInfos(rig, subrigs)
            self.mergeRigs(context, info, subinfos)
        else:
            rigs = []
            for rig in BlenderStatic.selected_armature(context):
                if rig.parent is None:
                    rigs.append(rig)
            rpairs = []
            for rig in rigs:
                subrigs = self.getSubRigs(context, rig)
                rpairs.append((rig, subrigs))
            ipairs = []
            for rig, subrigs in rpairs:
                info, subinfos = self.getRigInfos(rig, subrigs)
                ipairs.append((info, subinfos))
            for info, subinfos in ipairs:
                BlenderStatic.activate(context, info.rig)
                self.mergeRigs(context, info, subinfos)

    def getRigInfos(self, rig, subrigs):
        subinfos = []
        info = RigInfo(rig, True, self)
        for subrig in subrigs:
            if subrig.parent and subrig.parent_type == 'BONE':
                conforms = self.isConforming(subrig, rig)
            else:
                conforms = True
            subinfo = RigInfo(subrig, conforms, self)
            subinfos.append(subinfo)

        bpy.ops.object.select_all(action='DESELECT')
        for ob, _ in info.objects:
            BlenderObjectStatic.select(ob, True)
        for subinfo in subinfos:
            BlenderObjectStatic.select(subinfo.rig, True)
            for ob, _ in subinfo.objects:
                BlenderObjectStatic.select(ob, True)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        return info, subinfos

    def isConforming(self, subrig, rig):
        if self.useMergeNonConforming:
            return True
        for bname in subrig.data.bones.keys():
            if bname in rig.data.bones.keys():
                return True
        return False

    def applyTransforms(self, infos):
        bpy.ops.object.select_all(action='DESELECT')
        for info in infos:
            if info.conforms:
                BlenderObjectStatic.select(info.rig, True)
                for ob, _ in info.objects:
                    BlenderObjectStatic.select(ob, True)
        try:
            bpy.ops.object.transform_apply(
                location=True, rotation=True, scale=True)
        except RuntimeError:
            print("Failed to apply transform")

    def getSubRigs(self, context, rig):
        subrigs = []
        for ob in rig.children:
            if ob.type == 'ARMATURE' and ob.select_get():
                subrigs.append(ob)
                subrigs += self.getSubRigs(context, ob)
        return subrigs

    def mergeRigs(self, context, info, subinfos):
        rig = info.rig
        Settings.forAnimation(None, rig)
        if rig is None:
            raise DazError("No rigs to merge")
        oldvis = list(rig.data.layers)
        rig.data.layers = 32*[True]
        success = False
        try:
            self.mergeRigs1(info, subinfos, context)
            success = True
        finally:
            rig.data.layers = oldvis
            if success:
                rig.data.layers[self.clothesLayer-1] = True
            BlenderStatic.active_object(context, rig)
            Updating.drivers(rig)
            Updating.drivers(rig.data)

    def mergeRigs1(self, info, subinfos, context):
        from daz_import.Elements.Node import clearParent
        scn = context.scene
        rig = info.rig

        print("Merge infos to %s:" % rig.name)
        self.applyTransforms([info]+subinfos)
        mainbones = list(rig.pose.bones.keys())
        for subinfo in subinfos:
            subinfo.getEditBones(mainbones)
        adds, hdadds, removes = self.createNewCollections(rig)

        layers = (self.clothesLayer-1)*[False] + \
            [True] + (32-self.clothesLayer)*[False]
        BlenderStatic.activate(context, rig)
        BlenderStatic.set_mode('EDIT')
        for subinfo in subinfos:
            if subinfo.conforms:
                subinfo.addEditBones(rig, layers)
        BlenderStatic.set_mode('OBJECT')
        self.reparentObjects(info, rig, adds, hdadds, removes)
        for subinfo in subinfos:
            if subinfo.conforms:
                subinfo.copyPose(context, rig)
                for ob, _ in subinfo.objects:
                    if ob.type == 'MESH':
                        self.changeArmatureModifier(ob, rig)
                        subinfo.renameVertexGroups(ob)
                self.reparentObjects(subinfo, rig, adds, hdadds, removes)
                subinfo.rig.parent = None
                BlenderStatic.delete_list(context, [subinfo.rig])
            else:
                subinfo.reParent(rig)
                self.reparentObjects(subinfo, subinfo.rig,
                                     adds, hdadds, removes)
            BlenderStatic.delete_list(context, subinfo.deletes)
        BlenderStatic.activate(context, rig)
        self.cleanVertexGroups(rig)
        BlenderStatic.set_mode('OBJECT')
        self.applyTransforms([info])

    def reparentObjects(self, info, rig, adds, hdadds, removes):
        from daz_import.proxy import stripName

        for ob, data in info.objects:
            partype, parbone = data
            wmat = ob.matrix_world
            ob.parent = rig
            ob.parent_type = partype

            if parbone is None:
                pass
            elif parbone in rig.data.bones.keys():
                ob.parent_bone = parbone
            else:
                ob.parent_bone = info.getBoneKey(parbone)

            ob.matrix_world = wmat
            self.addToCollections(ob, adds, hdadds, removes)
            ob.name = stripName(ob.name)
            
            if ob.data:
                ob.data.name = stripName(ob.data.name)

    def createNewCollections(self, rig):
        adds = []
        hdadds = []
        removes = []
        if not self.createMeshCollection:
            return adds, hdadds, removes

        mcoll = hdcoll = None
        for coll in bpy.data.collections:
            if rig in coll.objects.values():
                if coll.name.endswith("HD"):
                    if hdcoll is None:
                        hdcoll = bpy.data.collections.new(
                            name=rig.name + " Meshes_HD")
                        hdadds = [hdcoll]
                    coll.children.link(hdcoll)
                else:
                    if mcoll is None:
                        mcoll = bpy.data.collections.new(
                            name=rig.name + " Meshes")
                        adds = [mcoll]
                    coll.children.link(mcoll)
                removes.append(coll)
        return adds, hdadds, removes

    def changeVertexGroupNames(self, ob, storage):
        for bname in storage.keys():
            if bname in ob.vertex_groups.keys():
                vgrp = ob.vertex_groups[bname]
                vgrp.name = storage[bname].realname

    def addToCollections(self, ob, adds, hdadds, removes):
        if not self.createMeshCollection:
            return
        if ob.name.endswith("HD"):
            adders = hdadds
        else:
            adders = adds
        for grp in adders:
            if ob.name not in grp.objects:
                grp.objects.link(ob)
        for grp in removes:
            if ob.name in grp.objects:
                grp.objects.unlink(ob)

    def changeArmatureModifier(self, ob, rig):
        mod = BlenderStatic.modifier(ob, 'ARMATURE')
        if mod:
            mod.name = rig.name
            mod.object = rig
            return
        if len(ob.vertex_groups) == 0:
            print("Mesh with no vertex groups: %s" % ob.name)
        else:
            mod = ob.modifiers.new(rig.name, "ARMATURE")
            mod.object = rig
            mod.use_deform_preserve_volume = True

    def cleanVertexGroups(self, rig):
        def unkey(bname):
            return bname.split(":", 1)[-1]

        bones = dict([(unkey(bname), []) for bname in rig.data.bones.keys()])
        for bone in rig.data.bones:
            bones[unkey(bone.name)].append(bone)
        for bname, dbones in bones.items():
            if len(dbones) == 1:
                bone = dbones[0]
                if bone.name != bname:
                    bone.name = bname

# -------------------------------------------------------------
#   Copy bone locations
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_CopyPose(DazOperator, IsArmature):
    bl_idname = "daz.copy_pose"
    bl_label = "Copy Pose"
    bl_description = "Copy pose from active rig to selected rigs"
    bl_options = {'UNDO'}

    def run(self, context):
        rig, subrigs = getSelectedRigs(context)
        if rig is None:
            raise DazError("No source armature")
        if not subrigs:
            raise DazError("No target armature")

        for subrig in subrigs:
            if not BlenderStatic.active_object(context, subrig):
                continue
            print("Copy bones to %s:" % subrig.name)
            BlenderStatic.world_matrix(subrig, rig.matrix_world)
            # Updating.scene(context)
            bpy.context.view_layer.update()
            for pb in subrig.pose.bones:
                if pb.name in rig.pose.bones.keys():
                    pb.matrix = rig.pose.bones[pb.name].matrix
                    bpy.context.view_layer.update()
                    # Updating.scene(context)

# -------------------------------------------------------------
#   Apply rest pose
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_ApplyRestPoses(DazOperator, IsArmature):
    bl_idname = "daz.apply_rest_pose"
    bl_label = "Apply Rest Pose"
    bl_description = "Apply current pose at rest pose to selected rigs and children"
    bl_options = {'UNDO'}

    def run(self, context):
        rig, subrigs = getSelectedRigs(context)
        applyRestPoses(context, rig, subrigs)


def applyRestPoses(context, rig, subrigs):

    def applyLimitConstraints(rig):
        constraints = []
        for pb in rig.pose.bones:
            if pb.rotation_mode != 'QUATERNION':
                x, y, z = pb.rotation_euler
                for cns in pb.constraints:
                    if cns.type == 'LIMIT_ROTATION':
                        constraints.append((cns, cns.mute))
                        cns.mute = True
                        applyLimitComp("min_x", "max_x",
                                       "use_limit_x", 0, cns, pb)
                        applyLimitComp("min_y", "max_y",
                                       "use_limit_y", 1, cns, pb)
                        applyLimitComp("min_z", "max_z",
                                       "use_limit_z", 2, cns, pb)
        return constraints

    def applyLimitComp(min, max, use, idx, cns, pb):
        x = pb.rotation_euler[idx]
        if getattr(cns, use):
            xmax = getattr(cns, max)
            if x > xmax:
                x = pb.rotation_euler[idx] = xmax
            xmax -= x
            if abs(xmax) < 1e-4:
                xmax = 0
            setattr(cns, max, xmax)

            xmin = getattr(cns, min)
            if x < xmin:
                x = pb.rotation_euler[idx] = xmin
            xmin -= x
            if abs(xmin) < 1e-4:
                xmin = 0
            setattr(cns, min, xmin)

    Settings.forAnimation(None, rig)
    rigs = [rig] + subrigs
    applyAllObjectTransforms(rigs)
    for subrig in rigs:
        for ob in subrig.children:
            if ob.type == 'MESH':
                setRestPose(ob, subrig, context)
        if not BlenderStatic.active_object(context, subrig):
            continue
        constraints = applyLimitConstraints(subrig)
        BlenderStatic.set_mode('POSE')
        bpy.ops.pose.armature_apply()
        for cns, mute in constraints:
            cns.mute = mute
    BlenderStatic.active_object(context, rig)


def applyAllObjectTransforms(rigs):
    bpy.ops.object.select_all(action='DESELECT')
    for rig in rigs:
        BlenderObjectStatic.select(rig, True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    try:
        for rig in rigs:
            for ob in rig.children:
                if ob.type == 'MESH':
                    BlenderObjectStatic.select(ob, True)
        bpy.ops.object.transform_apply(
            location=True, rotation=True, scale=True)
        return True
    except RuntimeError:
        print("Could not apply object transformations to meshes")
        return False


def setRestPose(ob, rig, context):
    from daz_import.Elements.Node import setParent
    if not BlenderStatic.active_object(context, ob):
        return
    setParent(context, ob, rig)
    if ob.parent_type == 'BONE' or ob.type != 'MESH':
        return

    if Settings.fitFile_:
        mod = BlenderStatic.modifier(ob, 'ARMATURE')
        if mod:
            mod.object = rig
    elif len(ob.vertex_groups) == 0:
        print("Mesh with no vertex groups: %s" % ob.name)
    else:
        try:
            applyArmatureModifier(ob)
            ok = True
        except RuntimeError:
            print("Could not apply armature to %s" % ob.name)
            ok = False
        if ok:
            mod = ob.modifiers.new(rig.name, "ARMATURE")
            mod.object = rig
            mod.use_deform_preserve_volume = True
            nmods = len(ob.modifiers)
            for n in range(nmods-1):
                bpy.ops.object.modifier_move_up(modifier=mod.name)


def applyArmatureModifier(ob):
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE':
            mname = mod.name
            if ob.data.shape_keys:
                if bpy.app.version < (2, 90, 0):
                    bpy.ops.object.modifier_apply(
                        apply_as='SHAPE', modifier=mname)
                else:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
                skey = ob.data.shape_keys.key_blocks[mname]
                skey.value = 1.0
            else:
                bpy.ops.object.modifier_apply(modifier=mname)

# -------------------------------------------------------------
#   Merge toes
# -------------------------------------------------------------


GenesisToes = {
    "lFoot": ["lMetatarsals"],
    "rFoot": ["rMetatarsals"],
    "lToe": ["lBigToe", "lSmallToe1", "lSmallToe2", "lSmallToe3", "lSmallToe4",
             "lBigToe_2", "lSmallToe1_2", "lSmallToe2_2", "lSmallToe3_2", "lSmallToe4_2"],
    "rToe": ["rBigToe", "rSmallToe1", "rSmallToe2", "rSmallToe3", "rSmallToe4",
             "rBigToe_2", "rSmallToe1_2", "rSmallToe2_2", "rSmallToe3_2", "rSmallToe4_2"],
}

NewParent = {
    "lToe": "lFoot",
    "rToe": "rFoot",
}


def reparentToes(rig, context):
    from daz_import.driver import removeBoneSumDrivers
    BlenderStatic.active_object(context, rig)
    toenames = []
    BlenderStatic.set_mode('EDIT')
    for parname in ["lToe", "rToe"]:
        if parname in rig.data.edit_bones.keys():
            parb = rig.data.edit_bones[parname]
            for bname in GenesisToes[parname]:
                if bname[-2:] == "_2":
                    continue
                if bname in rig.data.edit_bones.keys():
                    eb = rig.data.edit_bones[bname]
                    if UtilityBoneStatic.is_drv_bone(eb.parent.name):
                        eb = eb.parent
                    eb.parent = parb
                    toenames.append(eb.name)
    BlenderStatic.set_mode('OBJECT')
    #removeBoneSumDrivers(rig, toenames)


@Registrar()
class DAZ_OT_ReparentToes(DazOperator, IsArmature):
    bl_idname = "daz.reparent_toes"
    bl_label = "Reparent Toes"
    bl_description = "Parent small toes to big toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        reparentToes(context.object, context)


def mergeBonesAndVgroups(rig, mergers, parents, context):
    from daz_import.driver import removeBoneSumDrivers

    BlenderStatic.activate(context, rig)

    BlenderStatic.set_mode('OBJECT')
    for bones in mergers.values():
        removeBoneSumDrivers(rig, bones)

    BlenderStatic.set_mode('EDIT')
    for bname, pname in parents.items():
        if (pname in rig.data.edit_bones.keys() and
                bname in rig.data.edit_bones.keys()):
            eb = rig.data.edit_bones[bname]
            parb = rig.data.edit_bones[pname]
            eb.use_connect = False
            eb.parent = parb
            parb.tail = eb.head

    for bones in mergers.values():
        for eb in rig.data.edit_bones:
            if eb.name in bones:
                rig.data.edit_bones.remove(eb)

    BlenderStatic.set_mode('OBJECT')

    for ob in rig.children:
        if ob.type == 'MESH':
            for toe, subtoes in mergers.items():
                if toe in ob.vertex_groups.keys():
                    vgrp = ob.vertex_groups[toe]
                else:
                    vgrp = ob.vertex_groups.new(name=toe)
                subgrps = []
                for subtoe in subtoes:
                    if subtoe in ob.vertex_groups.keys():
                        subgrps.append(ob.vertex_groups[subtoe])
                idxs = [vg.index for vg in subgrps]
                idxs.append(vgrp.index)
                weights = dict([(vn, 0)
                                for vn in range(len(ob.data.vertices))])
                for v in ob.data.vertices:
                    for g in v.groups:
                        if g.group in idxs:
                            weights[v.index] += g.weight
                for subgrp in subgrps:
                    ob.vertex_groups.remove(subgrp)
                for vn, w in weights.items():
                    if w > 1e-3:
                        vgrp.add([vn], w, 'REPLACE')

    Updating.drivers(rig)
    BlenderStatic.set_mode('OBJECT')


@Registrar()
class DAZ_OT_MergeToes(DazOperator, IsArmature):
    bl_idname = "daz.merge_toes"
    bl_label = "Merge Toes"
    bl_description = "Merge separate toes into a single toe bone"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = context.object
        mergeBonesAndVgroups(rig, GenesisToes, NewParent, context)
