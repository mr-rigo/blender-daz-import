import os

import math
from mathutils import Vector
from urllib.parse import unquote
import bpy
import bmesh
from bpy.props import IntProperty, BoolProperty, \
    CollectionProperty, StringProperty

from collections import OrderedDict

from daz_import.Lib import Registrar
from daz_import.Elements.Assets.Channels import Channels
from daz_import.Lib.Settings import Settings

from daz_import.Elements.Node import Node
from daz_import.Lib.Files import SingleFile, DazFile
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.VectorStatic import VectorStatic
from daz_import.Lib.Utility import UtilityStatic

from daz_import.Lib.Errors import DazOperator,\
    IsMesh, ErrorsStatic, DazPropsOperator, DazError,\
    IsMeshArmature

from daz_import.Elements.Assets.Asset import Asset
from daz_import.Elements.Assets.FileAsset import FileAsset
from daz_import.Collection import DazPath, Collection


# -------------------------------------------------------------
#   Geonode
# -------------------------------------------------------------


class GeoNode(Node):
    def __init__(self, figure, geo, ref):

        if figure.caller:
            fileref = figure.caller.fileref
        else:
            fileref = figure.fileref
        super().__init__(fileref)

        self.dyngenhair = None
        self.dynsim = None
        self.dynhairflw = None
        self.lintess = None
        self.simsets = []

        self.id = DazPath.normalize(ref)

        if isinstance(geo, Geometry):
            geo.caller = self
            geo.nodes[self.id] = self
            self.data = geo
        else:
            msg = ("Not a geometry:\n%s" % geo)
            ErrorsStatic.report(msg, trigger=(2, 3))
            self.data = None

        self.figure = figure
        self.figureInst = None
        self.verts = None
        self.edges = []
        self.faces = []
        self.materials = {}
        self.hairMaterials = []
        self.isStrandHair = False
        self.properties = {}
        self.polylines = None
        self.highdef = None
        self.hdobject = None
        self.index = figure.count
        self.modifiers = {}
        self.morphsValues = {}
        self.shstruct = {}
        self.push = 0
        self.assigned = False

    def __repr__(self):
        return ("<GeoNode %s %d M:%d C: %s R: %s>" % (self.id, self.index, len(self.materials), self.center, self.rna))

    def errorWrite(self, ref, fp):
        fp.write('   Settings: %s\n' % (self))

    def isVisibleMaterial(self, dmat):
        if self.data:
            return self.data.isVisibleMaterial(dmat)
        return True

    def preprocess(self, context, inst):
        if self.data:
            self.data.preprocess(context, inst)
        elif inst.isStrandHair:
            geo = self.data = Geometry(self.fileref)
            geo.name = inst.name
            geo.isStrandHair = True
            geo.preprocess(context, inst)

    def buildObject(self, context, inst, center):
        Node.buildObject(self, context, inst, center)

    def addLSMesh(self, ob, inst, rigname):
        if self.assigned:
            return
        elif inst.isStrandHair:
            Settings.hairs_[rigname].append(ob)
        else:
            Settings.meshes_[rigname].append(ob)
        self.assigned = True

    def subtractCenter(self, ob, inst, center):
        if not Settings.fitFile_:
            ob.location = -center
        inst.center = center

    def subdivideObject(self, ob, inst, context):
        if self.highdef:
            me = self.buildHDMesh(ob)
            hdob = bpy.data.objects.new(ob.name + "_HD", me)
            self.hdobject = inst.hdobject = hdob
            Settings.hdmeshes_[Settings.rigname_].append(hdob)
            hdob.DazVisibilityDrivers = ob.DazVisibilityDrivers
            self.addHDMaterials(ob.data.materials, "")
            center = Vector((0, 0, 0))
            self.arrangeObject(hdob, inst, context, center)
            multi = False
            if not (Settings.useMultires and Settings.useMultiUvLayers):
                self.addHDUvs(ob, hdob)
            if Settings.useMultires:
                multi = addMultires(context, hdob, False)
            if multi:
                if Settings.useMultiUvLayers:
                    copyUvLayers(ob, hdob)
            elif len(hdob.data.vertices) == len(ob.data.vertices):
                print("HD mesh same as base mesh:", ob.name)
                self.hdobject = inst.hdobject = None
                BlenderStatic.delete_list(context, [hdob])
        elif Settings.useHDObjects_:
            self.hdobject = inst.hdobject = ob

        if ob and self.data:
            self.data.buildRigidity(ob)
            hdob = self.hdobject
            if hdob and hdob != ob:
                self.data.buildRigidity(hdob)

        if (self.type == "subdivision_surface" and
            self.data and
                (self.data.SubDIALevel > 0 or self.data.SubDRenderLevel > 0)):

            mod = ob.modifiers.new("Subsurf", 'SUBSURF')
            mod.render_levels = self.data.SubDIALevel + self.data.SubDRenderLevel
            mod.levels = self.data.SubDIALevel
            mod.show_viewport = not Settings.hide_subsurf_

            # import pdb; pdb.set_trace()

            if hasattr(mod, "use_limit_surface"):
                mod.use_limit_surface = False
            self.data.creaseEdges(context, ob)

    def addMappings(self, selmap):
        self.data.mappings = dict([(key, val)
                                   for val, key in selmap["mappings"]])

    def buildHDMesh(self, ob):
        verts = self.highdef.verts
        hdfaces = self.highdef.faces
        faces = self.stripNegatives([f[0] for f in hdfaces])
        mnums = [f[4] for f in hdfaces]
        nverts = len(verts)
        me = bpy.data.meshes.new(ob.data.name + "_HD")
        print("Build HD mesh for %s: %d verts, %d faces" %
              (ob.name, nverts, len(faces)))
        me.from_pydata(verts, [], faces)
        print("HD mesh %s built" % me.name)
        for f in me.polygons:
            f.material_index = mnums[f.index]
            f.use_smooth = True
        return me

    def addHDUvs(self, ob, hdob):
        if not self.highdef.uvs:
            if hdob.name not in Settings.hdUvMissing_:
                Settings.hdUvMissing_.append(hdob.name)
            return

        hdfaces = self.highdef.faces
        uvfaces = self.stripNegatives([f[1] for f in hdfaces])
        if len(ob.data.uv_layers) > 0:
            uvname = ob.data.uv_layers[0].name
        else:
            uvname = "UV Layer"
        addUvs(hdob.data, uvname, self.highdef.uvs, uvfaces)

    def addHDMaterials(self, mats, prefix):
        for mat in mats:
            pg = self.hdobject.data.DazHDMaterials.add()
            pg.name = prefix + mat.name.rsplit("-", 1)[0]
            pg.text = mat.name
        if self.data and self.data.vertex_pairs:
            # Geograft
            insts = []
            for inst in self.figure.instances.values():
                if inst and inst.parent and inst not in insts:
                    insts.append(inst)
                    par = inst.parent.geometries[0]
                    if par and par.hdobject and par.hdobject != par.rna:
                        par.addHDMaterials(mats, inst.name + "?" + prefix)

    def stripNegatives(self, faces):
        return [(f if f[-1] >= 0 else f[:-1]) for f in faces]

    def finalize(self, context, inst):
        geo = self.data
        ob = self.rna
        if ob is None:
            return
        if self.hairMaterials:
            for dmat in self.hairMaterials:
                if dmat.rna:
                    ob.data.materials.append(dmat.rna)
        if self.hdobject:
            self.finishHD(context, self.rna, self.hdobject, inst)
        if Settings.fitFile_ and ob.type == 'MESH':
            shiftMesh(ob, inst.worldmat.inverted())
            hdob = self.hdobject
            if hdob and hdob != ob:
                shiftMesh(hdob, inst.worldmat.inverted())

    def finishHD(self, context, ob, hdob, inst):
        if hdob != ob:
            self.copyHDMaterials(ob, hdob, context, inst)
        if Settings.hdcollection_ is None:
            from daz_import.Elements.Import import makeRootCollection
            # from daz_import.Elements.Import import makeRootCollection
            Settings.hdcollection_ = makeRootCollection(
                Settings.collection_.name + "_HD", context)
        if hdob.name in Settings.hdcollection_.objects:
            print("DUPHD", hdob.name)
            return
        Settings.hdcollection_.objects.link(hdob)
        if hdob.parent and hdob.parent.name not in Settings.hdcollection_.objects:
            Settings.hdcollection_.objects.link(hdob.parent)
        if hdob == ob:
            return
        hdob.parent = ob.parent
        hdob.parent_type = ob.parent_type
        hdob.parent_bone = ob.parent_bone
        BlenderStatic.world_matrix(hdob, ob.matrix_world)
        if hdob.name in inst.collection.objects:
            inst.collection.objects.unlink(hdob)

    def postbuild(self, context, inst):
        ob = self.rna
        if ob:
            pruneUvMaps(ob)
            self.addLSMesh(ob, inst, None)

    def copyHDMaterials(self, ob, hdob, context, inst):
        from daz_import.Elements.Material import Material

        def getDataMaterial(mname):
            while True:
                for mat in Material.loaded.values():
                    if mat.name.startswith(mname):
                        return mat

                words = mname.split("_", 1)
                if len(words) == 1:
                    return None
                mname = words[1]

        def fixHDMaterial(mat, uvmap):
            keep = True

            for node in mat.node_tree.nodes:
                if node.type in ['UVMAP', 'NORMAL_MAP']:
                    keep = False
                    break

            if keep:
                return mat
            
            nmat = mat.copy()

            for node in nmat.node_tree.nodes:
                if node.type in ['UVMAP', 'NORMAL_MAP']:
                    node.uv_map = uvmap

            return nmat

        uvmap = None
        useMulti = (BlenderStatic.modifier(hdob, 'MULTIRES')
                    and Settings.useMultiUvLayers)
        if not useMulti and len(ob.data.uv_layers) > 1:
            if hdob.data.uv_layers:
                uvmap = hdob.data.uv_layers[0].name
            elif hdob.name not in Settings.hdUvMissing_:
                Settings.hdUvMissing_.append(hdob.name)
        matnames = dict([(pg.name, pg.text)
                         for pg in hdob.data.DazHDMaterials])

        for mname in self.highdef.matgroups:
            mname = matnames.get(mname, mname)

            mat = None

            if mat := Material.loaded.get(mname):
                ...
            else:
                mat = getDataMaterial(mname)

            if uvmap and mat:
                mat = fixHDMaterial(mat, uvmap)

            hdob.data.materials.append(mat)
        inst.parentObject(context, self.hdobject)

    def setHideInfo(self):
        if self.data is None:
            return

        self.setHideInfoMesh(self.rna)

        if self.hdobject and self.hdobject != self.rna:
            self.setHideInfoMesh(self.hdobject)

    def setHideInfoMesh(self, ob):
        if ob.data is None:
            return
        ob.data.DazVertexCount = self.data.vertex_count
        
        if self.data.hidden_polys:
            hgroup = ob.data.DazMaskGroup

            for fn in self.data.hidden_polys:
                elt = hgroup.add()
                elt.a = fn

        if self.data.vertex_pairs:
            ggroup = ob.data.DazGraftGroup
            
            for vn, pvn in self.data.vertex_pairs:
                pair = ggroup.add()
                pair.a = vn
                pair.b = pvn

    def hideVertexGroups(self, hidden):
        fnums = self.data.getPolyGroup(hidden)
        self.data.hidePolyGroup(self.rna, fnums)
        if self.hdobject and self.hdobject != self.rna:
            self.data.hidePolyGroup(self.hdobject.rna, fnums)


