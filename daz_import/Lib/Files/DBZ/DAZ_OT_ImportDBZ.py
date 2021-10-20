from __future__ import annotations
import os
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import DazOperator, IsMesh
from daz_import.Lib.Files import MultiFile, DbzFile
from daz_import.Lib import Registrar
from daz_import.Lib.Files.DBZ.DBZ_Static import DBZ_Static
from daz_import.Lib import BlenderStatic


@Registrar()
class DAZ_OT_ImportDBZ(DazOperator, DbzFile, MultiFile):
    bl_idname = "daz.import_dbz"
    bl_label = "Import DBZ Morphs"
    bl_description = "Import DBZ or JSON file(s) (*.dbz, *.json) as morphs"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        
        objects = BlenderStatic.selected_meshes(context)
        if not objects:
            return

        Settings.scale_ = objects[0].DazScale

        for path in self.getMultiFiles(["dbz", "json"]):
            for ob in objects:
                self.buildDBZMorph(ob, path)

    @classmethod
    def buildDBZMorph(cls, ob, filepath):    
        dbz = DBZ_Static.load(filepath)

        if not ob.data.shape_keys:
            basic = ob.shape_key_add(name="Basic")
        else:
            basic = ob.data.shape_keys.key_blocks[0]

        sname = os.path.basename(os.path.splitext(filepath)[0])

        if sname in ob.data.shape_keys.key_blocks.keys():
            skey = ob.data.shape_keys.key_blocks[sname]
            ob.shape_key_remove(skey)

        if cls.makeShape(ob, sname, dbz.objects):
            return
        elif cls.makeShape(ob, sname, dbz.hdobjects):
            return
        else:
            print("No matching morph found")

    @staticmethod
    def makeShape(ob, sname, objects):
        for name in objects.keys():
            verts = objects[name][0].verts
            print("Try %s (%d verts)" % (name, len(verts)))
            if len(verts) == len(ob.data.vertices):
                skey = ob.shape_key_add(name=sname)
                for vn, co in enumerate(verts):
                    skey.data[vn].co = co
                print("Morph %s created" % sname)
                return True
        return False
