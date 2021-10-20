from daz_import.Elements.Assets import Assets
from daz_import.Lib.Errors import ErrorsStatic
from .Modifier import Modifier


class DForm(Modifier):
    def __init__(self, fileref):
        Modifier.__init__(self, fileref)
        self.parent = None
        self.dform = {}

    def __repr__(self):
        return ("<Dform %s>" % (self.id))

    def parse(self, struct):
        Modifier.parse(self, struct)
        self.dform = struct["dform"]        
        self.parent = self.get_children(url=struct["parent"])

    def update(self, struct):
        Modifier.update(self, struct)

    def build(self, context, inst):
        ob, rig, geonode = self.getGeoRig(context, inst)

        if ob is None or ob.type != 'MESH':
            return

        if ("influence_vertex_count" in self.dform.keys() and
                "influence_weights" in self.dform.keys()):
            vcount = self.dform["influence_vertex_count"]
            if vcount != len(ob.data.vertices) and vcount >= 0:
                msg = "Dform vertex count mismatch %d != %d" % (
                    vcount, len(ob.data.vertices))
                ErrorsStatic.report(msg, trigger=(2, 3))
            vgrp = ob.vertex_groups.new(name="Dform " + self.name)
            for vn, w in self.dform["influence_weights"]["values"]:
                vgrp.add([vn], w, 'REPLACE')
        elif "mask_bone" in self.dform.keys():
            pass
        else:
            print("DFORM", self.dform.keys())