def shiftMesh(ob, mat):
    from daz_import.Elements.Node import isUnitMatrix
    if isUnitMatrix(mat):
        return
    for v in ob.data.vertices:
        v.co = mat @ v.co


def isEmpty(vgrp, ob):
    idx = vgrp.index
    for v in ob.data.vertices:
        for g in v.groups:
            if (g.group == idx and
                    abs(g.weight-0.5) > 1e-4):
                return False
    return True

# -------------------------------------------------------------
#   Add multires
# -------------------------------------------------------------


def addMultires(context, hdob, strict):
    if bpy.app.version < (2, 90, 0):
        print("Cannot rebuild subdiv in Blender %d.%d.%d" % bpy.app.version)
        return False
    BlenderStatic.activate(context, hdob)
    BlenderStatic.set_mode('EDIT')
    bpy.ops.mesh.delete_loose()
    BlenderStatic.set_mode('OBJECT')
    mod = hdob.modifiers.new("Multires", 'MULTIRES')
    try:
        bpy.ops.object.multires_rebuild_subdiv(modifier="Multires")
        msg = None
    except RuntimeError:
        msg = ('Cannot rebuild subdivisions for "%s"' % hdob.name)
    if msg is None:
        hdob.DazMultires = True
        return True
    elif strict:
        raise DazError(msg)
    else:
        ErrorsStatic.report(msg, trigger=(2, 4))
        hdob.modifiers.remove(mod)
        Settings.hdFailures_.append(hdob.name)
        return False


