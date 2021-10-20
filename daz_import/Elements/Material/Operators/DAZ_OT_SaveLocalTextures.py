import os
import bpy
from daz_import.Lib import Registrar
from daz_import.Lib.Errors import DazPropsOperator
from bpy.props import BoolProperty
from daz_import.Lib import BlenderStatic


@Registrar()
class DAZ_OT_SaveLocalTextures(DazPropsOperator):
    bl_idname = "daz.save_local_textures"
    bl_label = "Save Settings Textures"
    bl_description = "Copy textures to the textures subfolder in the blend file's directory"
    bl_options = {'UNDO'}

    keepdirs: BoolProperty(
        name="Keep Directories",
        description="Keep the directory tree from Daz Studio, otherwise flatten the directory structure",
        default=True)

    @classmethod
    def poll(self, context):
        return bpy.data.filepath

    def draw(self, context):
        self.layout.prop(self, "keepdirs")

    def run(self, context):
        from shutil import copyfile

        texpath = os.path.join(os.path.dirname(bpy.data.filepath), "textures")
        print("Save textures to '%s'" % texpath)

        if not os.path.exists(texpath):
            os.makedirs(texpath)

        self.images = []

        for ob in BlenderStatic.visible_meshes(context):
            for mat in ob.data.materials:
                if mat:
                    if mat.use_nodes:
                        self.saveNodesInTree(mat.node_tree)
            for psys in ob.particle_systems:
                self.saveTextureSlots(psys.settings)
            ob.DazLocalTextures = True

        for img in self.images:
            src = bpy.path.abspath(img.filepath)
            src = bpy.path.reduce_dirs([src])[0]
            file = bpy.path.basename(src)
            srclower = src.lower().replace("\\", "/")
            if self.keepdirs and "/textures/" in srclower:
                subpath = os.path.dirname(srclower.rsplit("/textures/", 1)[1])
                folder = os.path.join(texpath, subpath)
                if not os.path.exists(folder):
                    print("Make %s" % folder)
                    os.makedirs(folder)
                trg = os.path.join(folder, file)
            else:
                trg = os.path.join(texpath, file)
            if src != trg and not os.path.exists(trg):
                print("Copy %s\n => %s" % (src, trg))
                copyfile(src, trg)
            img.filepath = bpy.path.relpath(trg)

    def saveNodesInTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                self.images.append(node.image)
            elif node.type == 'GROUP':
                self.saveNodesInTree(node.node_tree)

    def saveTextureSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex:
                tex = mtex.texture
                if hasattr(tex, "image") and tex.image:
                    self.images.append(tex.image)
