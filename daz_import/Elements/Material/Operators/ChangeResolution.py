import bpy
import os
from typing import List
from bpy.props import IntProperty, BoolProperty
from daz_import.Lib import BlenderStatic


class ChangeResolution():
    steps: IntProperty(
        name="Steps",
        description="Resize original images with this number of steps",
        min=0, max=8,
        default=2)

    resizeAll: BoolProperty(
        name="Resize All",
        description="Resize all textures of the selected meshes",
        default=True)

    def __init__(self):
        self.filenames = []
        self.images = {}

    def getFileNames(self, paths: List[str]):
        for path in paths:
            fname = bpy.path.basename(self.getBasePath(path))

            self.filenames.append(fname)

    @classmethod
    def getAllTextures(cls, context):
        paths = {}
        for ob in BlenderStatic.selected_meshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    cls.getTreeTextures(mat.node_tree, paths)
                else:
                    cls.getSlotTextures(mat, paths)
            for psys in ob.particle_systems:
                cls.getSlotTextures(psys.settings, paths)
        return paths

    @staticmethod
    def getSlotTextures(mat, paths):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                paths[mtex.texture.image.filepath] = True

    @classmethod
    def getTreeTextures(cls, tree, paths):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE' and node.image:
                img = node.image
                if img.source == 'TILED':
                    folder, basename, ext = cls.getTiledPath(img.filepath)
                    for file1 in os.listdir(folder):
                        fname1, ext1 = os.path.splitext(file1)
                        if fname1[:-4] == basename and ext1 == ext:
                            path = os.path.join(
                                folder, "%s%s" % (fname1, ext1))
                            paths[path] = True
                else:
                    paths[img.filepath] = True
            elif node.type == 'GROUP':
                cls.getTreeTextures(node.node_tree, paths)

    @staticmethod
    def getTiledPath(filepath):
        path = bpy.path.abspath(filepath)
        path = bpy.path.reduce_dirs([path])[0]
        folder = os.path.dirname(path)

        fname, ext = os.path.splitext(bpy.path.basename(path))
        return folder, fname[:-4], ext

    def replaceTextures(self, context):        
        for ob in BlenderStatic.selected_meshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    self.resizeTree(mat.node_tree)
                else:
                    self.resizeSlots(mat)
            for psys in ob.particle_systems:
                self.resizeSlots(psys.settings)

    def resizeSlots(self, mat):
        for mtex in mat.texture_slots:
            if mtex and mtex.texture.type == 'IMAGE':
                img = self.replaceImage(mtex.texture.image)
                mtex.texture.image = img

    def resizeTree(self, tree):
        for node in tree.nodes.values():
            if node.type == 'TEX_IMAGE':
                img = self.replaceImage(node.image)
                node.image = img
                if img:
                    node.name = img.name
            elif node.type == 'GROUP':
                self.resizeTree(node.node_tree)

    @staticmethod
    def getBasePath(path):
        fname, ext = os.path.splitext(path)

        if fname[-5:] == "-res0":
            return "%s%s" % (fname[:-5], ext)
        elif fname[-5:-1] == "-res" and fname[-1].isdigit():
            return "%s%s" % (fname[:-5], ext)
        elif (fname[-10:-6] == "-res" and
              fname[-6].isdigit() and
              fname[-5] == "_" and
              fname[-4:].isdigit()):
            return "%s%s%s" % (fname[:-10], fname[-5:], ext)
        else:
            return path

    def replaceImage(self, img):
        if img is None:
            return None

        colorSpace = img.colorspace_settings.name

        if colorSpace not in self.images.keys():
            self.images[colorSpace] = {}

        images = self.images[colorSpace]

        path = self.getBasePath(img.filepath)
        filename = bpy.path.basename(path)

        if filename not in self.filenames:
            return img

        newname, newpath = self.getNewPath(path)

        if img.source == 'TILED':
            newname = newname[:-5]

        if newpath == img.filepath:
            return img
        elif newpath in images.keys():
            return images[newpath][1]
        elif newname in bpy.data.images.keys():
            return bpy.data.images[newname]
        else:
            try:
                newimg = self.loadNewImage(img, newpath)
            except RuntimeError:
                newimg = None

        if newimg:
            newimg.name = newname
            newimg.colorspace_settings.name = colorSpace
            newimg.source = img.source
            images[newpath] = (img, newimg)
            return newimg
        else:
            print('"%s" does not exist' % newpath)
            return img

    @classmethod
    def loadNewImage(cls, img, newpath):
        print('Replace "%s" with "%s"' % (img.filepath, newpath))

        if img.source == 'TILED':

            folder, basename, ext = cls.getTiledPath(newpath)

            newimg = None
            print("Tiles:")

            for file1 in os.listdir(folder):
                fname1, ext1 = os.path.splitext(file1)

                if fname1[:-4] == basename and ext1 == ext:
                    path = os.path.join(folder, file1)
                    img = bpy.data.images.load(path)
                    udim = int(fname1[-4:])

                    if newimg is None:
                        newimg = img
                        newimg.source = 'TILED'
                        tile = img.tiles[0]
                        tile.number = udim
                    else:
                        newimg.tiles.new(tile_number=udim)

                    print('  "%s"' % file1)
            return newimg
        else:
            return bpy.data.images.load(newpath)

    def getNewPath(self, path: str):
        base, ext = os.path.splitext(path)

        if self.steps == 0:
            newbase = base
        elif len(base) > 5 and base[-5] == "_" and base[-4:].isdigit():
            newbase = ("%s-res%d%s" % (base[:-5], self.steps, base[-5:]))
        else:
            newbase = ("%s-res%d" % (base, self.steps))

        newname = bpy.path.basename(newbase)
        newpath = newbase + ext

        return newname, newpath