@Registrar()
class DAZ_OT_MakeMultires(DazOperator):
    bl_idname = "daz.make_multires"
    bl_label = "Make Multires"
    bl_description = "Convert HD mesh into mesh with multires modifier,\nand add vertex groups and extra UV layers"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        from daz_import.Elements.Modifier import makeArmatureModifier, copyVertexGroups
        meshes = BlenderStatic.selected_meshes(context)
        if len(meshes) != 2:
            raise DazError(
                "Two meshes must be selected, \none subdivided and one at base resolution.")
        hdob = context.object
        baseob = None
        for ob in meshes:
            if ob != hdob:
                if len(hdob.data.vertices) > len(ob.data.vertices):
                    baseob = ob
                else:
                    hdob = ob
                    baseob = context.object
                break
        addMultires(context, hdob, True)
        copyUvLayers(baseob, hdob)
        rig = baseob.parent
        if not (rig and rig.type == 'ARMATURE'):
            return
        hdob.parent = rig
        makeArmatureModifier(rig.name, context, hdob, rig)
        copyVertexGroups(baseob, hdob)


def copyUvLayers(ob, hdob):
    def setupLoopsMapping():
        loopsMapping = {}
        for f in hdob.data.polygons:
            loops = dict([(vn, f.loop_indices[i])
                          for i, vn in enumerate(f.vertices)])
            fid = tuple(UtilityStatic.sorted(list(f.vertices)))
            if fid in loopsMapping:
                raise RuntimeError("duplicated face_id?")
            loopsMapping[fid] = loops
        return loopsMapping

    def copyUvLayer(uvdata, hddata, loopsMapping):
        for f in ob.data.polygons:
            fid = tuple(UtilityStatic.sorted(list(f.vertices)))
            if fid not in loopsMapping:
                #print("Bad map", fid)
                continue
            for i, vn in enumerate(f.vertices):
                if vn not in loopsMapping[fid]:
                    print("Bad vert", vn)
                    continue
                hdLoop = loopsMapping[fid][vn]
                loop = f.loop_indices[i]
                hddata[hdLoop].uv = uvdata[loop].uv

    for uvlayer in list(hdob.data.uv_layers):
        hdob.data.uv_layers.remove(uvlayer)
    loopsMapping = setupLoopsMapping()
    for uvlayer in ob.data.uv_layers:
        hdlayer = makeNewUvloop(hdob.data, uvlayer.name, False)
        copyUvLayer(uvlayer.data, hdlayer.data, loopsMapping)

# -------------------------------------------------------------
#   Geometry Asset
# -------------------------------------------------------------


