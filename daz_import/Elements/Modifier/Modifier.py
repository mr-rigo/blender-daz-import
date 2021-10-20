from daz_import.Elements.Assets import Asset
from daz_import.Lib.Errors import ErrorsStatic


class Modifier(Asset):
    def __init__(self, fileref):
        Asset.__init__(self, fileref)

        self.groups = []

    def parse(self, data: dict):
        super().parse(data)
        if groups := data.get("groups"):
            self.groups = groups

    def update(self, struct):
        Asset.update(self, struct)
        if "groups" in struct.keys():
            self.groups = struct["groups"]

    def __repr__(self):
        return ("<Modifier %s>" % (self.id))

    def preprocess(self, inst):
        pass

    def postbuild(self, context, inst):
        pass

    def getGeoRig(self, context, inst):
        from daz_import.geometry import GeoNode
        from daz_import.figure import FigureInstance
        if isinstance(inst, GeoNode):
            # This happens for normal scenes
            ob = inst.rna
            if ob:
                rig = ob.parent
            else:
                rig = None
            return ob, rig, inst
        elif isinstance(inst, FigureInstance):
            # This happens for library characters
            rig = inst.rna
            if inst.geometries:
                geonode = inst.geometries[0]
                ob = geonode.rna
            else:
                ob = geonode = None
            return ob, rig, geonode
        else:
            msg = ("Expected geonode or figure but got:\n  %s" % inst)
            ErrorsStatic.report(msg, trigger=(2, 3))
            return None, None, None
