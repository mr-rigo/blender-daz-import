
from daz_import.Lib import Registrar, BlenderStatic
from daz_import.Lib.Errors import DazPropsOperator, IsMesh, DazError
from bpy.props import BoolProperty


@Registrar()
class DAZ_OT_CopyMaterials(DazPropsOperator):
    bl_idname = "daz.copy_materials"
    bl_label = "Copy Materials"
    bl_description = "Copy materials from active mesh to selected meshes"
    bl_options = {'UNDO'}
    pool = IsMesh.pool
    
    useMatchNames: BoolProperty(
        name="Match Names",
        description="Match materials based on names rather than material number",
        default=False)

    errorMismatch: BoolProperty(
        name="Error On Mismatch",
        description="Raise an error if the number of source and target materials are different",
        default=True)

    def draw(self, context):
        self.layout.prop(self, "useMatchNames")
        self.layout.prop(self, "errorMismatch")

    def run(self, context):
        src = context.object
        self.mismatch = ""
        found = False

        for trg in BlenderStatic.selected_meshes(context):
            if trg != src:
                self.copyMaterials(src, trg)
                found = True

        if not found:
            raise DazError("No target mesh selected")

        if self.mismatch:
            msg = "Material number mismatch.\n" + self.mismatch
            raise DazError(msg, warning=True)

    def copyMaterials(self, src, trg):
        ntrgmats = len(trg.data.materials)
        nsrcmats = len(src.data.materials)

        if ntrgmats != nsrcmats:
            self.mismatch += ("\n%s (%d materials) != %s (%d materials)"
                              % (src.name, nsrcmats, trg.name, ntrgmats))
            if self.errorMismatch:
                msg = "Material number mismatch.\n" + self.mismatch
                raise DazError(msg)

        mnums = [(f, f.material_index) for f in trg.data.polygons]
        srclist = [(mat.name, mn, mat)
                   for mn, mat in enumerate(src.data.materials)]
        trglist = [(mat.name, mn, mat)
                   for mn, mat in enumerate(trg.data.materials)]

        trgrest = trglist[nsrcmats:ntrgmats]
        trglist = trglist[:nsrcmats]
        srcrest = srclist[ntrgmats:nsrcmats]
        srclist = srclist[:ntrgmats]

        if self.useMatchNames:
            srclist.sort()
            trglist.sort()
            trgmats = {}
            for n, data in enumerate(srclist):
                mat = data[2]
                tname, mn, _tmat = trglist[n]
                trgmats[mn] = mat
                mat.name = tname
            trgmats = list(trgmats.items())
            trgmats.sort()
        else:
            trgmats = [data[1:3] for data in srclist]

        trg.data.materials.clear()

        for _mn, mat in trgmats:
            trg.data.materials.append(mat)

        for _, _, mat in trgrest:
            trg.data.materials.append(mat)

        for f, mn in mnums:
            f.material_index = mn