class Geometry(Asset):

    def __init__(self, fileref):
        super().__init__(fileref)
        self.type = None
        
        self.channelsData: Channels = Channels(self)

        self.instances = self.nodes = {}

        self.verts = []
        self.faces = []
        self.polylines = []
        self.strands = []
        self.polygon_indices = []
        self.material_indices = []
        self.polygon_material_groups = []
        self.polygon_groups = []
        self.edge_weights = []
        self.mappings = {}
        self.material_group_vis = {}

        self.material_selection_sets = []
        
        self.isStrandHair = False
        self.vertex_count = 0
        self.poly_count = 0
        self.vertex_pairs = []
        self.dmaterials = []
        self.bumpareas = {}

        self.hidden_polys = []
        self.uv_set = None
        self.default_uv_set = None
        self.uv_sets = OrderedDict()
        self.rigidity = []

        self.root_region = None
        self.SubDIALevel = 0
        self.SubDRenderLevel = 0
        self.shstruct = {}
        self.shells = {}

    def __repr__(self):
        return ("<Geometry %s %s %s>" % (self.id, self.name, self.rna))

    def getInstance(self, ref, caller=None):
        iref = UtilityStatic.inst_ref(ref)
        if iref in self.nodes.keys():
            return self.nodes[iref]
        iref = unquote(iref)
        if iref in self.nodes.keys():
            return self.nodes[iref]
        else:
            return None

    def parse(self, struct):
        super().parse(struct)
        self.channelsData.parse(struct)

        self.verts = d2bList(struct["vertices"]["values"])
        fdata = struct["polylist"]["values"]
        self.faces = [f[2:] for f in fdata]
        self.polygon_indices = [f[0] for f in fdata]
        self.polygon_groups = struct["polygon_groups"]["values"]
        self.material_indices = [f[1] for f in fdata]
        self.polygon_material_groups = struct["polygon_material_groups"]["values"]

        for key, data in struct.items():
            if key == "polyline_list":
                self.polylines = data["values"]
            elif key == "edge_weights":
                self.edge_weights = data["values"]
            elif key == "default_uv_set":
                if uvset := self.get_children(url=data, key='Uvset'):
                    self.default_uv_set = self.uv_sets[uvset.name] = uvset
            elif key == "uv_set":
                if uvset := self.get_children(url=data, key='Uvset'):
                    self.uv_set = self.uv_sets[uvset.name] = uvset
            elif key == "graft":
                for key1, data1 in data.items():
                    if key1 == "vertex_count":
                        self.vertex_count = data1
                    elif key1 == "poly_count":
                        self.poly_count = data1
                    elif key1 == "hidden_polys":
                        self.hidden_polys = data1["values"]
                    elif key1 == "vertex_pairs":
                        self.vertex_pairs = data1["values"]
            elif key == "rigidity":
                self.rigidity = data
            elif key == "groups":
                self.groups.append(data)
            elif key == "root_region":
                self.root_region = data
            elif key == "type":
                self.type = data

        if self.uv_set is None:
            self.uv_set = self.default_uv_set
        return self

    def update(self, struct):
        super().update(struct)
        self.channelsData.update(struct)

        if "polygon_groups" in struct.keys():
            self.polygon_groups = struct["polygon_groups"]["values"]
        if "polygon_material_groups" in struct.keys():
            self.polygon_material_groups = struct["polygon_material_groups"]["values"]

        if "SubDIALevel" in self.channelsData.channels.keys():
            self.SubDIALevel = UtilityStatic.get_current_value(
                self.channelsData.channels["SubDIALevel"], 0)
        if "SubDRenderLevel" in self.channelsData.channels.keys():
            self.SubDRenderLevel = UtilityStatic.get_current_value(
                self.channelsData.channels["SubDRenderLevel"], 0)
        if self.SubDIALevel == 0 and "current_subdivision_level" in struct.keys():
            self.SubDIALevel = struct["current_subdivision_level"]

    def setExtra(self, extra):
        if extra["type"] == "studio/geometry/shell":
            self.shstruct = extra
        elif extra["type"] == "material_selection_sets":
            self.material_selection_sets = extra["material_selection_sets"]

    def isVisibleMaterial(self, dmat):
        if not self.material_group_vis.keys():
            return True
        label = dmat.name.rsplit("-", 1)[0]
        if label in self.material_group_vis.keys():
            return self.material_group_vis[label]
        else:
            return True

    def getPolyGroup(self, hidden):
        polyidxs = dict([(pgrp, n)
                         for n, pgrp in enumerate(self.polygon_groups)])
        hideidxs = {}
        for pgrp in hidden:
            if pgrp in polyidxs.keys():
                hideidxs[polyidxs[pgrp]] = True
            elif pgrp in self.mappings.keys():
                alt = self.mappings[pgrp]
                if alt in polyidxs.keys():
                    hideidxs[polyidxs[alt]] = True
        return [fn for fn, idx in enumerate(self.polygon_indices)
                if idx in hideidxs.keys()]

    def hidePolyGroup(self, ob, fnums):
        if not fnums:
            return
        mat = self.getHiddenMaterial()
        mnum = len(ob.data.materials)
        ob.data.materials.append(mat)
        for fn in fnums:
            f = ob.data.polygons[fn]
            f.material_index = mnum

    def getHiddenMaterial(self):
        if Settings.hiddenMaterial_:
            return Settings.hiddenMaterial_

        mat = Settings.hiddenMaterial_ = bpy.data.materials.new("HIDDEN")
        mat.diffuse_color[3] = 0
        mat.use_nodes = True
        mat.blend_method = 'CLIP'
        mat.shadow_method = 'NONE'

        tree = mat.node_tree
        tree.nodes.clear()

        node = tree.nodes.new(type="ShaderNodeBsdfTransparent")
        node.location = (0, 0)

        output = tree.nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (200, 0)

        tree.link(node.outputs["BSDF"], output.inputs["Surface"])
        
        return mat

    def preprocess(self, context, inst):
        if self.shstruct:
            self.uvs = {}
            for geonode in self.nodes.values():
                self.processShell(geonode, inst)

    def processShell(self, geonode, inst):
        for extra in geonode.channelsData.extra:
            if "type" not in extra.keys():
                pass
            elif extra["type"] == "studio/node/shell":
                if "material_uvs" in extra.keys():
                    self.uvs = dict(extra["material_uvs"])
        if Settings.mergeShells:
            if inst.node2:
                missing = self.addShells(
                    inst.node2, inst, self.material_group_vis)
                for mname, shmat, uv in missing:
                    msg = ("Missing shell material\n" +
                           "Material: %s\n" % mname +
                           "Node: %s\n" % geonode.name +
                           "Inst: %s\n" % inst.name +
                           "Node2: %s\n" % inst.node2.name +
                           "UV set: %s\n" % uv)
                    ErrorsStatic.report(msg, trigger=(2, 4))

    def addShells(self, inst, shinst, vis):
        missing = []
        geonode = inst.geometries[0]
        geo = geonode.data

        if shinst.shstruct:
            shgeonode = shinst.geometries[0]
            shname = shinst.name

            for mname, shmat in shgeonode.materials.items():
                if mname in vis.keys():
                    if not vis[mname]:
                        continue
                else:
                    print("Warning: no visibility for material %s" % mname)

                if (shmat.channelsData.getValue("getChannelCutoutOpacity", 1) == 0 or
                        shmat.channelsData.getValue("getChannelOpacity", 1) == 0):
                    continue
                uv = self.uvs[mname]
                if mname in geonode.materials.keys():
                    dmat = geonode.materials[mname]
                    if shname not in dmat.shells.keys():
                        dmat.shells[shname] = self.makeShell(shname, shmat, uv)
                    shmat.ignore = True
                    self.addNewUvset(uv, geo, inst)
                else:
                    missing.append((mname, shmat, uv))
        self.matused = []

        for mname, shmat, uv in missing:
            for key, child in inst.children.items():
                self.addMoreShells(child, mname, shname, shmat, uv, "")

        return [miss for miss in missing if miss[0] not in self.matused]

    def addMoreShells(self, inst, mname, shname, shmat, uv, pprefix):
        from daz_import.figure import FigureInstance
        if not isinstance(inst, FigureInstance):
            return
        if mname in self.matused:
            return
        geonode = inst.geometries[0]
        geo = geonode.data
        prefix = pprefix + inst.node.name + "_"
        n = len(prefix)
        if mname[0:n] == prefix:
            mname1 = mname[n:]
        else:
            mname1 = None
        if mname1 and mname1 in geonode.materials.keys():
            dmat = geonode.materials[mname1]
            mshells = dmat.shells
            if shname not in mshells.keys():
                mshells[shname] = self.makeShell(shname, shmat, uv)
            shmat.ignore = True
            self.addNewUvset(uv, geo, inst)
            self.matused.append(mname)
        else:
            for key, child in inst.children.items():
                self.addMoreShells(child, mname, shname, shmat, uv, prefix)

    def addNewUvset(self, uv, geo, inst):
        if uv not in geo.uv_sets.keys():
            uvset = self.findUvSet(uv, inst.node.id)
            if uvset:
                geo.uv_sets[uv] = geo.uv_sets[uvset.name] = uvset

    def findUvSet(self, uv, url):
        from daz_import.transfer import findFileRecursive

        path = os.path.dirname(url)
        folder = Collection.path("%s/UV Sets" % path, strict=False)

        if not folder:
            folder = Collection.path(path)

        file = ("%s.dsf" % uv)

        if not folder:
            return

        file = findFileRecursive(folder, file)

        if not file:
            return

        url = unquote("%s#%s" % (file, uv))
        url = Collection.relative(url)

        asset = self.get_children(url=url)

        if asset:
            print("Found UV set '%s' in '%s'" % (uv, unquote(url)))
            self.uv_sets[uv] = asset

        return asset

    def buildData(self, context, geonode, inst, center):
        if not isinstance(geonode, GeoNode):
            raise DazError("BUG buildData: Should be Geonode:\n  %s" % geonode)
        if (self.rna and not Settings.singleUser_):
            return

        if self.sourcing:
            asset = self.sourcing
            if isinstance(asset, Geometry):
                self.polygon_groups = asset.polygon_groups
                self.polygon_material_groups = asset.polygon_material_groups
            else:
                ErrorsStatic.report(f"BUG: Sourcing:\n{self}\n  asset",
                                    trigger=(2, 3))

        me = self.rna = bpy.data.meshes.new(geonode.getName())

        verts = self.verts
        edges = []
        faces = self.faces

        if isinstance(geonode, GeoNode) and geonode.verts:
            if geonode.edges:
                verts = geonode.verts
                edges = geonode.edges
            elif geonode.faces:
                verts = geonode.verts
                faces = geonode.faces
            elif self.polylines:
                verts = geonode.verts
            elif len(geonode.verts) == len(verts):
                verts = geonode.verts

        if not verts:
            self.addAllMaterials(me, geonode)
            return None

        if self.polylines:
            for pline in self.polylines:
                edges += [(pline[i-1], pline[i]) for i in range(3, len(pline))]
                pn = pline[0]
                mn = pline[1]
                lverts = [verts[vn] for vn in pline[2:]]
                self.strands.append((pn, mn, lverts))

        if Settings.fitFile_:
            me.from_pydata(verts, edges, faces)
        else:
            me.from_pydata([Vector(vco)-center for vco in verts], edges, faces)

        if len(faces) != len(me.polygons):
            msg = ("Not all faces were created:\n" +
                   "Geometry: '%s'\n" % self.name +
                   "\# DAZ faces: %d\n" % len(faces) +
                   "\# Blender polygons: %d\n" % len(me.polygons))
            ErrorsStatic.report(msg, trigger=(2, 3))

        if len(me.polygons) > 0:
            for fn, mn in enumerate(self.material_indices):
                f = me.polygons[fn]
                f.material_index = mn
                f.use_smooth = True

        if self.polylines:
            me.DazMatNums.clear()
            if me.polygons:
                me.DazHairType = 'SHEET'
            else:
                me.DazHairType = 'LINE'
            for pline in self.polylines:
                mnum = pline[1]
                for n in range(len(pline)-3):
                    item = me.DazMatNums.add()
                    item.a = mnum
        elif self.isStrandHair:
            me.DazHairType = 'TUBE'

        hasShells = self.addMaterials(me, geonode, context)
        for key, uvset in self.uv_sets.items():
            self.buildUVSet(context, uvset, me, False)
        self.buildUVSet(context, self.uv_set, me, True)
        if self.shells and self.uv_set != self.default_uv_set:
            self.buildUVSet(context, self.default_uv_set, me, False)

        for struct in self.material_selection_sets:
            if "materials" in struct.keys() and "name" in struct.keys():
                if struct["name"][0:8] == "Template":
                    continue
                items = me.DazMaterialSets.add()
                items.name = struct["name"]
                for mname in struct["materials"]:
                    item = items.names.add()
                    item.name = mname

        ob = bpy.data.objects.new(inst.name, me)
        from daz_import.Elements.Finger import getFingerPrint
        me.DazFingerPrint = getFingerPrint(ob)
        if hasShells:
            ob.DazVisibilityDrivers = True
        return ob

    def creaseEdges(self, context, ob):
        if self.edge_weights:
            from daz_import.Lib.BlenderVertexStatic import BlenderVertexStatic

            vertedges = BlenderVertexStatic.getVertEdges(ob)

            weights = {}
            for vn1, vn2, w in self.edge_weights:
                for e in vertedges[vn1]:
                    if vn2 in e.vertices:
                        weights[e.index] = w
            BlenderStatic.activate(context, ob)
            BlenderStatic.set_mode('EDIT')
            bm = bmesh.from_edit_mesh(ob.data)
            bm.edges.ensure_lookup_table()
            creaseLayer = bm.edges.layers.crease.verify()
            level = max(1, self.SubDIALevel + self.SubDRenderLevel)
            for en, w in weights.items():
                e = bm.edges[en]
                e[creaseLayer] = min(1.0, w/level)
            bmesh.update_edit_mesh(ob.data)
            BlenderStatic.set_mode('OBJECT')
            self.edge_weights = []

    def addMaterials(self, me, geonode, context):
        hasShells = False
        for mn, mname in enumerate(self.polygon_material_groups):
            dmat = None

            if mname in geonode.materials.keys():
                dmat = geonode.materials[mname]
            else:
                ref = self.fileref + "#" + mname
                dmat = self.get_children(url=ref)

            if dmat:
                if dmat.rna is None:
                    msg = ("Material without rna:\n  %s\n  %s\n  %s" %
                           (dmat, geonode, self))
                    ErrorsStatic.report(msg, trigger=(2, 3))
                    # return False
                me.materials.append(dmat.rna)
                self.dmaterials.append(dmat)
                if dmat.shells:
                    hasShells = True
                if dmat.uv_set and dmat.uv_set.checkSize(me):
                    self.uv_set = dmat.uv_set
                if Settings.useAutoSmooth:
                    me.use_auto_smooth = dmat.channelsData.getValue(
                        ["Smooth On"], False)
                    me.auto_smooth_angle = dmat.channelsData.getValue(
                        ["Smooth Angle"], 89.9)*VectorStatic.D
            else:
                if Settings.verbosity > 3:
                    mats = list(geonode.materials.keys())
                    mats.sort()
                    print("Existing materials:\n  %s" % mats)
                ErrorsStatic.report("Material \"%s\" not found in geometry %s" % (
                    mname, geonode.name), trigger=(2, 4))
                return False
        return hasShells

    def addAllMaterials(self, me, geonode):
        for key, dmat in geonode.materials.items():
            if dmat.rna:
                me.materials.append(dmat.rna)
                self.dmaterials.append(dmat)

    def getBumpArea(self, me, bumps):
        bump = list(bumps)[0]
        if bump not in self.bumpareas.keys():
            area = 0.0
            for mn, dmat in enumerate(self.dmaterials):
                use = (bump in dmat.geobump.keys())
                for shell in dmat.shells.values():
                    if bump in shell.material.geobump.keys():
                        use = True
                if use:
                    area += sum([f.area for f in me.polygons if f.material_index == mn])
            self.bumpareas[bump] = area
        return self.bumpareas[bump]

    def buildUVSet(self, context, uv_set, me, setActive):
        if uv_set:
            if uv_set.checkSize(me):
                uv_set.build(context, me, self, setActive)
            else:
                msg = ("Incompatible UV sets:\n  %s\n  %s" %
                       (me.name, uv_set.name))
                ErrorsStatic.report(msg, trigger=(2, 3))

    def buildRigidity(self, ob):
        from daz_import.Elements.Modifier import buildVertexGroup
        if self.rigidity:
            if "weights" in self.rigidity.keys():
                buildVertexGroup(
                    ob, "Rigidity", self.rigidity["weights"]["values"])
            if "groups" not in self.rigidity.keys():
                return
            for group in self.rigidity["groups"]:
                rgroup = ob.data.DazRigidityGroups.add()
                rgroup.id = group["id"]
                rgroup.rotation_mode = group["rotation_mode"]
                rgroup.scale_modes = " ".join(group["scale_modes"])
                for vn in group["reference_vertices"]["values"]:
                    vert = rgroup.reference_vertices.add()
                    vert.a = vn
                for vn in group["mask_vertices"]["values"]:
                    vert = rgroup.mask_vertices.add()
                    vert.a = vn

    def makeShell(self, shname, shmat: Asset, uv):
        first = False
        if shname not in self.shells.keys():
            first = True
            self.shells[shname] = []

        match = None

        for shell in self.shells[shname]:
            if shmat.channelsData.equal(shell.material.channelsData):
                if uv == shell.uv:
                    return shell
                else:
                    match = shell

        if not match:
            for shell in self.shells[shname]:
                shell.single = False

        shell = Shell(shname, shmat, uv, self, first, match)
        self.shells[shname].append(shell)
        return shell


