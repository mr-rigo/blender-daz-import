import os
import bpy

from daz_import.Lib import Registrar
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.utils import *
from daz_import.Lib.Files import SingleFile, JsonFile, JsonExportFile
from .Material import EnumsHair, EnumsMaterials
from daz_import.Blender.SceneStatic import SceneStatic


def showBox(scn, attr, layout):
    if not getattr(scn, attr):
        layout.prop(scn, attr, icon="RIGHTARROW", emboss=False)
        return False
    else:
        layout.prop(scn, attr, icon="DOWNARROW_HLT", emboss=False)
        return True


@Registrar()
class DAZ_OT_SetSilentMode(bpy.types.Operator):
    bl_idname = "daz.set_silent_mode"
    bl_label = "Silent Mode"
    bl_description = "Toggle silent mode on or off (error popups off or on)"

    def execute(self, context):
        Settings.theSilentMode_ = (not Settings.theSilentMode_)
        return {'FINISHED'}


@Registrar()
class DAZ_OT_AddContentDir(bpy.types.Operator):
    bl_idname = "daz.add_content_dir"
    bl_label = "Add Content Directory"
    bl_description = "Add a content directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        pg = context.scene.DazContentDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_AddMDLDir(bpy.types.Operator):
    bl_idname = "daz.add_mdl_dir"
    bl_label = "Add MDL Directory"
    bl_description = "Add an MDL directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        pg = context.scene.DazMDLDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_AddCloudDir(bpy.types.Operator):
    bl_idname = "daz.add_cloud_dir"
    bl_label = "Add Cloud Directory"
    bl_description = "Add a cloud directory"
    bl_options = {'UNDO'}

    def execute(self, context):
        pg = context.scene.DazCloudDirs.add()
        pg.name = ""
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_SaveSettingsFile(bpy.types.Operator, SingleFile, JsonExportFile):
    bl_idname = "daz.save_settings_file"
    bl_label = "Save Settings File"
    bl_description = "Save current settings to file"
    bl_options = {'UNDO'}

    def execute(self, context):
        SceneStatic.fromScene(context.scene)
        Settings.save()
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        # self.properties.filepath = os.path.dirname(Settings.__settingsPath_)
        return SingleFile.invoke(self, context, event)


@Registrar()
class DAZ_OT_LoadFactorySettings(DazOperator):
    bl_idname = "daz.load_factory_settings"
    bl_label = "Load Factory Settings"
    bl_description = "Restore all global settings to factory defaults"
    bl_options = {'UNDO'}

    def execute(self, context):
        Settings.__init__()
        SceneStatic.toScene(context.scene)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_LoadRootPaths(DazOperator, SingleFile, JsonFile):
    bl_idname = "daz.load_root_paths"
    bl_label = "Load Root Paths"
    bl_description = "Load DAZ root paths from file"
    bl_options = {'UNDO'}

    useContent: BoolProperty(
        name="Load Content Directories",
        default=True)

    useMDL: BoolProperty(
        name="Load MDL Directories",
        default=True)

    useCloud: BoolProperty(
        name="Load Cloud Directories",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "useContent")
        self.layout.prop(self, "useMDL")
        self.layout.prop(self, "useCloud")

    def execute(self, context):
        from daz_import.Lib.Files import Json

        if struct := Json.load_setting(self.filepath):
            print("Load root paths from", self.filepath)
            SceneStatic.readDazPaths(struct, self)
            SceneStatic.toScene(context.scene)
        else:
            print("No root paths found in", self.filepath)

        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_LoadSettingsFile(DazOperator, SingleFile, JsonFile):
    bl_idname = "daz.load_settings_file"
    bl_label = "Load Settings File"
    bl_description = "Load settings from file"
    bl_options = {'UNDO'}

    def execute(self, context):
        Settings.load()
        SceneStatic.toScene(context.scene)
        print("Settings file %s saved" % self.filepath)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        # self.properties.filepath = os.path.dirname(Settings.__settingsPath_)
        return SingleFile.invoke(self, context, event)


