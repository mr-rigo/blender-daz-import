import bpy
from time import perf_counter
from daz_import.Lib.Files import MultiFile
from daz_import.Lib.Files import getExistingFilePath
from daz_import.Elements.Finger import isCharacter, getFingerPrint
from daz_import.Elements.Material import MaterialStatic
from daz_import.Elements.Morph import classifyShapekeys
from daz_import.merge import mergeUvLayers
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.utils import *

from .DazOptions import DazOperator, DazOptions
from .MorphTypeOptions import MorphTypeOptions
from daz_import.Lib import Registrar
from daz_import.Collection import Collection


@Registrar()
class EasyImportDAZ(DazOperator, DazOptions, MorphTypeOptions, MultiFile):
    """Load a DAZ File and perform the most common opertations"""
    bl_idname = "daz.easy_import_daz"
    bl_label = "Easy Import DAZ"
    bl_description = "Load a native DAZ file and perform the most common operations"
    bl_options = {'UNDO'}

    rigType: EnumProperty(
        items=[('DAZ', "DAZ", "Original DAZ rig"),
               ('CUSTOM', "Custom Shapes", "Original DAZ rig with custom shapes"),
               ('MHX', "MHX", "MHX rig"),
               ('RIGIFY', "Rigify", "Rigify")],
        name="Rig Type",
        description="Convert the main rig to a more animator-friendly rig",
        default='DAZ')

    mannequinType: EnumProperty(
        items=[('NONE', "None", "Don't make mannequins"),
               ('NUDE', "Nude", "Make mannequin for main mesh only"),
               ('ALL', "All", "Make mannequin from all meshes")],
        name="Mannequin Type",
        description="Add mannequin to meshes of this type",
        default='NONE')

    useEliminateEmpties: BoolProperty(
        name="Eliminate Empties",
        description="Delete non-hidden empties, parenting its children to its parent instead",
        default=True)

    useMergeRigs: BoolProperty(
        name="Merge Rigs",
        description="Merge all rigs to the main character rig",
        default=True)

    useCreateDuplicates: BoolProperty(
        name="Create Duplicate Bones",
        description="Create separate bones if several bones with the same name are found",
        default=False)

    useMergeMaterials: BoolProperty(
        name="Merge Materials",
        description="Merge identical materials",
        default=True)

    useMergeToes: BoolProperty(
        name="Merge Toes",
        description="Merge separate toes into a single toe bone",
        default=False)

    useTransferShapes: BoolProperty(
        name="Transfer Shapekeys",
        description="Transfer shapekeys from character to clothes",
        default=True)

    useMergeGeografts: BoolProperty(
        name="Merge Geografts",
        description="Merge selected geografts to active object.\nDoes not work with nested geografts.\nShapekeys are always transferred first",
        default=False)

    useMergeLashes: BoolProperty(
        name="Merge Lashes",
        description="Merge separate eyelash mesh to character.\nShapekeys are always transferred first",
        default=False)

    useConvertWidgets: BoolProperty(
        name="Convert To Widgets",
        description="Convert widget mesh to bone custom shapes",
        default=False)

    useMakeAllBonesPoseable: BoolProperty(
        name="Make All Bones Poseable",
        description="Add an extra layer of driven bones, to make them poseable",
        default=False)

    useFavoMorphs: BoolProperty(
        name="Use Favorite Morphs",
        description="Load a favorite morphs instead of loading standard morphs",
        default=False)

    favoPath: StringProperty(
        name="Favorite Morphs",
        description="Path to favorite morphs")

    useConvertHair: BoolProperty(
        name="Convert Hair",
        description="Convert strand-based hair to particle hair",
        default=False)

    addTweakBones: BoolProperty(
        name="Tweak Bones",
        description="Add tweak bones",
        default=True
    )

    useFingerIk: BoolProperty(
        name="Finger IK",
        description="Generate IK controls for fingers",
        default=False)

    def draw(self, context):
        DazOptions.draw(self, context)
        self.layout.separator()
        self.layout.prop(self, "useMergeMaterials")
        self.layout.prop(self, "useEliminateEmpties")
        self.layout.prop(self, "useMergeRigs")
        if self.useMergeRigs:
            self.subprop("useCreateDuplicates")
        self.layout.prop(self, "useMergeToes")
        self.layout.prop(self, "useFavoMorphs")
        if self.useFavoMorphs:
            self.layout.prop(self, "favoPath")
        MorphTypeOptions.draw(self, context)
        if self.useFavoMorphs or self.jcms or self.flexions:
            self.layout.prop(self, "useTransferShapes")
        self.layout.prop(self, "useMergeGeografts")
        self.layout.prop(self, "useMergeLashes")
        self.layout.prop(self, "useConvertWidgets")
        self.layout.prop(self, "useMakeAllBonesPoseable")
        self.layout.prop(self, "useConvertHair")
        self.layout.prop(self, "rigType")
        if self.rigType == 'MHX':
            self.subprop("addTweakBones")
            self.subprop("useFingerIk")
        elif self.rigType == 'RIGIFY':
            self.subprop("useFingerIk")
        self.layout.prop(self, "mannequinType")

    def invoke(self, context, event):
        self.favoPath = context.scene.DazFavoPath
        return MultiFile.invoke(self, context, event)

    def storeState(self, context):
        pass

    def restoreState(self, context):
        pass

    def run(self, context):
        filepaths = self.getMultiFiles(["duf", "dsf", "dse"])
        if len(filepaths) == 0:

            raise DazError("No valid files selected")
        if self.useFavoMorphs:
            self.favoPath = getExistingFilePath(self.favoPath, ".json")
        for filepath in filepaths:
            try:
                self.easyImport(context, filepath)
            except DazError as msg:
                raise DazError(msg)

    def easyImport(self, context, filepath):

        time1 = perf_counter()
        Collection.import_paths = [filepath]

        bpy.ops.daz.daz_import(
            skinColor=self.skinColor,
            clothesColor=self.clothesColor,
            fitMeshes=self.fitMeshes)

        if not Settings.objects_:
            raise DazError("No objects found")
        Settings.theSilentMode_ = True
        visibles = BlenderStatic.visible_objects(context)
        self.rigs = self.getTypedObjects(visibles, Settings.rigs_)
        self.meshes = self.getTypedObjects(visibles, Settings.meshes_)
        self.objects = self.getTypedObjects(visibles, Settings.objects_)
        self.hdmeshes = self.getTypedObjects(visibles, Settings.hdmeshes_)
        self.hairs = self.getTypedObjects(visibles, Settings.hairs_)

        if self.useEliminateEmpties:
            bpy.ops.object.select_all(action='DESELECT')
            for objects in Settings.objects_.values():
                for ob in objects:
                    BlenderObjectStatic.select(ob, True)
            bpy.ops.daz.eliminate_empties()

        for rigname in self.rigs.keys():
            self.treatRig(context, rigname)
        Settings.theSilentMode_ = False
        context.scene.DazFavoPath = self.favoPath
        time2 = perf_counter()
        print("File %s loaded in %.3f seconds" % (self.filepath, time2-time1))

    def getTypedObjects(self, visibles, struct):
        nstruct = {}
        for key, objects in struct.items():
            nstruct[key] = [ob for ob in objects if (ob and ob in visibles)]
        return nstruct

    def treatRig(self, context, rigname):

        rigs = self.rigs[rigname]
        meshes = self.meshes[rigname]
        objects = self.objects[rigname]
        hdmeshes = self.hdmeshes[rigname]
        hairs = self.hairs[rigname]
        if len(rigs) > 0:
            mainRig = rigs[0]
        else:
            mainRig = None
        if len(meshes) > 0:
            mainMesh = meshes[0]
        else:
            mainMesh = None
        if mainRig:
            mainChar = isCharacter(mainRig)
        else:
            mainChar = None
        if mainChar:
            print("Main character:", mainChar)
        elif mainMesh:
            print("Did not recognize main character", mainMesh.name)

        geografts = {}
        lashes = []
        clothes = []
        widgetMesh = None
        if mainMesh and mainRig:
            lmeshes = self.getLashes(mainRig, mainMesh)
            for ob in meshes[1:]:
                finger = getFingerPrint(ob)
                if ob.data.DazGraftGroup:
                    cob = self.getGraftParent(ob, meshes)
                    if cob:
                        if cob.name not in geografts.keys():
                            geografts[cob.name] = ([], cob)
                        geografts[cob.name][0].append(ob)
                    else:
                        clothes.append(ob)
                elif self.useConvertWidgets and finger == "1778-3059-1366":
                    widgetMesh = ob
                elif ob in lmeshes:
                    lashes.append(ob)
                else:
                    clothes.append(ob)

        if mainRig and BlenderStatic.activate(context, mainRig):
            # Merge rigs
            for rig in rigs[1:]:
                BlenderObjectStatic.select(rig, True)
            if self.useMergeRigs and len(rigs) > 1:
                print("Merge rigs")
                bpy.ops.daz.merge_rigs(
                    useCreateDuplicates=self.useCreateDuplicates)
                mainRig = context.object
                rigs = [mainRig]

            # Merge toes
            if BlenderStatic.activate(context, mainRig):
                if self.useMergeToes:
                    print("Merge toes")
                    bpy.ops.daz.merge_toes()

        if mainMesh and BlenderStatic.activate(context, mainMesh):
            # Merge materials
            for ob in meshes[1:]:
                BlenderObjectStatic.select(ob, True)
            print("Merge materials")
            bpy.ops.daz.merge_materials()

        if mainChar and mainRig and mainMesh:
            if self.useFavoMorphs:
                if BlenderStatic.activate(context, mainRig) and self.favoPath:
                    bpy.ops.daz.load_favo_morphs(filepath=self.favoPath)
            if (self.units or
                self.expressions or
                self.visemes or
                self.facs or
                self.facsexpr or
                self.body or
                self.jcms or
                    self.flexions):
                if BlenderStatic.activate(context, mainRig):
                    bpy.ops.daz.import_standard_morphs(
                        units=self.units,
                        expressions=self.expressions,
                        visemes=self.visemes,
                        facs=self.facs,
                        facsexpr=self.facsexpr,
                        body=self.body,
                        useMhxOnly=self.useMhxOnly,
                        jcms=self.jcms,
                        flexions=self.flexions)

        # Merge geografts
        if geografts:
            if self.useTransferShapes or self.useMergeGeografts:
                for aobs, cob in geografts.values():
                    if cob == mainMesh:
                        self.transferShapes(
                            context, cob, aobs, self.useMergeGeografts, "Body")
                for aobs, cob in geografts.values():
                    if cob != mainMesh:
                        self.transferShapes(
                            context, cob, aobs, self.useMergeGeografts, "All")
            if self.useMergeGeografts and BlenderStatic.activate(context, mainMesh):
                for aobs, cob in geografts.values():
                    for aob in aobs:
                        BlenderObjectStatic.select(aob, True)
                print("Merge geografts")
                bpy.ops.daz.merge_geografts()
                if Settings.viewportColors == 'GUESS':

                    Settings.skinColor_ = self.skinColor

                    for mat in mainMesh.data.materials:
                        MaterialStatic.guessMaterialColor(
                            mat, 'GUESS', True, Settings.skinColor_)

        # Merge lashes
        if lashes:
            if self.useTransferShapes or self.useMergeLashes:
                self.transferShapes(context, mainMesh, lashes,
                                    self.useMergeLashes, "Face")
            if self.useMergeLashes and BlenderStatic.activate(context, mainMesh):
                for ob in lashes:
                    BlenderObjectStatic.select(ob, True)
                print("Merge lashes")
                self.mergeLashes(mainMesh)

        # Transfer shapekeys to clothes
        if self.useTransferShapes:
            self.transferShapes(context, mainMesh, clothes, False, "Body")

        # Convert widget mesh to widgets
        if widgetMesh and mainRig and BlenderStatic.activate(context, widgetMesh):
            print("Convert to widgets")
            bpy.ops.daz.convert_widgets()

        if mainRig and BlenderStatic.activate(context, mainRig):
            # Make all bones poseable
            if self.useMakeAllBonesPoseable:
                print("Make all bones poseable")
                bpy.ops.daz.make_all_bones_poseable()

        # Convert hairs
        if (hairs and
            mainMesh and
            self.useConvertHair and
                BlenderStatic.activate(context, mainMesh)):
            bpy.ops.object.transform_apply(
                location=True, rotation=True, scale=True)
            for hair in hairs:
                if BlenderStatic.activate(context, hair):
                    BlenderObjectStatic.select(mainMesh, True)
                    bpy.ops.daz.make_hair(strandType='TUBE')

        # Change rig
        if mainRig and BlenderStatic.activate(context, mainRig):
            if self.rigType == 'CUSTOM':
                print("Add custom shapes")
                bpy.ops.daz.add_custom_shapes()
            elif self.rigType == 'MHX':
                print("Convert to MHX")
                bpy.ops.daz.convert_to_mhx(
                    addTweakBones=self.addTweakBones,
                    useFingerIk=self.useFingerIk,
                )
            elif self.rigType == 'RIGIFY':
                bpy.ops.daz.convert_to_rigify(
                    useDeleteMeta=True,
                    useFingerIk=self.useFingerIk)
                mainRig = context.object

        # Make mannequin
        if (mainRig and
            mainMesh and
            self.mannequinType != 'NONE' and
                BlenderStatic.activate(context, mainMesh)):
            if self.mannequinType == 'ALL':
                for ob in clothes:
                    BlenderObjectStatic.select(ob, True)
            print("Make mannequin")
            bpy.ops.daz.add_mannequin(
                useGroup=True, group="%s Mannequin" % mainRig.name)

        if mainMesh:
            mainMesh.update_tag()
        if mainRig:
            mainRig.update_tag()
            BlenderStatic.activate(context, mainRig)

    def getGraftParent(self, ob, meshes):
        for cob in meshes:
            if len(cob.data.vertices) == ob.data.DazVertexCount:
                return cob
        return None

    def transferShapes(self, context, ob, meshes, skipDrivers, bodypart):
        if not (ob and meshes):
            return

        skeys = ob.data.shape_keys
        if skeys:
            bodyparts = classifyShapekeys(ob, skeys)
            if bodypart == "All":
                snames = [sname for sname, bpart in bodyparts.items()]
            else:
                snames = [sname for sname, bpart in bodyparts.items() if bpart in [
                    bodypart, "All"]]
            if not snames:
                return
            BlenderStatic.activate(context, ob)
            selected = False
            for mesh in meshes:
                if self.useTransferTo(mesh):
                    BlenderObjectStatic.select(mesh, True)
                    selected = True
            if not selected:
                return
            Collection.import_paths = snames
            bpy.ops.daz.transfer_shapekeys(useDrivers=(not skipDrivers))

    def useTransferTo(self, mesh):
        if not BlenderStatic.modifier(mesh, 'ARMATURE'):
            return False
        ishair = ("head" in mesh.vertex_groups.keys() and
                  "lSldrBend" not in mesh.vertex_groups.keys())
        return not ishair

    def mergeLashes(self, ob):

        nlayers = len(ob.data.uv_layers)
        bpy.ops.object.join()
        idxs = list(range(nlayers, len(ob.data.uv_layers)))
        idxs.reverse()
        for idx in idxs:
            mergeUvLayers(ob.data, 0, idx)
        BlenderStatic.set_mode('EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        BlenderStatic.set_mode('OBJECT')
        print("Lashes merged")

    def getLashes(self, rig, ob):
        meshes = []
        for mesh in BlenderObjectStatic.mesh_children(rig):
            if mesh != ob:
                isLash = False
                for vgname in mesh.vertex_groups.keys():
                    if vgname[1:7] == "Eyelid":
                        isLash = True
                    elif vgname in ["lEye", "head"]:
                        isLash = False
                        break
                if isLash:
                    meshes.append(mesh)
        return meshes