def d2bList(verts):
    s = Settings.scale_
    if Settings.zup:
        return [[s*v[0], -s*v[2], s*v[1]] for v in verts]
    else:
        return [[s*v[0], s*v[1], s*v[2]] for v in verts]

# -------------------------------------------------------------
#   Shell
# -------------------------------------------------------------


class Shell:
    def __init__(self, shname, shmat, uv, geo, first, match):
        self.name = shname
        self.material = shmat
        self.uv = uv
        self.geometry = geo
        self.single = first
        self.match = match
        self.shader_object = None

    def __repr__(self):
        dmat = self.material
        return ("<Shell %s %s S:%s VectorStatic.D:%s>" % (self.name, dmat.name, self.single, dmat.getDiffuse()))

# -------------------------------------------------------------
#   UV Asset
# -------------------------------------------------------------


class Uvset(Asset):

    def __init__(self, fileref):
        super().__init__(fileref)

        self.uvs = []
        self.polyverts = []
        self.material = None
        self.built = []

    def __repr__(self):
        return ("<Uvset %s '%s' %d %d %s>" % (self.id, self.name, len(self.uvs), len(self.polyverts), self.material))

    def parse(self, struct):
        super().parse(struct)
        self.type = "uv_set"
        self.uvs = struct["uvs"]["values"]
        self.polyverts = struct["polygon_vertex_indices"]
        self.name = self.getLabel()
        return self

    def checkSize(self, me):
        if not self.polyverts:
            return True
        fnums = [pvi[0] for pvi in self.polyverts]
        fnums.sort()
        return (len(me.polygons) >= fnums[-1])

    def checkPolyverts(self, me, polyverts, error):
        uvnums = []
        for fverts in polyverts.values():
            uvnums += fverts
        if uvnums:
            uvmin = min(uvnums)
            uvmax = max(uvnums) + 1
        else:
            uvmin = uvmax = -1
        if (uvmin != 0 or uvmax != len(self.uvs)):
            msg = ("Vertex number mismatch.\n" +
                   "Expected mesh with %d UV vertices        \n" % len(self.uvs) +
                   "but %s has %d UV vertices." % (me.name, uvmax))
            if error:
                raise DazError(msg)
            else:
                print(msg)

    def getPolyVerts(self, me):
        polyverts = dict([(f.index, list(f.vertices)) for f in me.polygons])
        if self.polyverts:
            for fn, vn, uv in self.polyverts:
                f = me.polygons[fn]
                for n, vn1 in enumerate(f.vertices):
                    if vn1 == vn:
                        polyverts[fn][n] = uv
        return polyverts

    def build(self, context, me, geo, setActive):
        if self.name is None or me in self.built:
            return
        if len(me.polygons) == 0:
            print("NO UVs", me.name, self.name)
            return

        polyverts = self.getPolyVerts(me)
        self.checkPolyverts(me, polyverts, False)
        uvloop = makeNewUvloop(me, self.getLabel(), setActive)

        m = 0
        vnmax = len(self.uvs)
        nmats = len(geo.polygon_material_groups)
        ucoords = [[] for n in range(nmats)]
        for fn, f in enumerate(me.polygons):
            mn = geo.material_indices[fn]
            for n in range(len(f.vertices)):
                vn = polyverts[f.index][n]
                if vn < vnmax:
                    uv = self.uvs[vn]
                    uvloop.data[m].uv = uv
                    ucoords[mn].append(uv[0])
                m += 1

        for mn in range(nmats):
            if len(ucoords[mn]) > 0:
                umin = min(ucoords[mn])
                umax = max(ucoords[mn])
                if umax-umin <= 1:
                    udim = math.floor((umin+umax)/2)
                else:
                    udim = 0
                    if Settings.verbosity > 2:
                        print("UV coordinate difference %f - %f > 1" %
                              (umax, umin))
                self.fixUdims(context, mn, udim, geo)
        self.built.append(me)

    def fixUdims(self, context, mn, udim, geo):
        fixed = False
        key = geo.polygon_material_groups[mn]
        for geonode in geo.nodes.values():
            if key in geonode.materials.keys():
                dmat = geonode.materials[key]
                dmat.fixUdim(context, udim)
                fixed = True
        if not fixed:
            print("Material \"%s\" not found" % key)