@Registrar()
class DAZ_OT_GlobalSettings(DazOperator):
    bl_idname = "daz.global_settings"
    bl_label = "Settings Settings"
    bl_description = "Show or update global settings"

    def draw(self, context):
        scn = context.scene
        split = self.layout.split(factor=0.4)
        col = split.column()
        box = col.box()
        box.label(text="DAZ Studio Root Directories")
        if showBox(scn, "DazShowContentDirs", box):
            for pg in scn.DazContentDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_content_dir")
        if showBox(scn, "DazShowMDLDirs", box):
            for pg in scn.DazMDLDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_mdl_dir")
        if showBox(scn, "DazShowCloudDirs", box):
            for pg in scn.DazCloudDirs:
                box.prop(pg, "name", text="")
            box.operator("daz.add_cloud_dir")
        box.label(text="Path To Output Errors:")
        box.prop(scn, "DazErrorPath", text="")

        col = split.column()
        box = col.box()
        box.label(text="General")
        box.prop(scn, "DazUnitScale")
        box.prop(scn, "DazVerbosity")
        box.prop(scn, "DazCaseSensitivePaths")

        box = col.box()
        box.label(text="Debugging")
        box.prop(scn, "DazZup")
        box.prop(scn, "DazUnflipped")
        box.prop(scn, "DazDump")
        box.prop(scn, "DazShowHiddenObjects")
        box.prop(scn, "DazPruneNodes")
        box.prop(scn, "DazMergeShells")

        box = col.box()
        box.label(text="Meshes")
        box.prop(scn, "DazHighdef")
        box.prop(scn, "DazMultires")
        box.prop(scn, "DazMultiUvLayers")
        box.prop(scn, "DazUseAutoSmooth")
        box.prop(scn, "DazUseInstancing")
        box.prop(scn, "DazSimulation")

        col = split.column()
        box = col.box()
        box.label(text="Rigging")
        box.prop(scn, "DazUseQuaternions")
        box.prop(scn, "DazConnectClose")
        box.prop(scn, "DazUseLockLoc")
        box.prop(scn, "DazUseLimitLoc")
        box.prop(scn, "DazUseLockRot")
        box.prop(scn, "DazUseLimitRot")
        box.prop(scn, "DazDisplayLimitRot")

        box = col.box()
        box.label(text="Morphs")
        box.prop(scn, "DazUseAdjusters")
        box.prop(scn, "DazMakeHiddenSliders")
        box.prop(scn, "DazSliderLimits")
        box.prop(scn, "DazFinalLimits")
        box.prop(scn, "DazMorphMultiplier")
        box.prop(scn, "DazCustomMin")
        box.prop(scn, "DazCustomMax")
        box.prop(scn, "DazShowFinalProps")
        box.prop(scn, "DazUseERC")
        box.prop(scn, "DazStripCategory")
        box.prop(scn, "DazUseModifiedMesh")

        box = split.box()
        box.label(text="Materials")
        box.prop(scn, "DazMaterialMethod")
        box.prop(scn, "DazSSSMethod")
        box.prop(scn, "DazRefractiveMethod")
        box.prop(scn, "DazHairMaterialMethod")
        box.separator()
        box.prop(scn, "DazViewportColor")
        box.prop(scn, "DazUseWorld")
        box.prop(scn, "DazReuseMaterials")
        box.prop(scn, "DazBumpFactor")
        box.prop(scn, "DazFakeCaustics")
        box.prop(scn, "DazFakeTranslucencyTexture")
        box.prop(scn, "DazImageInterpolation")
        box.prop(scn, "DazHandleRenderSettings")
        box.prop(scn, "DazHandleLightSettings")
        box.separator()
        box.prop(scn, "DazUseDisplacement")
        box.prop(scn, "DazUseEmission")
        box.prop(scn, "DazUseReflection")
        box.prop(scn, "DazUseVolume")

        row = self.layout.row()
        row.operator("daz.load_root_paths")
        row.operator("daz.load_factory_settings")
        row.operator("daz.save_settings_file")
        row.operator("daz.load_settings_file")

    def run(self, context):
        SceneStatic.fromScene(context.scene)
        Settings.save()

    def invoke(self, context, event):
        SceneStatic.toScene(context.scene)
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=1200)

# -------------------------------------------------------------
#   Initialize
# -------------------------------------------------------------


