from __future__ import annotations
import os
from mathutils import Vector, Quaternion, Matrix
from daz_import.Lib.Settings import Settings, Settings
from daz_import.Lib.Errors import DazError

from daz_import.Lib.Files import DbzFile, Json
from daz_import.Lib.Files.DBZ.DBZInfo import DBZInfo
from daz_import.Lib.Files.DBZ.DBZObject import DBZObject


class DBZ_Static:

    @classmethod
    def fitToFile(cls, filepath, nodes):        
        from daz_import.figure import FigureInstance        
        print("Fitting objects with dbz file...")
        
        filepath = cls.getFitFile(filepath)
        dbz = cls.load(filepath)
        subsurfaced = False
        unfitted = []
        taken = dict([(name, 0) for name in dbz.objects.keys()])
        takenfigs = dict([(name, []) for name in dbz.rigs.keys()])

        for node, inst in nodes:

            if inst is None:
                print("fitToFile inst is None:\n  ", node)
                continue
            if isinstance(inst, FigureInstance):
                if inst.node.name in dbz.rigs.keys():
                    dbz.fitFigure(inst, takenfigs)

            for geonode in inst.geometries:
                geo = geonode.data
                if geo is None:
                    continue
                nname = dbz.tryGetName(node.name)
                if (nname is None and
                        node.name[0].isdigit()):
                    nname = dbz.tryGetName("a"+node.name)

                if nname:
                    idx = taken[nname]
                    if idx >= len(dbz.objects[nname]):
                        msg = ("Too many instances of object %s: %d" %
                               (nname, idx))
                        ok = False
                    else:
                        base = dbz.objects[nname][idx]
                        highdef = None
                        if dbz.hdobjects:
                            try:
                                highdef = dbz.hdobjects[nname][idx]
                                print("Highdef", nname, highdef.lod,
                                      len(highdef.verts))
                            except KeyError:
                                pass
                        taken[nname] += 1
                        ok = True
                    if not ok:
                        print(msg)
                        unfitted.append(node)
                    elif subsurfaced:
                        if len(verts) < len(geo.verts):
                            msg = ("Mismatch %s, %s: %d < %d" % (
                                node.name, geo.name, len(base.verts), len(geo.verts)))
                            print(msg)
                        else:
                            geonode.verts = verts[0:len(geo.verts)]
                            geonode.center = base.center
                            geonode.highdef = highdef
                    else:
                        if len(base.verts) != len(geo.verts):
                            ok = False
                            for base1 in dbz.getAlternatives(nname):
                                if len(base1.verts) == len(geo.verts):
                                    geonode.verts = base1.verts
                                    geonode.center = base1.center
                                    geonode.highdef = highdef
                                    ok = True
                                    break
                            if not ok:
                                msg = ("Mismatch %s, %s: %d != %d. " % (node.name, geo.name, len(base.verts), len(geo.verts)) +
                                       "(OK for hair)")
                                print(msg)
                                geonode.verts = base.verts
                                geonode.edges = [e[0:2] for e in base.edges]
                                geonode.faces = [f[0] for f in base.faces]
                                geonode.properties = base.properties
                                geonode.center = base.center
                        else:
                            geonode.verts = base.verts
                            geonode.center = base.center
                            geonode.highdef = highdef
                elif len(geo.verts) == 0:
                    print("Zero verts:", node.name)
                    pass
                else:
                    unfitted.append(node)

        if unfitted:
            print("The following nodes were not found")
            print("and must be fitted manually:")
            for node in unfitted:
                print('    "%s"' % node.name)
            print("The following nodes were fitted:")
            for oname in dbz.objects.keys():
                print('    "%s"' % oname)

    @staticmethod
    def getFitFile(filepath) -> str:
        filename = os.path.splitext(filepath)[0]

        for ext in [".dbz", ".json"]:
            filepath = filename + ext
            if os.path.exists(filepath):
                return filepath

        raise DazError("Mesh fitting set to DBZ (JSON).\n" +
                       f"Export \"{filename}.dbz\"            \n" +
                       "from Daz Studio to fit to dbz file.\n" +
                       "See documentation for more information.")

    @staticmethod
    def load(filepath: str) -> DBZInfo:
        from daz_import.geometry import d2bList

        dbz = DBZInfo()
        struct = Json.load(filepath)

        if ("application" not in struct.keys() or
                struct["application"] not in ["export_basic_data", "export_to_blender", "export_highdef_to_blender"]):
            msg = ("The file\n" +
                   filepath + "           \n" +
                   "does not contain data exported from DAZ Studio")
            raise DazError(msg)

        for figure in struct["figures"]:
            if "num verts" in figure.keys() and figure["num verts"] == 0:
                continue

            if "center_point" in figure.keys():
                center = Vector(figure["center_point"])
            else:
                center = None

            name = figure["name"]
            if name not in dbz.objects.keys():
                dbz.objects[name] = []

            if "vertices" in figure.keys():
                verts = d2bList(figure["vertices"])
                edges = faces = uvs = matgroups = []
                props = {}

                if "edges" in figure.keys():
                    edges = figure["edges"]
                if "faces" in figure.keys():
                    faces = figure["faces"]
                if "uvs" in figure.keys():
                    uvs = figure["uvs"]
                if "material groups" in figure.keys():
                    matgroups = figure["material groups"]
                if "node" in figure.keys():
                    props = figure["node"]["properties"]
                dbz.objects[name].append(
                    DBZObject(verts, uvs, edges, faces, matgroups, props, 0, center))

            if Settings.useHighDef and "hd vertices" in figure.keys():
                Settings.useHDObjects_ = True
                if name not in dbz.hdobjects.keys():
                    dbz.hdobjects[name] = []
                verts = []
                faces = []
                lod = 0
                uvs = []
                matgroups = []
                props = {}
                for key, value in figure.items():
                    if key == "hd vertices":
                        verts = d2bList(value)
                    elif key == "subd level":
                        lod = value
                    elif key == "hd uvs":
                        uvs = value
                    elif key == "hd faces":
                        faces = value
                    elif key == "hd material groups":
                        matgroups = value
                dbz.hdobjects[name].append(
                    DBZObject(verts, uvs, [], faces, matgroups, props, lod, center))

            if "bones" not in figure.keys():
                continue

            restdata, transforms = {}, {}

            if name not in dbz.rigs.keys():
                dbz.rigs[name] = []

            dbz.rigs[name].append((restdata, transforms, center))

            for bone in figure["bones"]:
                head = Vector(bone["center_point"])
                tail = Vector(bone["end_point"])
                vec = tail - head

                if "ws_transform" in bone.keys():
                    ws = bone["ws_transform"]
                    wsmat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
                    head = Vector(ws[9:12])
                    tail = head + vec @ wsmat
                else:
                    head = Vector(bone["ws_pos"])
                    x, y, z, w = bone["ws_rot"]
                    quat = Quaternion((w, x, y, z))
                    rmat = quat.to_matrix().to_3x3()
                    ws = bone["ws_scale"]
                    smat = Matrix([ws[0:3], ws[3:6], ws[6:9]])
                    tail = head + vec @ smat @ rmat
                    wsmat = smat @ rmat
                if "orientation" in bone.keys():
                    orient = bone["orientation"]
                    xyz = bone["rotation_order"]
                    origin = bone["origin"]
                else:
                    orient = xyz = origin = None
                bname = bone["name"]
                rmat = wsmat.to_4x4()
                rmat.col[3][0:3] = Settings.scale_*head
                restdata[bname] = (head, tail, orient, xyz, origin, wsmat)
                transforms[bname] = (rmat, head, rmat.to_euler(), (1, 1, 1))

        return dbz