def makeNewUvloop(me, name, setActive):
    uvtex = me.uv_layers.new()
    uvtex.name = name
    uvloop = me.uv_layers[-1]
    uvloop.active_render = setActive
    if setActive:
        me.uv_layers.active_index = len(me.uv_layers) - 1
    return uvloop


def addUvs(me, name, uvs, uvfaces):
    if not uvs:
        return
    uvloop = makeNewUvloop(me, name, True)
    m = 0
    for f in uvfaces:
        for vn in f:
            uvloop.data[m].uv = uvs[vn]
            m += 1

# -------------------------------------------------------------
#   Prune Uv textures
# -------------------------------------------------------------


def pruneUvMaps(ob):
    if ob.data is None or len(ob.data.uv_layers) <= 1:
        return
    print("Pruning UV maps")
    uvtexs = {}
    for uvtex in ob.data.uv_layers:
        uvtexs[uvtex.name] = [uvtex, uvtex.active_render]
    for mat in ob.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if (node.type == "ATTRIBUTE" and
                        node.attribute_name in uvtexs.keys()):
                    uvtexs[node.attribute_name][1] = True
                elif (node.type == "UVMAP" and
                      node.uv_map in uvtexs.keys()):
                    uvtexs[node.uv_map][1] = True
    for uvtex, used in uvtexs.values():
        if not used:
            ob.data.uv_layers.remove(uvtex)