@Registrar.func
def register():

    bpy.types.Scene.DazContentDirs = CollectionProperty(
        type=bpy.types.PropertyGroup,
        name="DAZ Content Directories",
        description="Search paths for DAZ Studio content")

    bpy.types.Scene.DazMDLDirs = CollectionProperty(
        type=bpy.types.PropertyGroup,
        name="DAZ MDL Directories",
        description="Search paths for DAZ Studio MDL")

    bpy.types.Scene.DazCloudDirs = CollectionProperty(
        type=bpy.types.PropertyGroup,
        name="DAZ Cloud Directories",
        description="Search paths for DAZ Studio cloud content")

    bpy.types.Scene.DazErrorPath = StringProperty(
        name="Error Path",
        description="Path to error report file")

    bpy.types.Scene.DazUnitScale = FloatProperty(
        name="Unit Scale",
        description="Scale used to convert between DAZ and Blender units. Default unit meters",
        default=0.01,
        precision=3,
        min=0.001, max=100.0)

    bpy.types.Scene.DazVerbosity = IntProperty(
        name="Verbosity",
        description="Controls the number of warning messages when loading files",
        min=1, max=5)

    bpy.types.Scene.DazUseAdjusters = EnumProperty(
        items=[('NONE', "None", "Don't add adjusters"),
               ('TYPE', "Morph Type", "Add adjusters for morph type"),
               ('STRENGTH', "Morph Strength", "Add adjusters for morph strength"),
               ('BOTH', "Both Type And Strength", "Add adjusters for both morph type and strength")],
        name="Adjust",
        description="Add extra sliders to adjust the overall strength\nof translation channels (shapekeys and locations)")

    bpy.types.Scene.DazCustomMin = FloatProperty(
        name="Custom Min",
        description="Custom minimum for sliders",
        min=-10.0, max=0.0)

    bpy.types.Scene.DazCustomMax = FloatProperty(
        name="Custom Max",
        description="Custom maximum for sliders",
        min=0.0, max=10.0)

    bpy.types.Scene.DazMorphMultiplier = FloatProperty(
        name="Multiplier",
        description="Morph multiplier. Multiply the min and \nmax values for sliders with this factor",
        min=0.0, max=10.0)

    enums = [('DAZ', "DAZ", "Use min and max values from DAZ files if available.\nThe limits are multiplied with the factor below"),
             ('CUSTOM', "Custom", "Use min and max values from custom sliders"),
             ('NONE', "None", "Don't limit sliders")]

    bpy.types.Scene.DazFinalLimits = EnumProperty(
        items=enums,
        name="Final Limits",
        description="Final min and max values for DAZ properties,\nwhen all sliders are taken into account")

    bpy.types.Scene.DazSliderLimits = EnumProperty(
        items=enums,
        name="Slider Limits",
        description="Min and max values for sliders")

    bpy.types.Scene.DazShowFinalProps = BoolProperty(
        name="Show Final Morph Values",
        description="Display the \"final\" values of morphs")

    bpy.types.Scene.DazUseERC = BoolProperty(
        name="ERC Morphs",
        description="Load support for ERC morphs that change the rest pose")

    bpy.types.Scene.DazStripCategory = BoolProperty(
        name="Strip Category",
        description="Strip category from morph names")

    bpy.types.Scene.DazUseModifiedMesh = BoolProperty(
        name="Load To Modified Meshes",
        description="Load morphs to meshes that have been modified by merging geografts or lashes.\nWarning: can give incorrect shapekeys if meshes have been modified in edit mode")

    bpy.types.Scene.DazMakeHiddenSliders = BoolProperty(
        name="Make Hidden Sliders",
        description="Create properties for hidden morphs,\nso they can be displayed in the UI",
        default=False)

    bpy.types.Scene.DazShowHiddenObjects = BoolProperty(
        name="Show Hidden Objects",
        description="Don't hide objects which are hidden in DAZ Studio",
        default=False)

    # Object properties

    bpy.types.Object.DazId = StringProperty(
        name="ID",
        default="")

    bpy.types.Object.DazUrl = StringProperty(
        name="URL",
        default="")

    bpy.types.Object.DazScene = StringProperty(
        name="Scene",
        default="")

    bpy.types.Object.DazRig = StringProperty(
        name="Rig Type",
        default="")

    bpy.types.Object.DazMesh = StringProperty(
        name="Mesh Type",
        default="")

    bpy.types.Object.DazScale = FloatProperty(
        name="Unit Scale",
        default=0.01,
        precision=4)

    bpy.types.Object.DazUnits = StringProperty(default="")
    bpy.types.Object.DazExpressions = StringProperty(default="")
    bpy.types.Object.DazVisemes = StringProperty(default="")
    bpy.types.Object.DazBodies = StringProperty(default="")
    bpy.types.Object.DazFlexions = StringProperty(default="")
    bpy.types.Object.DazCorrectives = StringProperty(default="")

    bpy.types.Object.DazRotMode = StringProperty(default='XYZ')
    bpy.types.PoseBone.DazRotMode = StringProperty(default='XYZ')
    bpy.types.PoseBone.DazAltName = StringProperty(default="")
    bpy.types.Armature.DazUnflipped = BoolProperty(
        name="Unflipped", default=False)
    bpy.types.Object.DazOrient = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Bone.DazOrient = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Object.DazHead = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Object.DazTail = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Object.DazAngle = FloatProperty(default=0)
    bpy.types.Object.DazNormal = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Bone.DazHead = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Bone.DazTail = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.Bone.DazAngle = FloatProperty(default=0)
    bpy.types.Bone.DazNormal = FloatVectorProperty(size=3, default=(0, 0, 0))
    bpy.types.PoseBone.DazHeadLocal = FloatVectorProperty(
        size=3, default=(-1, -1, -1))
    bpy.types.PoseBone.DazTailLocal = FloatVectorProperty(
        size=3, default=(-1, -1, -1))
    bpy.types.PoseBone.HdOffset = FloatVectorProperty(
        size=3, default=(0, 0, 0))

    bpy.types.PoseBone.DazRotLocks = BoolVectorProperty(
        name="Rotation Locks",
        size=3,
        default=(False, False, False)
    )

    bpy.types.PoseBone.DazLocLocks = BoolVectorProperty(
        name="Location Locks",
        size=3,
        default=(False, False, False)
    )

    bpy.types.Armature.DazExtraFaceBones = BoolProperty(default=False)
    bpy.types.Armature.DazExtraDrivenBones = BoolProperty(default=False)

    bpy.types.Scene.DazShowPaths = BoolProperty(
        name="Paths To DAZ Library", default=False)
    bpy.types.Scene.DazShowContentDirs = BoolProperty(
        name="Content Directories", default=True)
    bpy.types.Scene.DazShowMDLDirs = BoolProperty(
        name="MDL Directories", default=False)
    bpy.types.Scene.DazShowCloudDirs = BoolProperty(
        name="Cloud Directories", default=False)

    bpy.types.Scene.DazFilter = StringProperty(
        name="Filter",
        description="Filter string",
        default=""
    )

    bpy.types.Scene.DazMaterialMethod = EnumProperty(
        items=EnumsMaterials,
        name="Method",
        description="Material Method",
        default='BSDF')

    bpy.types.Scene.DazSSSMethod = EnumProperty(
        items=[('BURLEY', "Christensen-Burley", "Chiristensen-Burley"),
               ('RANDOM_WALK', "Random Walk", "Random walk")],
        name="SSS Method",
        description="Method for subsurface scattering",
        default='RANDOM_WALK')

    bpy.types.Scene.DazRefractiveMethod = EnumProperty(
        items=[('BSDF', "BSDF", "Add BSDF refractive node group"),
               ('SECOND', "Second Principled",
                "Add second principled node for refractive part"),
               ('REUSE', "Reuse Principled",
                ("Don't add extra nodes for refractive parts, but reuse the\n" +
                 "principled node for both opaque and refractive components.\n" +
                 "Introduces artifacts sometimes"))],
        name="Refractive Method",
        description="Method for refractive part of principled materials",
        default='BSDF')

    bpy.types.Scene.DazHairMaterialMethod = EnumProperty(
        items=EnumsHair,
        name="Hair",
        description="Method for hair materials",
        default='HAIR_BSDF')

    bpy.types.Scene.DazViewportColor = EnumProperty(
        items=[('ORIGINAL', "Original", "Original diffuse color"),
               ('RANDOM', "Random", "Random colors for each material"),
               ('GUESS', "Guess", "Guess colors based on name"),
               ],
        name="Viewport Color",
        description="Method to display object in viewport")

    bpy.types.Scene.DazUseWorld = EnumProperty(
        items=[('ALWAYS', "Always", "Always create world material"),
               ('DOME', "Dome", "Create world material from dome"),
               ('NEVER', "Never", "Never create world material")],
        name="World",
        description="When to create a world material")

    bpy.types.Scene.DazReuseMaterials = BoolProperty(
        name="Reuse Materials",
        description="Use existing materials if such exists.\nMay lead to incorrect materials")

    bpy.types.Scene.DazConnectClose = BoolProperty(
        name="Connect Close",
        description="Connect bones to their parent if the head is close to the parent's tail")

    bpy.types.Scene.DazUseLockLoc = BoolProperty(
        name="Location Locks",
        description="Use location locks")

    bpy.types.Scene.DazUseLimitLoc = BoolProperty(
        name="Location Limits",
        description="Use location limits")

    bpy.types.Scene.DazUseLockRot = BoolProperty(
        name="Rotation Locks",
        description="Use rotation locks")

    bpy.types.Scene.DazUseLimitRot = BoolProperty(
        name="Rotation Limits",
        description="Use rotation limits")

    bpy.types.Scene.DazDisplayLimitRot = BoolProperty(
        name="Display Rotation Limits",
        description="Display rotation limits as IK limits")

    bpy.types.Object.DazHasLocLocks = BoolProperty(default=False)
    bpy.types.Object.DazHasRotLocks = BoolProperty(default=False)
    bpy.types.Object.DazHasLocLimits = BoolProperty(default=False)
    bpy.types.Object.DazHasRotLimits = BoolProperty(default=False)

    bpy.types.Scene.DazDump = BoolProperty(
        name="Dump Debug Info",
        description="Dump debug info in the file\ndaz_importer_errors.text after loading file")

    bpy.types.Scene.DazZup = BoolProperty(
        name="Z Up",
        description="Convert from DAZ's Y up convention to Blender's Z up convention.\nDisable for debugging only")

    bpy.types.Scene.DazUnflipped = BoolProperty(
        name="Unflipped Bones",
        description="Don't flip bone axes.\nEnable for debugging only")

    bpy.types.Scene.DazUseQuaternions = BoolProperty(
        name="Quaternions",
        description="Use quaternions for ball-and-socket joints (shoulders and hips)")

    bpy.types.Scene.DazCaseSensitivePaths = BoolProperty(
        name="Case-Sensitive Paths",
        description="Convert URLs to lowercase. Works best on Windows.")

    bpy.types.Scene.DazUseInstancing = BoolProperty(
        name="Use Instancing",
        description="Use instancing for DAZ instances")

    bpy.types.Scene.DazHighdef = BoolProperty(
        name="Build HD Meshes",
        description="Build HD meshes if included in .dbz file")

    bpy.types.Scene.DazMultires = BoolProperty(
        name="Add Multires",
        description="Add multires modifier to HD meshes and rebuild lower subdivision levels")

    bpy.types.Scene.DazMultiUvLayers = BoolProperty(
        name="Multiple UV Layers",
        description="Use multiple UV layers for HD meshes with multires modifiers")

    bpy.types.Scene.DazUseAutoSmooth = BoolProperty(
        name="Auto Smooth",
        description=(
            "Use auto smooth if this is done in DAZ Studio.\n" +
            "This can be useful for objects with hard edges,\n" +
            "but leads to poor performance and artifacts for organic meshes"))

    bpy.types.Scene.DazSimulation = BoolProperty(
        name="Simulation",
        description="Add influence (pinning) vertex groups for simulation")

    bpy.types.Scene.DazMergeShells = BoolProperty(
        name="Merge Shell Materials",
        description="Merge shell materials with object materials.\nDisable for debugging only")

    bpy.types.Scene.DazPruneNodes = BoolProperty(
        name="Prune Node Tree",
        description="Prune material node-tree.\nDisable for debugging only")

    bpy.types.Scene.DazBumpFactor = FloatProperty(
        name="Bump Factor",
        description="Multiplier for bump strength",
        min=0.1, max=10)

    bpy.types.Scene.DazFakeCaustics = BoolProperty(
        name="Fake Caustics",
        description="Use fake caustics")

    bpy.types.Scene.DazFakeTranslucencyTexture = BoolProperty(
        name="Fake Translucency Textures",
        description="If there is no translucency texture, use diffuse texture instead.\nSometimes useful to avoid \"white skin\" effect")

    bpy.types.Scene.DazUseDisplacement = BoolProperty(
        name="Displacement",
        description="Use displacement maps")

    bpy.types.Scene.DazUseEmission = BoolProperty(
        name="Emission",
        description="Use emission.")

    bpy.types.Scene.DazUseReflection = BoolProperty(
        name="Reflection",
        description="Use reflection maps")

    bpy.types.Scene.DazUseVolume = BoolProperty(
        name="Volume",
        description="Use volume node in BSDF tree")

    bpy.types.Scene.DazImageInterpolation = EnumProperty(
        items=[('Linear', "Linear", "Linear"),
               ('Closest', "Closest", "Closest"),
               ('Cubic', "Cubic", "Cubic"),
               ('Smart', "Smart", "Smart")],
        name="Interpolation",
        description="Image interpolation")

    bpy.types.Material.DazRenderEngine = StringProperty(default='NONE')
    bpy.types.Material.DazShader = StringProperty(default='NONE')

    bpy.types.Object.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDimsCollapsed = BoolProperty(default=False)
    bpy.types.Material.DazUDim = IntProperty(default=0)
    bpy.types.Material.DazVDim = IntProperty(default=0)
