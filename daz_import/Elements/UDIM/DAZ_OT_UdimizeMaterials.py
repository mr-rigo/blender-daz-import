import bpy
import os
from bpy.props import BoolProperty, EnumProperty

from daz_import.Elements.UDIM import UDimStatic
from daz_import.Lib.Errors import DazPropsOperator, DazError
from daz_import.Elements.Material import MaterialSelector
from daz_import.Lib import Registrar


def getTargetMaterial(scn, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]


@Registrar((2, 82, 0))
class DAZ_OT_UdimizeMaterials(DazPropsOperator, MaterialSelector):
    bl_idname = "daz.make_udim_materials"
    bl_label = "Make UDIM Materials"
    bl_description = "Combine materials of selected mesh into a single UDIM material"
    bl_options = {'UNDO'}

    trgmat: EnumProperty(items=getTargetMaterial, name="Active")

    useFixTiles: BoolProperty(
        name="Fix UV tiles",
        description="Move UV vertices to the right tile automatically",
        default=True)

    useMergeMaterials: BoolProperty(
        name="Merge Materials",
        description="Merge materials and not only textures.\nIf on, some info may be lost.\nIf off, Merge Materials must be called afterwards",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "useFixTiles")
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "trgmat")
        self.layout.label(text="Materials To Merge")
        MaterialSelector.draw(self, context)

    def invoke(self, context, event):
        ob = context.object
        if not ob.DazLocalTextures:
            from daz_import.Lib.Errors import ErrorsStatic
            ErrorsStatic.invoke("Save local textures first")
            return {'CANCELLED'}
        self.setupMaterials(ob)
        return DazPropsOperator.invoke(self, context, event)

    def isDefaultActive(self, mat):
        return self.isSkinRedMaterial(mat)

    def run(self, context):
        from shutil import copyfile

        ob = context.object
        mats = []
        mnums = []
        amat = None
        for mn, umat in enumerate(self.umats):
            if umat.bool:
                mat = ob.data.materials[umat.name]
                mats.append(mat)
                mnums.append(mn)
                if amat is None or mat.name == self.trgmat:
                    amat = mat
                    amnum = mn
                    atile = 1001 + mat.DazUDim

        if amat is None:
            raise DazError("No materials selected")

        self.nodes = {}
        for mat in mats:
            self.nodes[mat.name] = self.getChannels(mat)

        if self.useFixTiles:
            for f in ob.data.polygons:
                f.select = False
            for mn, mat in zip(mnums, mats):
                self.fixTiles(mat, mn, ob)

        for key, anode in self.nodes[amat.name].items():
            if anode.image.source == "TILED":
                raise DazError("Material %s already UDIM  " % amat.name)
            anode.image.source = "TILED"
            anode.extension = "CLIP"
            if anode.image:
                imgname = anode.image.name
            else:
                imgname = anode.name
            basename = "T_%s" % self.getBaseName(imgname, amat.DazUDim)
            udims = {}
            for mat in mats:
                nodes = self.nodes[mat.name]
                if key in nodes.keys():
                    node = nodes[key]
                    img = node.image
                    self.updateImage(img, basename, mat.DazUDim)
                    if mat.DazUDim not in udims.keys():
                        udims[mat.DazUDim] = mat.name
                    if mat == amat:
                        img.name = self.makeImageName(basename, atile, img)
                        node.label = basename
                        node.name = basename

            img = anode.image
            tile0 = img.tiles[0]
            for udim, mname in udims.items():
                if udim == 0:
                    tile0.number = 1001
                    tile0.label = mname
                else:
                    img.tiles.new(tile_number=1001+udim, label=mname)

        if self.useMergeMaterials:
            for f in ob.data.polygons:
                if f.material_index in mnums:
                    f.material_index = amnum

            mnums.reverse()
            for mn in mnums:
                if mn != amnum:
                    ob.data.materials.pop(index=mn)
        else:
            anodes = self.nodes[amat.name]
            for mat in mats:
                if mat != amat:
                    nodes = self.nodes[mat.name]
                    for key, node in nodes.items():
                        if key in anodes.keys():
                            anode = anodes[key]
                            img = node.image = anode.image
                            node.extension = "CLIP"
                            node.label = anode.label
                            node.name = anode.name

    def makeImageName(self, basename, tile, img):
        return "%s%s" % (basename, os.path.splitext(img.name)[1])

    def fixTiles(self, mat, mn, ob):
        for node in self.nodes[mat.name].values():
            if node.image:
                imgname = node.image.name
                if imgname[-4:].isdigit():
                    tile = int(imgname[-4:]) - 1001
                elif (imgname[-8:-4].isdigit() and
                      imgname[-4] == "." and
                      imgname[-3:].isdigit()):
                    tile = int(imgname[-8:-4]) - 1001
                else:
                    continue
                if mat.DazUDim != tile:
                    UDimStatic.shiftUVs(mat, mn, ob, tile)
                return

    def getChannels(self, mat):
        channels = {}
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                channel = self.getChannel(node, mat.node_tree.links)
                channels[channel] = node
        return channels

    def getChannel(self, node, links):
        for link in links:
            if link.from_node == node:
                if link.to_node.type in ["MIX_RGB", "MATH"]:
                    return self.getChannel(link.to_node, links)
                elif link.to_node.type == "BSDF_PRINCIPLED":
                    return ("PBR_%s" % link.to_socket.name)
                elif link.to_node.type == 'GROUP':
                    return link.to_node.node_tree.name
                else:
                    return link.to_node.type
        return None

    def getBaseName(self, string, udim):
        du = str(1001 + udim)
        if string[-4:] == du:
            string = string[:-4]
            if string[-1] in ["_", "-"]:
                string = string[:-1]
        return string

    def updateImage(self, img, basename, udim):
        from shutil import copyfile
        src = bpy.path.abspath(img.filepath)
        src = bpy.path.reduce_dirs([src])[0]
        folder = os.path.dirname(src)
        fname, ext = os.path.splitext(bpy.path.basename(src))
        trg = os.path.join(folder, "%s_%d%s" % (basename, 1001+udim, ext))
        if src != trg and not os.path.exists(trg):
            print("Copy %s\n => %s" % (src, trg))
            copyfile(src, trg)
        img.filepath = bpy.path.relpath(trg)