@Registrar()
class DAZ_OT_PruneUvMaps(DazOperator, IsMesh):
    bl_idname = "daz.prune_uv_maps"
    bl_label = "Prune UV Maps"
    bl_description = "Remove unused UV maps"
    bl_options = {'UNDO'}

    def run(self, context):
        BlenderStatic.set_mode('OBJECT')
        for ob in BlenderStatic.selected_meshes(context):
            pruneUvMaps(ob)

# -------------------------------------------------------------
#   Collaps UDims
# -------------------------------------------------------------


def addUdimsToUVs(ob, restore, udim, vdim):
    mat = ob.data.materials[0]
    for uvloop in ob.data.uv_layers:
        m = 0
        for fn, f in enumerate(ob.data.polygons):
            mat = ob.data.materials[f.material_index]
            if restore:
                ushift = mat.DazUDim
                vshift = mat.DazVDim
            else:
                ushift = udim - mat.DazUDim
                vshift = vdim - mat.DazVDim
            for n in range(len(f.vertices)):
                uvloop.data[m].uv[0] += ushift
                uvloop.data[m].uv[1] += vshift
                m += 1


@Registrar()
class DAZ_OT_CollapseUDims(DazOperator):
    bl_idname = "daz.collapse_udims"
    bl_label = "Collapse UDIMs"
    bl_description = "Restrict UV coordinates to the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and not ob.DazUDimsCollapsed)

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.collapseUDims(ob)

    def collapseUDims(self, ob):
        from daz_import.Elements.UDIM import UDimStatic

        if ob.DazUDimsCollapsed:
            return
        ob.DazUDimsCollapsed = True
        addUdimsToUVs(ob, False, 0, 0)
        for mn, mat in enumerate(ob.data.materials):
            if mat.DazUDimsCollapsed:
                continue
            mat.DazUDimsCollapsed = True
            UDimStatic.add(mat, -mat.DazUDim, -mat.DazVDim)


@Registrar()
class DAZ_OT_RestoreUDims(DazOperator):
    bl_idname = "daz.restore_udims"
    bl_label = "Restore UDIMs"
    bl_description = "Restore original UV coordinates outside the [0:1] range"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.DazUDimsCollapsed)

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.restoreUDims(ob)

    def restoreUDims(self, ob):
        from daz_import.Elements.UDIM import UDimStatic
        if not ob.DazUDimsCollapsed:
            return
        ob.DazUDimsCollapsed = False
        addUdimsToUVs(ob, True, 0, 0)
        for mn, mat in enumerate(ob.data.materials):
            if not mat.DazUDimsCollapsed:
                continue
            mat.DazUDimsCollapsed = False
            UDimStatic.add(mat, mat.DazUDim, mat.DazVDim)


@Registrar()
class DAZ_OT_UDimsFromTextures(DazOperator):
    bl_idname = "daz.udims_from_textures"
    bl_label = "UDIMs From Textures"
    bl_description = "Restore UV coordinates based on texture names"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.udimsFromTextures(ob)

    def udimsFromTextures(self, ob):
        dims = {}
        print("Shift materials:")
        for mn, mat in enumerate(ob.data.materials):
            udim = vdim = 0
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if (node.type == 'TEX_IMAGE' and
                            node.image):
                        tile = node.image.name.rsplit("_", 1)[-1]
                        if len(tile) == 4 and tile.isdigit():
                            udim = (int(tile) - 1001) % 10
                            vdim = (int(tile) - 1001) // 10
            dims[mn] = (udim, vdim)
            print("  ", mat.name, udim, vdim)

        for uvloop in ob.data.uv_layers:
            m = 0
            for fn, f in enumerate(ob.data.polygons):
                udim, vdim = dims[f.material_index]
                for _ in f.vertices:
                    uvs = uvloop.data[m].uv
                    uvs[0] += udim - int(uvs[0])
                    uvs[1] += vdim - int(uvs[1])
                    m += 1

# -------------------------------------------------------------
#   Load UVs
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_LoadUV(DazOperator, DazFile, SingleFile, IsMesh):
    bl_idname = "daz.load_uv"
    bl_label = "Load UV Set"
    bl_description = "Load a UV set to the active mesh"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        from daz_import.Lib.Files import getFolders
        folders = getFolders(context.object, ["UV Sets/", ""])
        if folders:
            self.properties.filepath = folders[0]
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        ob = context.object
        me = ob.data

        Settings.clear()
        Settings.reset()
        Settings.scale_ = ob.DazScale
        Settings.useUV_ = True

        asset = FileAsset.create_by_url(self.filepath)
        if asset is None or len(asset.uvs) == 0:
            raise DazError("Not an UV asset:\n  '%s'" % self.filepath)

        for uvset in asset.uvs:
            polyverts = uvset.getPolyVerts(me)
            uvset.checkPolyverts(me, polyverts, True)
            uvloop = makeNewUvloop(me, uvset.getLabel(), False)
            vnmax = len(uvset.uvs)
            m = 0
            for fn, f in enumerate(me.polygons):
                for n in range(len(f.vertices)):
                    vn = polyverts[f.index][n]
                    if vn < vnmax:
                        uv = uvset.uvs[vn]
                        uvloop.data[m].uv = uv
                    m += 1

# ----------------------------------------------------------
#   Prune vertex groups
# ----------------------------------------------------------


