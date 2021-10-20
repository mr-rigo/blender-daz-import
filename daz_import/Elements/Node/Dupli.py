import bpy

from mathutils import Matrix
from daz_import.Lib.Settings import Settings
from daz_import.Lib.BlenderStatic import BlenderStatic
from .NodeStatic import findLayerCollection, NodeStatic


class Dupli:

    def __init__(self, ob, refcoll, parcoll):
        self.object = ob
        self.refcoll = refcoll
        self.parcoll = parcoll

        obname = ob.name
        ob.name = refcoll.name

        self.empty = bpy.data.objects.new(obname, None)
        self.empty.instance_type = 'COLLECTION'
        self.empty.instance_collection = self.refcoll

        parcoll.objects.link(self.empty)

    def addToRefColl(self, ob):
        if ob.name in self.parcoll.objects:
            self.parcoll.objects.unlink(ob)

        NodeStatic.addToCollection(ob, self.refcoll)

        for child in ob.children:
            self.addToRefColl(child)

    def excludeRefColl(self, toplayer):
        layer = findLayerCollection(toplayer, self.refcoll)
        layer.exclude = True

    def storeTransforms(self, wmats):
        ob = self.object
        wmat = ob.matrix_world.copy()
        wmats[ob.name] = (ob, wmat)

        for child in ob.children:
            wmat = child.matrix_world.copy()
            wmats[child.name] = (child, wmat)

    def transformEmpty(self):
        ob = self.object
        wmat = ob.matrix_world.copy()
        self.empty.parent = ob.parent

        BlenderStatic.world_matrix(self.empty, wmat)

        ob.parent = None
        ob.matrix_world = Matrix()

    @staticmethod
    def transformDuplis(context):
        wmats = {}

        for dupli in Settings.duplis_.values():
            dupli.storeTransforms(wmats)

        for dupli in Settings.duplis_.values():
            dupli.transformEmpty()

        for dupli in Settings.duplis_.values():
            dupli.addToRefColl(dupli.object)

        toplayer = context.view_layer.layer_collection

        for dupli in Settings.duplis_.values():
            dupli.excludeRefColl(toplayer)


transformDuplis = Dupli.transformDuplis