@Registrar()
class DAZ_OT_LimitVertexGroups(DazPropsOperator):
    bl_idname = "daz.limit_vertex_groups"
    bl_label = "Limit Vertex Groups"
    bl_description = "Limit the number of vertex groups per vertex"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    limit: IntProperty(
        name="Limit",
        description="Max number of vertex group per vertex",
        default=4,
        min=1, max=10
    )

    def draw(self, context):
        self.layout.prop(self, "limit")

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.limitVertexGroups(ob)

    def limitVertexGroups(self, ob):
        deletes = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        weights = dict([(vgrp.index, []) for vgrp in ob.vertex_groups])
        for v in ob.data.vertices:
            data = [(g.weight, g.group) for g in v.groups]
            if len(data) > self.limit:
                data.sort()
                vnmin = len(data) - self.limit
                for w, gn in data[0:vnmin]:
                    deletes[gn].append(v.index)
                wsum = sum([w for w, gn in data[vnmin:]])
                for w, gn in data[vnmin:]:
                    weights[gn].append((v.index, w/wsum))
        for vgrp in ob.vertex_groups:
            vnums = deletes[vgrp.index]
            if vnums:
                vgrp.remove(vnums)
            for vn, w in weights[vgrp.index]:
                vgrp.add([vn], w, 'REPLACE')

# ----------------------------------------------------------
#   Finalize meshes
# ----------------------------------------------------------


@Registrar()
class DAZ_OT_FinalizeMeshes(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.finalize_meshes"
    bl_label = "Finalize Meshes"
    bl_description = "Remove internal properties from meshes.\nDisables some tools but may improve performance"
    bl_options = {'UNDO'}

    storeData: BoolProperty(
        name="Store Data",
        description="Store data in a file",
        default=True)

    overwrite: BoolProperty(
        name="Overwrite",
        description="Overwrite stored data",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "storeData")
        self.layout.prop(self, "overwrite")

    def invoke(self, context, event):
        ob = context.object
        if (ob.DazBlendFile and ob.DazBlendFile != bpy.data.filepath):
            self.storeData = False
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        from daz_import.Elements.Morph import getRigFromObject
        from daz_import.Lib import Json
        ob = context.object
        rig = getRigFromObject(ob)
        self.nothing = True
        if self.storeData:
            if not bpy.data.filepath:
                raise DazError("Save the blend file first")
            struct = {"filetype": "mesh_data", "meshes": []}
        else:
            struct = None
        for ob1 in rig.children:
            if ob1.type == 'MESH':
                self.finalizeMesh(ob1, struct)
        if ob.type == 'MESH' and ob not in rig.children:
            self.finalizeMesh(ob, struct)
        if self.nothing:
            print("Nothing to save.")
        elif self.storeData:
            rig.DazBlendFile = bpy.data.filepath
            folder, path = getMeshDataFile(bpy.data.filepath)
            if not os.path.exists(folder):
                os.makedirs(folder)
            if self.overwrite or not os.path.exists(path):
                Json.save(struct, path)
                print('Saved "%s"' % path)

    def finalizeMesh(self, ob, struct):
        from daz_import.Elements.Finger import getFingerPrint
        if self.storeData:
            ob.DazBlendFile = bpy.data.filepath
            mstruct = {}
            struct["meshes"].append(mstruct)
            mstruct["name"] = ob.name
            mstruct["finger_print"] = getFingerPrint(ob)
            mstruct["orig_finger_print"] = ob.data.DazFingerPrint
            origverts = [(int(item.name), item.a)
                         for item in ob.data.DazOrigVerts]
            origverts.sort()
            mstruct["orig_verts"] = origverts
            if origverts:
                self.nothing = False
        clearMeshProps(ob.data)


def clearMeshProps(me):
    me.DazRigidityGroups.clear()
    me.DazOrigVerts.clear()
    #me.DazFingerPrint = getFingerPrint(ob)
    me.DazGraftGroup.clear()
    me.DazMaskGroup.clear()
    me.DazMatNums.clear()
    me.DazMaterialSets.clear()
    me.DazHDMaterials.clear()


def getMeshDataFile(filepath):
    folder = os.path.dirname(filepath)
    folder = os.path.join(folder, "mesh_data")
    fname = os.path.splitext(os.path.basename(filepath))[0]
    path = os.path.join(folder, "%s.json" % fname)
    return folder, path


def restoreOrigVerts(ob, vcount):
    if len(ob.data.DazOrigVerts) > 0:
        return True, False
    elif not ob.DazBlendFile:
        return False, False
    folder, filepath = getMeshDataFile(ob.DazBlendFile)
    if not os.path.exists(filepath):
        print("%s does not exist" % filepath)
        return False, False
    from daz_import.Lib import Json
    from daz_import.Elements.Finger import getFingerPrint

    finger = getFingerPrint(ob)
    struct = Json.load(filepath)

    for mstruct in struct["meshes"]:
        if mstruct["finger_print"] == finger and mstruct["orig_verts"]:
            nverts = int(mstruct["orig_finger_print"].split("-")[0])
            if nverts == vcount or vcount < 0:
                me = ob.data
                me.DazOrigVerts.clear()
                for m, n in mstruct["orig_verts"]:
                    pg = me.DazOrigVerts.add()
                    pg.name = str(m)
                    pg.a = n
                me.DazFingerPrint = mstruct["orig_finger_print"]
                return True, True
    return False, False

# ----------------------------------------------------------
#   Initialize
# ----------------------------------------------------------


@Registrar.func
def register():
    from daz_import.Elements.Groups import DazIntGroup, DazFloatGroup, DazPairGroup, DazRigidityGroup, DazStringStringGroup, DazTextGroup

    bpy.types.Mesh.DazRigidityGroups = CollectionProperty(
        type=DazRigidityGroup)
    bpy.types.Mesh.DazOrigVerts = CollectionProperty(type=DazIntGroup)
    bpy.types.Mesh.DazFingerPrint = StringProperty(
        name="Original Fingerprint", default="")
    bpy.types.Mesh.DazGraftGroup = CollectionProperty(type=DazPairGroup)
    bpy.types.Mesh.DazMaskGroup = CollectionProperty(type=DazIntGroup)
    bpy.types.Mesh.DazMatNums = CollectionProperty(type=DazIntGroup)
    bpy.types.Mesh.DazVertexCount = IntProperty(default=0)
    bpy.types.Mesh.DazMaterialSets = CollectionProperty(
        type=DazStringStringGroup)
    bpy.types.Mesh.DazHDMaterials = CollectionProperty(type=DazTextGroup)
    bpy.types.Object.DazMultires = BoolProperty(default=False)
    bpy.types.Mesh.DazHairType = StringProperty(default='SHEET')

    bpy.types.Object.DazBlendFile = StringProperty(
        name="Blend File",
        description="Blend file where the object is defined",
        default="")
