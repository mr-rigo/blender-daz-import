import os
import bpy
from collections import OrderedDict

from bpy_extras.io_utils import ImportHelper
from mathutils import Vector
from daz_import.driver import DriverUser

from daz_import.Lib import Json, Registrar
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Files import SingleFile, MultiFile, DazImageFile, DatFile, JsonFile
from daz_import.Elements.Animation import ActionOptions
from daz_import.Elements.Groups import DazTextGroup, DazFloatGroup, DazStringGroup, DazMorphInfoGroup
from daz_import.Elements.Import.MorphTypeOptions import MorphTypeOptions 

from daz_import.Collection import Collection, DazPath
from daz_import.Lib.Errors import DazOperator, IsMeshArmature,\
    IsMesh, DazPropsOperator, IsArmature, DazError

from bpy.props import StringProperty, EnumProperty, IntProperty,\
    BoolProperty, CollectionProperty, FloatProperty

from .static import *
from .data import *

from .LoadMorph import LoadMorph
from daz_import.Lib.Utility import PropsStatic


def keyProp(rig, key, frame):
    rig.keyframe_insert(PropsStatic.ref(key), frame=frame)


def keyShape(skeys, key, frame):
    skeys.keyframe_insert('key_blocks["%s"].value' % key, frame=frame)


def unkeyProp(rig, key, frame):
    try:
        rig.keyframe_delete(PropsStatic.ref(key), frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def unkeyShape(skeys, key, frame):
    try:
        skeys.keyframe_delete('key_blocks["%s"].value' % key, frame=frame)
    except RuntimeError:
        print("No action to unkey %s" % key)


def getPropFCurves(rig, key):
    if rig.animation_data and rig.animation_data.action:
        path = PropsStatic.ref(key)
        return [fcu for fcu in rig.animation_data.action.fcurves if path == fcu.data_path]
    return []


def autoKeyProp(rig, key, scn, frame, force):
    if scn.tool_settings.use_keyframe_insert_auto:
        if force or getPropFCurves(rig, key):
            keyProp(rig, key, frame)


def autoKeyShape(skeys, key, scn, frame):
    if scn.tool_settings.use_keyframe_insert_auto:
        keyShape(skeys, key, frame)


def pinProp(rig, scn, key, morphset, category, frame, value=1.0):
    if rig:
        setMorphs(0.0, rig, morphset, category, scn, frame, True)
        rig[key] = value
        autoKeyProp(rig, key, scn, frame, True)


def pinShape(ob, scn, key, category, frame):
    skeys = ob.data.shape_keys
    if skeys:
        clearShapes(ob, category, scn, frame)
        skeys.key_blocks[key].value = 1.0
        autoKeyShape(skeys, key, scn, frame)


# -------------------------------------------------------------
#   Classes
# -------------------------------------------------------------


class MorphsetString:
    morphset: StringProperty(default="")
    category: StringProperty(default="")
    prefix: StringProperty(default="")


class CategoryString:
    category: StringProperty(
        name="Category",
        description="Add morphs to this category of custom morphs",
        default="Shapes"
    )


def getActiveCategories(scn, context):
    ob = context.object
    cats = [(cat.name, cat.name, cat.name) for cat in ob.DazMorphCats]
    cats.sort()
    return [("All", "All", "All")] + cats


class CustomEnums:
    custom: EnumProperty(
        items=getActiveCategories,
        name="Category")


@Registrar()
class DazSelectGroup(bpy.types.PropertyGroup):
    text: StringProperty()
    category: StringProperty()
    index: IntProperty()
    select: BoolProperty()

    def __lt__(self, other):
        return (self.text < other.text)


@Registrar()
class DazCategory(bpy.types.PropertyGroup):
    custom: StringProperty()
    morphs: CollectionProperty(type=DazTextGroup)

    if bpy.app.version < (2, 90, 0):
        active: BoolProperty(default=False)
    else:
        active: BoolProperty(default=False, override={'LIBRARY_OVERRIDABLE'})


@Registrar()
class DazActiveGroup(bpy.types.PropertyGroup):
    if bpy.app.version < (2, 90, 0):
        active: BoolProperty(default=True)
    else:
        active: BoolProperty(default=True, override={'LIBRARY_OVERRIDABLE'})


# -------------------------------------------------------------
#   Morph selector
# -------------------------------------------------------------


class MorphSelector:
    selector = None

    @classmethod
    def get(cls):
        return cls.selector

    @classmethod
    def set(cls, selector):
        cls.selector = selector


@Registrar()
class DAZ_OT_SelectAll(bpy.types.Operator):
    bl_idname = "daz.select_all"
    bl_label = "All"
    bl_description = "Select all"

    def execute(self, context):
        MorphSelector.get().selectAll(context)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_SelectNone(bpy.types.Operator):
    bl_idname = "daz.select_none"
    bl_label = "None"
    bl_description = "Select none"

    def execute(self, context):
        MorphSelector.get().selectNone(context)
        return {'PASS_THROUGH'}


class Selector():
    selection: CollectionProperty(type=DazSelectGroup)

    filter: StringProperty(
        name="Filter",
        description="Show only items containing this string",
        default=""
    )

    defaultSelect = False
    columnWidth = 180
    ncols = 6
    nrows = 20
    mincols = 3

    def draw(self, context):
        scn = context.scene
        self.drawSelectionRow()
        self.layout.prop(self, "filter", icon='VIEWZOOM', text="")
        self.drawExtra(context)
        self.layout.separator()
        items = [item for item in self.selection if self.isSelected(item)]
        items.sort()
        nitems = len(items)
        ncols = self.ncols
        nrows = self.nrows
        if nitems > ncols*nrows:
            nrows = nitems//ncols + 1
        else:
            ncols = nitems//nrows + 1
            if ncols < self.mincols:
                ncols = self.mincols
                nrows = (nitems-1)//ncols + 1
        cols = []
        for n in range(ncols):
            cols.append(items[0:nrows])
            items = items[nrows:]
        for m in range(nrows):
            row = self.layout.row()
            for col in cols:
                if m < len(col):
                    item = col[m]
                    row.prop(item, "select", text="")
                    row.label(text=item.text)
                else:
                    row.label(text="")

    def drawSelectionRow(self):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_none")

    def drawExtra(self, context):
        pass

    def selectAll(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = True

    def selectNone(self, context):
        for item in self.selection:
            if self.isSelected(item):
                item.select = False

    def isSelected(self, item):
        return (self.selectCondition(item) and self.filtered(item))

    def selectCondition(self, item):
        return True

    def filtered(self, item):
        return (not self.filter or self.filter.lower() in item.text.lower())

    def getSelectedItems(self):
        return [item for item in self.selection if item.select and self.isSelected(item)]

    def getSelectedProps(self):
        if Collection.import_paths:
            return Collection.import_paths
        else:
            return [item.name for item in self.getSelectedItems()]

    def invokeDialog(self, context):
        MorphSelector.set(self)
        Collection.clear_import()
        wm = context.window_manager
        ncols = len(self.selection)//self.nrows + 1
        if ncols > self.ncols:
            ncols = self.ncols
        elif ncols < self.mincols:
            ncols = self.mincols
        wm.invoke_props_dialog(self, width=ncols*self.columnWidth)
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        scn = context.scene
        ob = context.object
        rig = self.rig = getRigFromObject(ob)
        self.selection.clear()
        for idx, data in enumerate(self.getKeys(rig, ob)):
            prop, text, cat = data
            item = self.selection.add()
            item.name = prop
            item.text = text
            item.category = cat
            item.index = idx
            item.select = self.defaultSelect
        return self.invokeDialog(context)


class Enums:
    morph = []
    cat = []

    @classmethod
    def getMorphEnums(cls, scn, context):
        return cls.morph

    @classmethod
    def getCatEnums(cls, scn, context):
        return cls.cat


class GeneralMorphSelector(Selector):
    morphset: EnumProperty(
        items=Enums.morph,
        name="Type")

    category: EnumProperty(
        items=Enums.cat,
        name="Category")

    def selectCondition(self, item):
        if self.morphset == "Custom":
            return (item.name in self.catnames[self.category])
        else:
            return (item.name in self.morphnames[self.morphset])

    def draw(self, context):
        self.layout.prop(self, "morphset")
        self.layout.prop(self, "category")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        morphs = getMorphList(rig, self.morphset, sets=theStandardMorphSets)
        keys = [(item.name, item.text, "All") for item in morphs]
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name, item.text, cat.name))
        return keys

    def invoke(self, context, event):
        ob = context.object
        rig = self.rig = getRigFromObject(ob)
        Enums.morph = [("All", "All", "All")]
        Enums.cat = [("All", "All", "All")]
        self.morphset = "All"
        self.morphnames = {}
        self.morphnames["All"] = []
        for morphset in theStandardMorphSets:
            Enums.morph.append((morphset, morphset, morphset))
            pg = getattr(self.rig, "Daz"+morphset)
            self.morphnames["All"] += list(pg.keys())
            self.morphnames[morphset] = pg.keys()
        Enums.morph.append(("Custom", "Custom", "Custom"))
        self.catnames = {}
        self.catnames["All"] = []
        for cat in rig.DazMorphCats:
            Enums.cat.append((cat.name, cat.name, cat.name))
            self.morphnames["All"] += list(cat.morphs.keys())
            self.catnames["All"] += list(cat.morphs.keys())
            self.catnames[cat.name] = cat.morphs.keys()
        return Selector.invoke(self, context, event)


class CustomSelector(Selector, CustomEnums):

    def selectCondition(self, item):
        return (self.custom == "All" or item.category == self.custom)

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def getKeys(self, rig, ob):
        keys = []
        for cat in rig.DazMorphCats:
            for item in cat.morphs:
                keys.append((item.name, item.text, cat.name))
        return keys


class JCMSelector(Selector):
    bodypart: EnumProperty(
        items=[("All", "All", "All. Easy import transfers these shapekeys to all meshes"),
               ("Face", "Face", "Face. Easy import transfers these shapekeys to lashes"),
               ("Body", "Body", "Body. Easy import transfers these shapekeys to clothes and geografts"),
               ("Custom", "Custom", "Custom. Easy import does not transfer these shapekeys")],
        name="Body part",
        description="Part of character that the morphs affect",
        default="All")

    def selectCondition(self, item):
        return (self.bodypart == "All" or item.category == self.bodypart)

    def drawSelectionRow(self):
        row = self.layout.row()
        row.prop(self, "bodypart")
        row.operator("daz.select_all")
        row.operator("daz.select_none")

    def getKeys(self, rig, ob):
        keys = []
        skeys = ob.data.shape_keys
        for skey in skeys.key_blocks[1:]:
            keys.append((skey.name, skey.name, self.bodyparts[skey.name]))
        return keys

    def invoke(self, context, event):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            print("Object %s has no shapekeys")
            return {'FINISHED'}
        self.bodyparts = classifyShapekeys(ob, skeys)
        return Selector.invoke(self, context, event)


# ------------------------------------------------------------------
#   Settings lists of morph paths
# ------------------------------------------------------------------
ShortForms = {
    "phmunits": ["phmbrow", "phmcheek", "phmeye", "phmjaw", "phmlip", "phmmouth", "phmnos", "phmteeth", "phmtongue"],

    "ectrlunits": ["ectrlbrow", "ectrlcheek", "ectrleye", "ectrljaw", "ectrllip", "ectrlmouth", "ectrlnos", "ectrlteeth", "ectrltongue"],
}

ShortForms["units"] = ShortForms["ectrlunits"] + ShortForms["phmunits"]


def getShortformList(item):
    if isinstance(item, list):
        return item
    else:
        return ShortForms[item]


class MorphStatic:
    files = {}
    names = {}


def getAllMorphFiles(char, morphset):
    return list(MorphStatic.files[char][morphset].values())


def getMorphPaths(char):
    setupMorphPaths(False)
    morphpaths = {}
    if char in MorphStatic.files.keys():
        for morphset, pgs in MorphStatic.files[char].items():
            morphpaths[morphset] = pgs.values()
    return morphpaths


def setupMorphPaths(force):
    from daz_import.Elements.Modifier import getCanonicalKey

    if MorphStatic.files and not force:
        return
    MorphStatic.files = {}
    MorphStatic.names = {}

    folder = os.path.join(Settings.root_, "data/paths/")
    charPaths = {}
    files = list(os.listdir(folder))
    files.sort()

    for file in files:
        path = os.path.join(folder, file)
        struct = Json.load(path)
        charPaths[struct["name"]] = struct

    for char in charPaths.keys():
        charFiles = MorphStatic.files[char] = {}

        for key, struct in charPaths[char].items():
            if key in ["name", "hd-morphs"]:
                continue
            type = key.capitalize()
            if type not in charFiles.keys():
                charFiles[type] = OrderedDict()
            typeFiles = charFiles[type]
            if type not in MorphStatic.names.keys():
                MorphStatic.names[type] = OrderedDict()
            typeNames = MorphStatic.names[type]

            if isinstance(struct["prefix"], list):
                prefixes = struct["prefix"]
            else:
                prefixes = [struct["prefix"]]

            if "strip" in struct.keys():
                strips = struct["strip"]
            else:
                strips = prefixes

            folder = struct["path"]
            includes = getShortformList(struct["include"])
            excludes = getShortformList(struct["exclude"])
            if "exclude2" in struct.keys():
                excludes += getShortformList(struct["exclude2"])

            for dazpath in Collection.get_paths():
                folderpath = "%s/%s" % (dazpath, folder)

                if not os.path.exists(folderpath) and Settings.caseSensitivePaths:
                    folderpath = Collection.fix_path(folderpath)

                if os.path.exists(folderpath):
                    files = list(os.listdir(folderpath))
                    files.sort()
                    for file in files:
                        fname, ext = os.path.splitext(file)
                        if ext not in [".duf", ".dsf"]:
                            continue
                        isright, name = isRightType(
                            fname, prefixes, strips, includes, excludes)
                        if isright:
                            fname = fname.lower()
                            #fpath = os.path.join(folder, file)
                            string = "%s/%s" % (folderpath, file)
                            typeFiles[name] = string.replace("//", "/")
                            #prop = BoolProperty(name=name, default=True)
                            #setattr(bpy.types.Scene, "Daz"+name, prop)
                            typeNames[fname] = name


def isRightType(fname, prefixes, strips, includes, excludes):
    string = fname.lower()
    ok = False
    for prefix in prefixes:
        n = len(prefix)
        if string[0:n] == prefix:
            ok = True
            if prefix in strips:
                name = fname[n:]
            else:
                name = fname
            break
    if not ok:
        return False, fname

    if includes == []:
        for exclude in excludes:
            if exclude in string:
                return False, name
        return True, name

    for include in includes:
        if (include in string or
                string[0:len(include)-1] == include[1:]):
            for exclude in excludes:
                if (exclude in string or
                        string[0:len(exclude)-1] == exclude[1:]):
                    return False, name
            return True, name
    return False, name


@Registrar()
class DAZ_OT_Update(DazOperator):
    bl_idname = "daz.update_morph_paths"
    bl_label = "Update Morph Paths"
    bl_description = "Update paths to predefined morphs"
    bl_options = {'UNDO'}

    def run(self, context):
        setupMorphPaths(True)
        print(MorphStatic.files.items())
        print("UU", MorphStatic.names.items())


@Registrar()
class DAZ_OT_SelectAllMorphs(DazOperator):
    bl_idname = "daz.select_all_morphs"
    bl_label = "Select All"
    bl_description = "Select/Deselect all morphs in this section"
    bl_options = {'UNDO'}

    type: StringProperty()
    value: BoolProperty()

    def run(self, context):
        scn = context.scene
        names = MorphStatic.names[self.morphset]
        for name in names.values():
            scn["Daz"+name] = self.value

# ------------------------------------------------------------------
#   Load typed morphs base class
# ------------------------------------------------------------------


class MorphLoader(LoadMorph):
    loadMissing = True
    category = ""
    adjuster = None

    def __init__(self, rig=None, mesh=None):
        from daz_import.Elements.Finger import getFingeredCharacter
        self.rig, self.mesh, self.char, self.modded = getFingeredCharacter(
            bpy.context.object, Settings.useModifiedMesh)
        if mesh:
            self.mesh = mesh

    def getMorphSet(self, asset):
        return self.morphset

    def getAdjustProp(self):
        return self.adjuster

    def findPropGroup(self, prop):
        return None

    def addUrl(self, asset, aliases, filepath, bodypart):
        if self.mesh:
            pgs = self.mesh.DazMorphUrls
        elif self.rig:
            pgs = self.rig.DazMorphUrls
        else:
            return
        if filepath not in pgs.keys():
            item = pgs.add()
            item.name = filepath
            item.morphset = self.getMorphSet(asset)
            if asset.name in aliases.keys():
                item.text = aliases[asset.name]
            else:
                item.text = asset.name
            item.category = self.category
            item.bodypart = bodypart

    def getAllMorphs(self, namepaths, context):
        from time import perf_counter
        from daz_import.driver import setBoolProp

        if self.mesh:
            ob = self.mesh
        elif self.rig:
            ob = self.rig
        else:
            raise DazError("Neither mesh nor rig selected")
        Settings.forMorphLoad(ob)
        if not self.usePropDrivers:
            self.rig = None

        self.errors = {}
        t1 = perf_counter()

        if namepaths:
            path = namepaths[0][0]
            folder = os.path.dirname(path)
        else:
            raise DazError("No morphs selected")

        self.loadAllMorphs(namepaths)
        t2 = perf_counter()

        print("Folder %s loaded in %.3f seconds" % (folder, t2-t1))
        
        if self.errors:
            msg = "Morphs loaded with errors."

            for err, props in self.errors.items():
                msg += "\n%s:    \n" % err
                for prop in props:
                    msg += "    %s\n" % prop

        elif self.erc and Settings.verbosity >= 3:
            msg = "Found morphs that want to\nchange the rest pose"
        else:
            msg = None

    def addToMorphSet(self, prop, asset, hidden):
        from daz_import.Elements.Modifier import getCanonicalKey
        pgs = self.findPropGroup(prop)

        if pgs is None:
            return

        if prop in pgs.keys():
            item = pgs[prop]
        else:
            item = pgs.add()
            item.name = prop

        if asset and asset.name == prop:
            label = asset.label
            visible = asset.visible
        else:
            label = getCanonicalKey(prop)
            visible = True

        n = len(self.category)

        if Settings.useStripCategory and self.category and label[0:n] == self.category:
            label = label[n:]

        if self.hideable and (hidden or not visible):
            item.text = "[%s]" % label
        else:
            item.text = label

        return prop

    def findIked(self):
        self.iked = []

        if self.rig and self.rig.data.DazSimpleIK:
            for pb in self.rig.pose.bones:
                cns = BlenderStatic.constraint(pb, 'IK')
                if cns:
                    par = pb
                    for n in range(cns.chain_count):
                        if par is None:
                            break
                        self.iked.append(par)
                        par = par.parent

# ------------------------------------------------------------------
#   Load standard morphs
# ------------------------------------------------------------------


class StandardMorphLoader(MorphLoader):
    suppressError = True
    ignoreHD = False
    hideable = True

    def setupCharacter(self, context):
        ob = context.object
        if not self.char:
            from daz_import.Lib.Errors import ErrorsStatic

            msg = ("Can not add morphs to this mesh:\n %s" % ob.name)
            ErrorsStatic.invoke(msg)

            return False
        return True

    def findPropGroup(self, prop):
        return getattr(self.rig, "Daz"+self.morphset)

    def getMorphFiles(self):
        try:
            return MorphStatic.files[self.char][self.morphset]
        except KeyError:
            return []

    def getPaths(self, context):
        return

    def run(self, context):
        self.adjuster = theAdjusters[self.morphset]
        setupMorphPaths(False)
        if self.rig:
            self.rig.DazMorphPrefixes = False
            self.findIked()
        namepaths = self.getActiveMorphFiles(context)
        msg = self.getAllMorphs(namepaths, context)
        if msg:
            raise DazError(msg, warning=True)

# ------------------------------------------------------------------------
#   Import general morph or driven pose
# ------------------------------------------------------------------------


class StandardMorphSelector(Selector):
    def draw(self, context):
        Selector.draw(self, context)

    def getActiveMorphFiles(self, context):
        namepaths = []

        if Collection.import_paths:
            for path in Collection.import_paths:
                text = os.path.splitext(os.path.basename(path))[0]
                namepaths.append((text, path, self.bodypart))
        else:
            for item in self.getSelectedItems():
                namepaths.append((item.text, item.name, self.bodypart))
        return namepaths

    def isActive(self, name, scn):
        return True

    def selectCondition(self, item):
        return True

    def invoke(self, context, event):
        scn = context.scene
        self.selection.clear()
        if not self.setupCharacter(context):
            return {'FINISHED'}
        setupMorphPaths(False)
        try:
            pgs = MorphStatic.files[self.char][self.morphset]
        except KeyError:
            msg = ("Character %s does not support feature %s" %
                   (self.char, self.morphset))
            print(msg)
            return {'FINISHED'}
        for key, path in pgs.items():
            item = self.selection.add()
            item.name = path
            item.text = key
            item.category = self.morphset
            item.select = True
        return self.invokeDialog(context)


@Registrar()
class DAZ_OT_ImportUnits(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_units"
    bl_label = "Import Units"
    bl_description = "Import selected face unit morphs"
    bl_options = {'UNDO'}

    morphset = "Units"
    bodypart = "Face"


@Registrar()
class DAZ_OT_ImportExpressions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_expressions"
    bl_label = "Import Expressions"
    bl_description = "Import selected expression morphs"
    bl_options = {'UNDO'}

    morphset = "Expressions"
    bodypart = "Face"


@Registrar()
class DAZ_OT_ImportVisemes(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_visemes"
    bl_label = "Import Visemes"
    bl_description = "Import selected viseme morphs"
    bl_options = {'UNDO'}

    morphset = "Visemes"
    bodypart = "Face"


@Registrar()
class DAZ_OT_ImportFacs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs"
    bl_label = "Import FACS Units"
    bl_description = "Import selected FACS unit morphs"
    bl_options = {'UNDO'}

    morphset = "Facs"
    bodypart = "Face"


@Registrar()
class DAZ_OT_ImportFacsExpressions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_facs_expressions"
    bl_label = "Import FACS Expressions"
    bl_description = "Import selected FACS expression morphs"
    bl_options = {'UNDO'}

    morphset = "Facsexpr"
    bodypart = "Face"
    loadMissing = False


@Registrar()
class DAZ_OT_SelectMhxCompatible(bpy.types.Operator):
    bl_idname = "daz.select_mhx_compatible"
    bl_label = "MHX Compatible"
    bl_description = "Select MHX compatible body morphs"

    def execute(self, context):
        MorphSelector.get().selectMhxCompatible(context)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_ImportBodyMorphs(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMeshArmature):
    bl_idname = "daz.import_body_morphs"
    bl_label = "Import Body Morphs"
    bl_description = "Import selected body morphs"
    bl_options = {'UNDO'}

    morphset = "Body"
    bodypart = "Body"

    def drawSelectionRow(self):
        row = self.layout.row()
        row.operator("daz.select_all")
        row.operator("daz.select_mhx_compatible")
        row.operator("daz.select_none")

    def selectMhxCompatible(self, context):
        safe, unsafe = getMhxSafe(self.rig)
        for item in self.selection:
            item.select = False
            for string in safe:
                if string in item.text:
                    item.select = True
            for string in unsafe:
                if string in item.text:
                    item.select = False

    def run(self, context):
        StandardMorphLoader.run(self, context)


def getMhxSafe(rig):
    safe = ["Breast", "Finger", "Thumb", "Index", "Mid", "Ring", "Pinky"]
    if rig:
        if "lBigToe" in rig.data.bones.keys():
            safe.append("Toe")
            unsafe = ["Foot"]
        else:
            unsafe = ["Toe"]
    else:
        safe = unsafe = []
    return safe, unsafe


@Registrar()
class DAZ_OT_ImportJCMs(DazOperator, StandardMorphSelector, StandardMorphLoader):
    bl_idname = "daz.import_jcms"
    bl_label = "Import JCMs"
    bl_description = "Import selected joint corrective morphs"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    morphset = "Jcms"
    bodypart = "Body"
    hideable = False


@Registrar()
class DAZ_OT_ImportFlexions(DazOperator, StandardMorphSelector, StandardMorphLoader, IsMesh):
    bl_idname = "daz.import_flexions"
    bl_label = "Import Flexions"
    bl_description = "Import selected flexion morphs"
    bl_options = {'UNDO'}

    morphset = "Flexions"
    bodypart = "Body"
    hideable = False

# ------------------------------------------------------------------------
#   Import all standard morphs in one bunch, for performance
# ------------------------------------------------------------------------


@Registrar()
class DAZ_OT_ImportStandardMorphs(DazPropsOperator, StandardMorphLoader, MorphTypeOptions, IsMeshArmature):
    bl_idname = "daz.import_standard_morphs"
    bl_label = "Import Standard Morphs"
    bl_description = "Import all standard morphs of selected types.\nDoing this once is faster than loading individual types"
    bl_options = {'UNDO'}

    morphset = "Standard"

    def run(self, context):
        if not self.setupCharacter(context):
            return
        setupMorphPaths(False)
        if self.rig:
            self.rig.DazMorphPrefixes = False
        self.message = None
        self.loadMorphType(context, self.units, "Units", "Face")
        self.loadMorphType(context, False, "Head", "Face")
        self.loadMorphType(context, self.expressions, "Expressions", "Face")
        self.loadMorphType(context, self.visemes, "Visemes", "Face")
        self.loadMorphType(context, self.facs, "Facs", "Face")
        self.loadMorphType(context, self.facsexpr, "Facsexpr", "Face")
        self.loadMorphType(context, self.body, "Body", "Body")
        self.loadMorphType(context, self.jcms, "Jcms", "Body")
        self.loadMorphType(context, self.flexions, "Flexions", "Body")
        if self.message:
            raise DazError(self.message, warning=True)

    def loadMorphType(self, context, use, morphset, bodypart):
        if not use:
            return
        try:
            struct = MorphStatic.files[self.char][morphset]
        except KeyError:
            msg = ("Character %s does not support feature %s" %
                   (self.char, morphset))
            print(msg)
            return
        print("Load %s" % morphset)
        if morphset == "Body" and self.useMhxOnly:
            struct = self.selectMhxMorphs(struct)
        self.morphset = morphset
        self.adjuster = theAdjusters[morphset]
        self.namepaths = []
        for key, filepath in struct.items():
            fileref = self.getFileRef(filepath)
            self.namepaths.append((key, filepath, bodypart))
        msg = self.getAllMorphs(self.namepaths, context)
        if msg:
            self.message = msg

    def selectMhxMorphs(self, struct):
        safe, unsafe = getMhxSafe(self.rig)
        nstruct = {}
        for key, path in struct.items():
            for string in unsafe:
                if string in key:
                    continue
            for string in safe:
                if string in key:
                    nstruct[key] = path
        return nstruct

    def addToMorphSet(self, prop, asset, hidden):
        self.hideable = (self.morphset in ["Jcms", "Flexions"])
        StandardMorphLoader.addToMorphSet(self, prop, asset, hidden)

# ------------------------------------------------------------------------
#   Import general morph or driven pose
# ------------------------------------------------------------------------


class CustomMorphLoader(MorphLoader):
    morphset = "Custom"
    hideable = True
    category = ""

    def findPropGroup(self, prop):
        if self.rig is None:
            return None
        if self.morphset != "Custom":
            return getattr(self.rig, "Daz"+self.morphset)
        cats = self.rig.DazMorphCats
        if self.category not in cats.keys():
            cat = cats.add()
            cat.name = self.category
        else:
            cat = cats[self.category]
        return cat.morphs


@Registrar()
class DAZ_OT_ImportCustomMorphs(DazOperator, CustomMorphLoader, DazImageFile, MultiFile, IsMeshArmature):
    bl_idname = "daz.import_custom_morphs"
    bl_label = "Import Custom Morphs"
    bl_description = "Import selected morphs from native DAZ files (*.duf, *.dsf)"
    bl_options = {'UNDO'}

    category: StringProperty(
        name="Category",
        default="Shapes")

    usePropDrivers: BoolProperty(
        name="Use Rig Property Drivers",
        description="Drive shapekeys with rig properties",
        default=True)

    useMeshCats: BoolProperty(
        name="Use Mesh Categories",
        description="Mesh categories",
        default=False)

    bodypart: EnumProperty(
        items=[("Face", "Face", "Face"),
               ("Body", "Body", "Body"),
               ("Custom", "Custom", "Custom")],
        name="Body part",
        description="Part of character that the morphs affect",
        default="Custom")

    treatHD: EnumProperty(
        items=[('ERROR', "Error", "Raise error"),
               ('CREATE', "Create Shapekey", "Create empty shapekeys"),
               ('ACTIVE', "Active Shapekey", "Drive active shapekey")],
        name="Treat HD Mismatch",
        description="How to deal with vertex count mismatch for HD morphs",
        default='ERROR'
    )

    def draw(self, context):
        self.layout.prop(self, "usePropDrivers")
        if self.usePropDrivers:
            self.layout.prop(self, "category")
        else:
            self.layout.prop(self, "useMeshCats")
            if self.useMeshCats:
                self.layout.prop(self, "category")
        self.layout.prop(self, "bodypart")
        self.layout.prop(self, "treatHD")

    def invoke(self, context, event):
        from daz_import.Lib.Files import getFolders
        folders = getFolders(self.mesh, ["Morphs/", ""])
        if not folders:
            folders = getFolders(self.rig, ["Morphs/", ""])
        if folders:
            self.properties.filepath = folders[0]
        return MultiFile.invoke(self, context, event)

    def run(self, context):
        from daz_import.driver import setBoolProp
        self.findIked()
        namepaths = self.getNamePaths()
        msg = self.getAllMorphs(namepaths, context)
        if self.usePropDrivers and self.rig:
            self.rig.DazCustomMorphs = True
        elif self.useMeshCats and self.shapekeys:
            props = self.shapekeys.keys()
            addToCategories(self.mesh, props, self.category)
            self.mesh.DazMeshMorphs = True
        if msg:
            raise DazError(msg, warning=True)

    def getNamePaths(self):
        namepaths = []
        folder = ""
        for path in self.getMultiFiles(["duf", "dsf"]):
            name = os.path.splitext(os.path.basename(path))[0]
            namepaths.append((name, path, self.bodypart))
        return namepaths

    def getAdjustProp(self):
        self.rig.DazCustomMorphs = True
        if self.category not in self.rig.DazMorphCats.keys():
            cat = self.rig.DazMorphCats.add()
            cat.name = self.category
        return "Adjust Custom/%s" % self.category

# ------------------------------------------------------------------------
#   Categories
# ------------------------------------------------------------------------


def addToCategories(ob, props, category):
    from daz_import.driver import setBoolProp
    from daz_import.Elements.Modifier import getCanonicalKey

    if props and ob is not None:
        cats = dict([(cat.name, cat) for cat in ob.DazMorphCats])
        if category not in cats.keys():
            cat = ob.DazMorphCats.add()
            cat.name = category
        else:
            cat = cats[category]
        setBoolProp(cat, "active", True)
        for prop in props:
            if prop not in cat.morphs.keys():
                morph = cat.morphs.add()
            else:
                morph = cat.morphs[prop]
            morph.name = prop
            morph.text = getCanonicalKey(prop)
            setBoolProp(morph, "active", True)

# ------------------------------------------------------------------------
#   Rename category
# ------------------------------------------------------------------------


@Registrar()
class DAZ_OT_RenameCategory(DazPropsOperator, CustomEnums, CategoryString, IsMeshArmature):
    bl_idname = "daz.rename_category"
    bl_label = "Rename Category"
    bl_description = "Rename selected category"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "custom")
        self.layout.prop(self, "category", text="New Name")

    def run(self, context):
        rig = context.object
        if self.custom == "All":
            raise DazError("Cannot rename all categories")
        cat = rig.DazMorphCats[self.custom]
        cat.name = self.category


def removeFromPropGroup(pgs, prop):
    idxs = []
    for n, item in enumerate(pgs):
        if item.name == prop:
            idxs.append(n)
    idxs.reverse()
    for n in idxs:
        pgs.remove(n)

# ------------------------------------------------------------------------
#   Remove category
# ------------------------------------------------------------------------


@Registrar()
class DAZ_OT_RemoveCategories(DazOperator, Selector, IsArmature):
    bl_idname = "daz.remove_categories"
    bl_label = "Remove Categories"
    bl_description = "Remove selected categories and associated drivers"
    bl_options = {'UNDO'}

    useDeleteShapekeys: BoolProperty(
        name="Delete Shapekeys",
        description="Delete both drivers and shapekeys",
        default=True)

    useDeleteProps: BoolProperty(
        name="Delete Properties",
        description="Delete object and armature properties associated with this morph",
        default=True)

    useDeleteDrivers: BoolProperty(
        name="Delete Drivers",
        description="Delete drivers associated with this morph",
        default=True)

    def drawExtra(self, context):
        self.layout.prop(self, "useDeleteShapekeys")
        self.layout.prop(self, "useDeleteDrivers")
        if self.useDeleteDrivers:
            self.layout.prop(self, "useDeleteProps")

    def run(self, context):
        items = [(item.index, item.name) for item in self.getSelectedItems()]
        items.sort()
        items.reverse()
        ob = context.object
        if ob.type == 'ARMATURE':
            self.runRig(context, ob, items)
        elif ob.type == 'MESH':
            self.runMesh(context, ob, items)

    def runMesh(self, context, ob, items):
        for idx, key in items:
            cat = ob.DazMorphCats[key]
            ob.DazMorphCats.remove(idx)
        if len(ob.DazMorphCats) == 0:
            ob.DazMeshMorphs = False

    def runRig(self, context, rig, items):
        amt = rig.data
        for idx, key in items:
            cat = rig.DazMorphCats[key]
            for pg in cat.morphs:
                raw = pg.name
                final = PropsStatic.final(raw)
                rest = PropsStatic.rest(raw)
                if raw in rig.keys():
                    rig[raw] = 0.0
                if self.useDeleteDrivers:
                    self.removePropDrivers(rig, PropsStatic.ref(raw), rig)
                    self.removePropDrivers(amt, PropsStatic.ref(final), amt)
                    self.removePropDrivers(amt, PropsStatic.ref(rest), amt)
                for ob in rig.children:
                    if ob.type == 'MESH':
                        self.removePropDrivers(
                            ob.data.shape_keys, PropsStatic.ref(raw), rig)
                        self.removePropDrivers(
                            ob.data.shape_keys, PropsStatic.ref(final), amt)
                        if self.useDeleteShapekeys and ob.data.shape_keys:
                            if raw in ob.data.shape_keys.key_blocks.keys():
                                skey = ob.data.shape_keys.key_blocks[raw]
                                ob.shape_key_remove(skey)
                if raw in rig.keys():
                    self.removeFromPropGroups(rig, raw)
                if self.useDeleteProps and self.useDeleteDrivers:
                    if raw in rig.keys():
                        rig[raw] = 0.0
                        del rig[raw]
                    if final in amt.keys():
                        amt[final] = 0.0
                        del amt[final]
                    if rest in amt.keys():
                        amt[rest] = 0.0
                        del amt[rest]
            rig.DazMorphCats.remove(idx)
        if len(rig.DazMorphCats) == 0:
            rig.DazCustomMorphs = False

    def removePropDrivers(self, rna, path, rig):
        def matchesPath(var, path, rig):
            if var.type == 'SINGLE_PROP':
                trg = var.targets[0]
                return (trg.id == rig and trg.data_path == path)
            return False

        if rna is None or rna.animation_data is None:
            return
        fcus = []
        for fcu in rna.animation_data.drivers:
            if fcu.data_path == path:
                fcus.append(fcu)
                continue
            vars = []
            keep = False
            for var in fcu.driver.variables:
                if matchesPath(var, path, rig):
                    vars.append(var)
                else:
                    keep = True
            if keep:
                if fcu.driver.type == 'SCRIPTED':
                    string = fcu.driver.expression
                    for var in vars:
                        string = string.replace(var.name, "0")
                    fcu.driver.expression = string
                for var in vars:
                    fcu.driver.variables.remove(var)
            else:
                fcus.append(fcu)
        for fcu in fcus:
            try:
                rna.driver_remove(fcu.data_path, fcu.array_index)
            except TypeError:
                pass

    def removeFromPropGroups(self, rig, prop):
        for morphset in theStandardMorphSets:
            pgs = getattr(rig, "Daz" + morphset)
            removeFromPropGroup(pgs, prop)

    def selectCondition(self, item):
        return True

    def getKeys(self, rig, ob):
        keys = []
        for cat in ob.DazMorphCats:
            key = cat.name
            keys.append((key, key, key))
        return keys


# ------------------------------------------------------------------------
#   Select and unselect all
# ------------------------------------------------------------------------


class Activator(MorphsetString):
    useMesh: BoolProperty(default=False)

    def run(self, context):
        scn = context.scene
        if self.useMesh:
            ob = context.object
            morphs = getCustomMorphs(scn, ob, self.category)
        else:
            ob = getRigFromObject(context.object)
            morphs = getRelevantMorphs(scn, ob, self.morphset, self.category)
        for morph in morphs:
            setActivated(ob, morph, self.activate)


def setActivated(ob, key, value):
    from daz_import.driver import setBoolProp
    if ob is None:
        return
    pg = getActivateGroup(ob, key)
    setBoolProp(pg, "active", value)


def getActivated(ob, rna, key, force=False):
    if key not in rna.keys():
        return False
    elif force:
        return True
    else:
        pg = getActivateGroup(ob, key)
        return pg.active


def getExistingActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        return None


def getActivateGroup(rig, key):
    if key in rig.DazActivated.keys():
        return rig.DazActivated[key]
    else:
        try:
            pg = rig.DazActivated.add()
            pg.name = key
            return pg
        except TypeError as err:
            msg = "Failed to load morph, because\n%s" % err
        raise DazError(msg)


@Registrar()
class DAZ_OT_ActivateAll(DazOperator, Activator):
    bl_idname = "daz.activate_all"
    bl_label = "Select All"
    bl_description = "Select all morphs of this type"
    bl_options = {'UNDO'}

    activate = True


@Registrar()
class DAZ_OT_DeactivateAll(DazOperator, Activator):
    bl_idname = "daz.deactivate_all"
    bl_label = "Unselect All"
    bl_description = "Unselect all morphs of this type"
    bl_options = {'UNDO'}

    activate = False

# ------------------------------------------------------------------------
#   Prettifying
# ------------------------------------------------------------------------


def prettifyAll(context):
    from daz_import.driver import setBoolProp
    scn = context.scene
    for ob in BlenderStatic.selected(context):
        for prop in ob.keys():
            if prop[0:7] == "DazShow":
                setBoolProp(ob, prop, True)
            elif prop[0:3] in ["Mhh", "DzM"]:
                setBoolProp(ob, prop, True)
        for cat in ob.DazMorphCats:
            setBoolProp(cat, "active", True)
            for morph in cat.morphs:
                if morph.name in ob.keys():
                    Props.set_overridable(ob, morph.name)
        for pg in ob.DazActivated:
            setBoolProp(pg, "active", True)


@Registrar()
class DAZ_OT_Prettify(DazOperator):
    bl_idname = "daz.prettify"
    bl_label = "Prettify Panels"
    bl_description = (
        "Change sliders to checkboxes\n" +
        "(If boolean options appear as sliders, use this button to refresh them)"
    )
    bl_options = {'UNDO'}

    def run(self, context):
        prettifyAll(context)

# ------------------------------------------------------------------
#   Clear morphs
# ------------------------------------------------------------------


def getRelevantMorphs(scn, rig, morphset, category):
    filter = scn.DazFilter.lower()
    morphs = []
    if rig is None:
        return morphs
    if morphset == "Custom":
        return getCustomMorphs(scn, rig, category)
    elif rig.DazMorphPrefixes:
        for key in rig.keys():
            if key[0:2] == "Dz":
                raise DazError("OLD morphs", rig, key)
    elif morphset == "All":
        for mset in theStandardMorphSets:
            pgs = getattr(rig, "Daz"+mset)
            morphs += [key for key in pgs.keys() if filter in key.lower()]
        for cat in rig.DazMorphCats:
            morphs += [morph.name for morph in cat.morphs if filter in morph.name.lower()]
    else:
        pgs = getattr(rig, "Daz"+morphset)
        morphs += [key for key in pgs.keys() if filter in key.lower()]
    return morphs


def getCustomMorphs(scn, ob, category):
    filter = scn.DazFilter.lower()
    morphs = []
    if category:
        for cat in ob.DazMorphCats:
            if cat.name == category:
                morphs = [
                    morph.name for morph in cat.morphs if filter in morph.name.lower()]
                return morphs
    else:
        for cat in ob.DazMorphCats:
            morphs += [morph.name for morph in cat.morphs if filter in morph.name.lower()]
    return morphs


def setMorphs(value, rig, morphset, category, scn, frame, force):
    morphs = getRelevantMorphs(scn, rig, morphset, category)
    for morph in morphs:
        if (getActivated(rig, rig, morph, force) and
                isinstance(rig[morph], float)):
            rig[morph] = value
            autoKeyProp(rig, morph, scn, frame, force)


def clearShapes(ob, category, scn, frame):
    skeys = ob.data.shape_keys
    if skeys is None:
        return
    morphs = getCustomMorphs(scn, ob, category)
    for morph in morphs:
        if getActivated(ob, skeys.key_blocks, morph):
            skeys.key_blocks[morph].value = 0.0
            autoKeyShape(skeys, morph, scn, frame)


@Registrar()
class DAZ_OT_ClearMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.clear_morphs"
    bl_label = "Clear Morphs"
    bl_description = "Set all selected morphs of specified type to zero.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            setMorphs(0.0, rig, self.morphset, self.category,
                      scn, scn.frame_current, False)
            Updating.rig_drivers(context, rig)


@Registrar()
class DAZ_OT_SetMorphs(DazPropsOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.set_morphs"
    bl_label = "Set Morphs"
    bl_description = "Set all selected morphs of specified type to given value.\nDoes not affect integer properties"
    bl_options = {'UNDO'}

    value: FloatProperty(
        name="Value",
        description="Set all selected morphs to this value",
        default=1.0)

    def draw(self, context):
        self.layout.prop(self, "value")

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            setMorphs(self.value, rig, self.morphset,
                      self.category, scn, scn.frame_current, False)
            Updating.rig_drivers(context, rig)


@Registrar()
class DAZ_OT_ClearShapes(DazOperator, MorphsetString):
    bl_idname = "daz.clear_shapes"
    bl_label = "Clear Shapes"
    bl_description = "Set all shapekeys values of specified type to zero"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        scn = context.scene
        clearShapes(context.object, self.category, scn, scn.frame_current)

# ------------------------------------------------------------------
#   Add morphs to keyset
# ------------------------------------------------------------------


@Registrar()
class DAZ_OT_AddKeysets(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.add_keyset"
    bl_label = "Keyset"
    bl_description = "Add selected morphs to active custom keying set, or make new one"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            aksi = scn.keying_sets.active_index
            if aksi <= -1:
                aks = scn.keying_sets.new(
                    idname="daz_morphs", name="daz_morphs")
            aks = scn.keying_sets.active
            morphs = getRelevantMorphs(scn, rig, self.morphset, self.category)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    aks.paths.add(rig.id_data, PropsStatic.ref(morph))
            Updating.rig_drivers(context, rig)

# ------------------------------------------------------------------
#   Set morph keys
# ------------------------------------------------------------------


@Registrar()
class DAZ_OT_KeyMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.key_morphs"
    bl_label = "Set Keys"
    bl_description = "Set keys for all selected morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig:
            scn = context.scene
            morphs = getRelevantMorphs(scn, rig, self.morphset, self.category)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    keyProp(rig, morph, scn.frame_current)
            Updating.rig_drivers(context, rig)


@Registrar()
class DAZ_OT_KeyShapes(DazOperator, MorphsetString, IsMesh):
    bl_idname = "daz.key_shapes"
    bl_label = "Set Keys"
    bl_description = "Set keys for all shapes of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys:
            scn = context.scene
            if self.category:
                cats = [ob.DazMorphCats[self.category]]
            else:
                cats = ob.DazMorphCats
            for cat in cats:
                for morph in cat.morphs:
                    if getActivated(ob, skeys.key_blocks, morph.name):
                        keyShape(skeys, morph.name, scn.frame_current)

# ------------------------------------------------------------------
#   Remove morph keys
# ------------------------------------------------------------------


@Registrar()
class DAZ_OT_UnkeyMorphs(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.unkey_morphs"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all selected morphs of specified type at current frame"
    bl_options = {'UNDO'}

    def run(self, context):
        rig = getRigFromObject(context.object)
        if rig and rig.animation_data and rig.animation_data.action:
            scn = context.scene
            morphs = getRelevantMorphs(scn, rig, self.morphset, self.category)
            for morph in morphs:
                if getActivated(rig, rig, morph):
                    unkeyProp(rig, morph, scn.frame_current)
            Updating.rig_drivers(context, rig)


@Registrar()
class DAZ_OT_UnkeyShapes(DazOperator, MorphsetString):
    bl_idname = "daz.unkey_shapes"
    bl_label = "Remove Keys"
    bl_description = "Remove keys from all shapekeys of specified type at current frame"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys and skeys.animation_data and skeys.animation_data.action:
            scn = context.scene
            if self.category:
                cats = [ob.DazMorphCats[self.category]]
            else:
                cats = ob.DazMorphCats
            for cat in cats:
                for morph in cat.morphs:
                    if getActivated(ob, skeys.key_blocks, morph.name):
                        unkeyShape(skeys, morph.name, scn.frame_current)

# ------------------------------------------------------------------
#   Update property limits
# ------------------------------------------------------------------


@Registrar()
class DAZ_OT_UpdateSliderLimits(DazOperator, GeneralMorphSelector, IsMeshArmature):
    bl_idname = "daz.update_slider_limits"
    bl_label = "Update Slider Limits"
    bl_description = "Update slider min and max values"
    bl_options = {'UNDO'}

    min: FloatProperty(
        name="Min",
        description="Minimum slider value",
        default=0.0)

    max: FloatProperty(
        name="Max",
        description="Maximum slider value",
        default=1.0)

    useSliders: BoolProperty(
        name="Sliders",
        description="Update min and max for slider values",
        default=True)

    useFinal: BoolProperty(
        name="Final",
        description="Update min and max for final values",
        default=True)

    useShapekeys: BoolProperty(
        name="Shapekeys",
        description="Update min and max for shapekeys",
        default=True)

    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "min")
        row.prop(self, "max")
        row = self.layout.row()
        row.prop(self, "useSliders")
        row.prop(self, "useFinal")
        row.prop(self, "useShapekeys")
        GeneralMorphSelector.draw(self, context)

    def run(self, context):
        ob = context.object
        rig = getRigFromObject(ob)
        self.props = [item.name.lower() for item in self.getSelectedItems()]
        if rig:
            self.updatePropLimits(rig, context)
        if ob != rig:
            self.updatePropLimits(ob, context)

    def updatePropLimits(self, rig, context):
        from daz_import.driver import setFloatProp
        for ob in rig.children:
            if ob.type == 'MESH' and ob.data.shape_keys and self.useShapekeys:
                for skey in ob.data.shape_keys.key_blocks:
                    if skey.name.lower() in self.props:
                        skey.slider_min = self.min
                        skey.slider_max = self.max
        amt = rig.data
        for raw in rig.keys():
            if raw.lower() in self.props:
                if self.useSliders:
                    setFloatProp(rig, raw, rig[raw], self.min, self.max)
                if self.useFinal:
                    final = PropsStatic.final(raw)
                    setFloatProp(amt, final, amt[final], self.min, self.max)
        Updating.rig_drivers(context, rig)
        print("Slider limits updated")

# ------------------------------------------------------------------
#   Remove all morph drivers
# ------------------------------------------------------------------


@Registrar()
class DAZ_OT_RemoveAllDrivers(DazPropsOperator, DriverUser, IsMeshArmature):
    bl_idname = "daz.remove_all_drivers"
    bl_label = "Remove All Drivers"
    bl_description = "Remove all drivers from selected objects"
    bl_options = {'UNDO'}

    useRemoveProps: BoolProperty(
        name="Remove Properties",
        description="Also remove driving properties",
        default=True)

    useRemoveAllProps: BoolProperty(
        name="Remove All Properties",
        description="Also remove other properties",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "useRemoveProps")
        if self.useRemoveProps:
            self.layout.prop(self, "useRemoveAllProps")

    def run(self, context):
        self.targets = {}
        meshes = BlenderStatic.selected_meshes(context)
        rigs = BlenderStatic.selected_armature(context)
        for ob in meshes:
            skeys = ob.data.shape_keys
            if skeys:
                self.removeDrivers(skeys)
        for rig in rigs:
            self.removeDrivers(rig.data)
            self.removeDrivers(rig)

        if not self.useRemoveProps:
            return
        for path, rna in self.targets.items():
            words = path.split('"')
            if len(words) == 5 and words[0] == "pose.bones[" and words[4] == "]":
                bname = words[1]
                prop = words[3]
                pb = rna.pose.bones[bname]
                if prop in pb.keys():
                    del pb[prop]
            elif len(words) == 3 and words[2] == "]":
                prop = words[1]
                if prop in rna.keys():
                    del rna[prop]

        if not self.useRemoveAllProps:
            return
        for rig in rigs:
            for key in list(rig.keys()):
                if not (key[0] == "_" or hasattr(rig, key)):
                    del rig[key]
            for key in list(rig.data.keys()):
                if not (key[0] == "_" or hasattr(rig.data, key)):
                    del rig.data[key]

    def removeDrivers(self, rna):
        if not rna.animation_data:
            return
        for fcu in list(rna.animation_data.drivers):
            if fcu.driver:
                for var in fcu.driver.variables:
                    for trg in var.targets:
                        self.targets[trg.data_path] = trg.id
            idx = self.getArrayIndex(fcu)
            self.removeDriver(rna, fcu.data_path, idx)

# -------------------------------------------------------------
#   Add driven value nodes
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_AddDrivenValueNodes(DazOperator, Selector, DriverUser, IsMesh):
    bl_idname = "daz.add_driven_value_nodes"
    bl_label = "Add Driven Value Nodes"
    bl_description = "Add driven value nodes"
    bl_options = {'UNDO'}

    allSets = theMorphSets

    def getKeys(self, rig, ob):
        skeys = ob.data.shape_keys
        if skeys:
            return [(sname, sname, "All") for sname in skeys.key_blocks.keys()]
        else:
            return []

    def draw(self, context):
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        self.layout.label(text="Active material: %s" % mat.name)
        Selector.draw(self, context)

    def run(self, context):
        from daz_import.driver import getShapekeyDriver
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys is None:
            raise DazError("Object %s has not shapekeys" % ob.name)
        rig = getRigFromObject(ob)
        mat = ob.data.materials[ob.active_material_index]
        props = self.getSelectedProps()
        nprops = len(props)
        for n, prop in enumerate(props):
            skey = skeys.key_blocks[prop]
            fcu = getShapekeyDriver(skeys, prop)
            node = mat.node_tree.nodes.new(type="ShaderNodeValue")
            node.name = node.label = skey.name
            node.location = (-1100, 250-250*n)
            if fcu:
                channel = ('nodes["%s"].outputs[0].default_value' % node.name)
                fcu2 = mat.node_tree.driver_add(channel)
                fcu2 = self.copyFcurve(fcu, fcu2)

# -------------------------------------------------------------
#   Add and remove driver
# -------------------------------------------------------------


class AddRemoveDriver:

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if (rig and rig.type == 'ARMATURE'):
            for sname in self.getSelectedProps():
                self.handleShapekey(sname, rig, ob)
            Updating.rig_drivers(context, rig)
        Updating.drivers(ob.data.shape_keys)

    def invoke(self, context, event):
        self.selection.clear()
        ob = context.object
        rig = ob.parent
        if (rig and rig.type != 'ARMATURE'):
            rig = None
        skeys = ob.data.shape_keys
        if skeys:
            for skey in skeys.key_blocks[1:]:
                if self.includeShapekey(skeys, skey.name):
                    item = self.selection.add()
                    item.name = item.text = skey.name
                    item.category = self.getCategory(rig, ob, skey.name)
                    item.select = False
        return self.invokeDialog(context)

    def createRawFinPair(self, rig, raw, rna, channel, value, min, max):
        from daz_import.driver import addDriverVar, setFloatProp, removeModifiers
        final = PropsStatic.final(raw)
        setFloatProp(rig, raw, value, min, max)
        setFloatProp(rig.data, final, value, min, max)
        fcu = rig.data.driver_add(PropsStatic.ref(final))
        removeModifiers(fcu)
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", PropsStatic.ref(raw), rig)
        fcu.driver.expression = "a"
        fcu = rna.driver_add(channel)
        removeModifiers(fcu)
        fcu.driver.type = 'SCRIPTED'
        addDriverVar(fcu, "a", PropsStatic.ref(final), rig.data)
        fcu.driver.expression = "a"


@Registrar()
class DAZ_OT_AddShapeToCategory(DazOperator, AddRemoveDriver, Selector, CustomEnums, CategoryString):
    bl_idname = "daz.add_shape_to_category"
    bl_label = "Add Shapekey To Category"
    bl_description = "Add selected shapekeys to mesh category"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    makenew: BoolProperty(
        name="New Category",
        description="Create a new category",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "makenew")
        if self.makenew:
            self.layout.prop(self, "category")
        else:
            self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def run(self, context):
        ob = context.object
        if self.makenew:
            cat = self.category
        elif self.custom == "All":
            raise DazError("Cannot add to all categories")
        else:
            cat = self.custom
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            addToCategories(ob, [sname], cat)
            ob.DazMeshMorphs = True

    def includeShapekey(self, skeys, sname):
        return True

    def getCategory(self, rig, ob, sname):
        return ""


@Registrar()
class DAZ_OT_AddShapekeyDrivers(DazOperator, AddRemoveDriver, Selector, CategoryString, IsMesh):
    bl_idname = "daz.add_shapekey_drivers"
    bl_label = "Add Shapekey Drivers"
    bl_description = "Add rig drivers to shapekeys"
    bl_options = {'UNDO'}

    def draw(self, context):
        self.layout.prop(self, "category")
        Selector.draw(self, context)

    def handleShapekey(self, sname, rig, ob):
        from daz_import.driver import getShapekeyDriver
        skeys = ob.data.shape_keys
        skey = skeys.key_blocks[sname]
        if getShapekeyDriver(skeys, skey.name):
            raise DazError("Shapekey %s is already driven" % skey.name)
        self.createRawFinPair(rig, sname, skey, "value",
                              skey.value, skey.slider_min, skey.slider_max)
        addToCategories(rig, [sname], self.category)
        rig.DazCustomMorphs = True

    def includeShapekey(self, skeys, sname):
        from daz_import.driver import getShapekeyDriver
        return (not getShapekeyDriver(skeys, sname))

    def getCategory(self, rig, ob, sname):
        return ""


@Registrar()
class DAZ_OT_RemoveShapeFromCategory(DazOperator, AddRemoveDriver, CustomSelector):
    bl_idname = "daz.remove_shape_from_category"
    bl_label = "Remove Shapekey From Category"
    bl_description = "Remove selected shapekeys from mesh category"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def draw(self, context):
        self.layout.prop(self, "custom")
        Selector.draw(self, context)

    def run(self, context):
        ob = context.object
        snames = []
        for sname in self.getSelectedProps():
            skey = ob.data.shape_keys.key_blocks[sname]
            snames.append(skey.name)
        if self.custom == "All":
            for cat in ob.DazMorphCats:
                self.removeFromCategory(ob, snames, cat.name)
        else:
            self.removeFromCategory(ob, snames, self.custom)
        Updating.drivers(ob.data.shape_keys)

    def includeShapekey(self, skeys, sname):
        return True

    def getCategory(self, rig, ob, sname):
        for cat in ob.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""

    def removeFromCategory(self, ob, props, category):
        if category in ob.DazMorphCats.keys():
            cat = ob.DazMorphCats[category]
            for prop in props:
                removeFromPropGroup(cat.morphs, prop)


@Registrar()
class DAZ_OT_RemoveShapekeyDrivers(DazOperator, AddRemoveDriver, CustomSelector, IsMesh):
    bl_idname = "daz.remove_shapekey_drivers"
    bl_label = "Remove Shapekey Drivers"
    bl_description = "Remove rig drivers from shapekeys"
    bl_options = {'UNDO'}

    def handleShapekey(self, sname, rig, ob):
        skey = ob.data.shape_keys.key_blocks[sname]
        skey.driver_remove("value")
        rig = ob.parent
        if rig and rig.type == 'ARMATURE':
            final = PropsStatic.final(sname)
            rig.data.driver_remove(PropsStatic.ref(final))
            if final in rig.data.keys():
                del rig.data[final]
            if sname in rig.keys():
                del rig[sname]

    def includeShapekey(self, skeys, sname):
        from daz_import.driver import getShapekeyDriver
        return getShapekeyDriver(skeys, sname)

    def getCategory(self, rig, ob, sname):
        if rig is None:
            return ""
        for cat in rig.DazMorphCats:
            for morph in cat.morphs:
                if sname == morph.name:
                    return cat.name
        return ""

# -------------------------------------------------------------
#
# -------------------------------------------------------------


def getRigFromObject(ob, useMesh=False):
    if ob.type == 'ARMATURE':
        return ob
    elif useMesh and ob.type == 'MESH':
        return ob
    else:
        ob = ob.parent
        if ob is None or ob.type != 'ARMATURE':
            return None
        return ob


@Registrar()
class DAZ_OT_ToggleAllCats(DazOperator, IsMeshArmature):
    bl_idname = "daz.toggle_all_cats"
    bl_label = "Toggle All Categories"
    bl_description = "Toggle all morph categories on and off"
    bl_options = {'UNDO'}

    useMesh: BoolProperty(default=False)
    useOpen: BoolProperty()

    def run(self, context):
        rig = getRigFromObject(context.object, self.useMesh)
        if rig:
            for cat in rig.DazMorphCats:
                cat["active"] = self.useOpen

# -------------------------------------------------------------
#
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_PinProp(DazOperator, MorphsetString, IsMeshArmature):
    bl_idname = "daz.pin_prop"
    bl_label = ""
    bl_description = "Pin property"
    bl_options = {'UNDO'}

    key: StringProperty()

    def run(self, context):
        rig = getRigFromObject(context.object)
        scn = context.scene
        setupMorphPaths(False)
        pinProp(rig, scn, self.key, self.morphset,
                self.category, scn.frame_current)
        Updating.rig_drivers(context, rig)


@Registrar()
class DAZ_OT_PinShape(DazOperator, MorphsetString):
    bl_idname = "daz.pin_shape"
    bl_label = ""
    bl_description = "Pin shapekey value"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    key: StringProperty()

    def run(self, context):
        ob = context.object
        scn = context.scene
        pinShape(ob, scn, self.key, self.category, scn.frame_current)

# ---------------------------------------------------------------------
#   Load Moho
# ---------------------------------------------------------------------


@Registrar()
class DAZ_OT_LoadMoho(DazOperator, DatFile, ActionOptions, SingleFile, IsMeshArmature):
    bl_idname = "daz.load_moho"
    bl_label = "Load Moho"
    bl_description = "Load Moho (.dat) file"
    bl_options = {'UNDO'}

    emphasis: FloatProperty(
        name="Emphasis",
        description="Speech strength",
        min=0.2, max=5.0,
        default=1.0)

    useUpdateLimits: BoolProperty(
        name="Update Limits",
        description="Update limits of open vowels to account for emphasis",
        default=True)

    useRelax: BoolProperty(
        name="Relax Animation",
        description="Relax the Moho animation to make it more natural",
        default=True)

    def draw(self, context):
        self.layout.prop(self, "useRelax")
        if self.useRelax:
            self.layout.prop(self, "emphasis")
            self.layout.prop(self, "useUpdateLimits")
        self.layout.separator()
        self.layout.prop(self, "makeNewAction")
        if self.makeNewAction:
            self.layout.prop(self, "actionName")
        self.layout.prop(self, "atFrameOne")

    def storeState(self, context):
        scn = context.scene
        self.auto = scn.tool_settings.use_keyframe_insert_auto
        scn.tool_settings.use_keyframe_insert_auto = True
        DazOperator.storeState(self, context)

    def restoreState(self, context):
        scn = context.scene
        scn.tool_settings.use_keyframe_insert_auto = self.auto
        DazOperator.restoreState(self, context)

    openVowels = ["AI", "E", "O"]
    silentVowels = ["FV", "MBP", "WQ"]

    def run(self, context):
        scn = context.scene
        rig = getRigFromObject(context.object)
        if rig is None:
            raise DazError("No armature found")
        self.clearAction(rig)
        if self.atFrameOne:
            frame0 = 0
        else:
            frame0 = scn.frame_current-1
        frames = self.readMoho()
        if self.useRelax:
            frames = self.improveMoho(frames)
            if self.useUpdateLimits:
                self.updateLimits(rig)
        for frame, moho, value in frames:
            if moho == "rest":
                setMorphs(0.0, rig, "Visemes", "", scn, frame, True)
            else:
                prop = self.getMohoKey(moho, rig)
                pinProp(rig, scn, prop, "Visemes",
                        "", frame+frame0, value=value)
        self.nameAction(rig)
        print("Moho file %s loaded" % self.filepath)

    def updateLimits(self, rig):
        from daz_import.driver import getPropMinMax, setPropMinMax
        for moho in self.openVowels:
            prop = self.getMohoKey(moho, rig)
            min, max = getPropMinMax(rig, prop)
            if max < self.emphasis:
                setPropMinMax(rig, prop, min, self.emphasis)
            final = PropsStatic.final(prop)
            if final in rig.data.keys():
                min, max = getPropMinMax(rig.data, final)
                if max < self.emphasis:
                    setPropMinMax(rig.data, final, min, self.emphasis)

    def readMoho(self):
        from daz_import.Lib.Files import FilePath
        frames = []

        with FilePath.safeOpen(self.filepath, "r") as fp:
            for n, line in enumerate(fp):
                words = line.split()
                if len(words) >= 2 and words[0].isdigit():
                    frames.append((int(words[0]), n, words[1]))

        frames.sort()
        return [(t, key, 1.0) for t, n, key in frames]

    def improveMoho(self, frames):
        first, frames = self.splitBeginning(frames)
        frames.reverse()
        last, frames = self.splitBeginning(frames)
        last.reverse()
        frames.reverse()
        key0 = "etc"
        emp = self.emphasis
        nframes = self.pruneRest(first)
        for n, frame in enumerate(frames[:-1]):
            t, key, y = frame
            t1, key1, y1 = frames[n+1]
            if key == "etc":
                if key0 == key1 and key0 in self.openVowels:
                    nframe = (t, key0, 0.5*emp)
                    nframes.append(nframe)
            elif key in self.openVowels:
                if key0 == key1 and key0 in self.silentVowels:
                    nframe = (t, key, 0.5*emp)
                elif key1 in self.silentVowels and t1-t <= 3:
                    nframe = (t, key, 0.5*emp)
                else:
                    nframe = (t, key, emp)
                nframes.append(nframe)
            else:
                nframes.append(frame)
            key0 = key
        nframes.append(frames[-1])
        last = self.pruneRest(last)
        return nframes + last

    def splitBeginning(self, frames):
        first = []
        for frame in frames:
            if frame[1] in ("rest", "etc"):
                first.append(frame)
            else:
                break
        n = len(first)
        return first, frames[n:]

    def pruneRest(self, frames):
        for frame in frames:
            if frame[1] == "rest":
                return [frame]
        return []

    def getMohoKey(self, moho, rig):
        Moho2Daz = {
            "rest": "Rest",
            "etc": "K",
            "AI": "AA",
            "O": "OW",
            "U": "UW",
            "WQ": "W",
            "L": "L",
            "E": "EH",
            "MBP": "M",
            "FV": "F"
        }
        daz = Moho2Daz[moho]
        for item in rig.DazVisemes:
            if item.text == daz:
                prop = item.name
                if prop in rig.keys():
                    return prop
        raise DazError("Missing viseme: %s (%s)" % (daz, moho))

# -------------------------------------------------------------
#   Convert pose to shapekey
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_ConvertMorphsToShapes(DazOperator, GeneralMorphSelector, IsMesh):
    bl_idname = "daz.convert_morphs_to_shapekeys"
    bl_label = "Convert Morphs To Shapekeys"
    bl_description = "Convert face rig morphs to shapekeys"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        rig = ob.parent
        if rig is None or rig.type != 'ARMATURE':
            return
        items = self.getSelectedItems()
        nitems = len(items)
        Progress.start("Convert morphs to shapekeys")
        for n, item in enumerate(items):
            Progress.show(n, nitems)
            key = item.name
            mname = item.text
            rig[key] = 0.0
            if (ob.data.shape_keys and
                    mname in ob.data.shape_keys.key_blocks.keys()):
                print("Skip", mname)
                continue
            if mname:
                mod = BlenderStatic.modifier(ob, 'ARMATURE')
                if mod:
                    rig[key] = 1.0
                    Updating.rig_drivers(context, rig)
                    self.applyArmature(ob, rig, mod, mname)
                    rig[key] = 0.0
        Updating.rig_drivers(context, rig)

    def applyArmature(self, ob, rig, mod, mname):
        mod.name = mname
        if bpy.app.version < (2, 90, 0):
            bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=mname)
        else:
            bpy.ops.object.modifier_apply_as_shapekey(modifier=mname)
        skey = ob.data.shape_keys.key_blocks[mname]
        skey.value = 0.0
        offsets = [(skey.data[vn].co - v.co).length for vn,
                   v in enumerate(ob.data.vertices)]
        omax = max(offsets)
        omin = min(offsets)
        eps = 1e-2 * ob.DazScale    # eps = 0.1 mm
        if abs(omax) < eps and abs(omin) < eps:
            idx = ob.data.shape_keys.key_blocks.keys().index(skey.name)
            ob.active_shape_key_index = idx
            bpy.ops.object.shape_key_remove()
            ob.active_shape_key_index = 0
        nmod = ob.modifiers.new(rig.name, "ARMATURE")
        nmod.object = rig
        nmod.use_deform_preserve_volume = True
        for i in range(len(ob.modifiers)-1):
            bpy.ops.object.modifier_move_up(modifier=nmod.name)

# -------------------------------------------------------------
#   Transfer verts to shapekeys
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_MeshToShape(DazOperator):
    bl_idname = "daz.transfer_mesh_to_shape"
    bl_label = "Transfer Mesh To Shapekey"
    bl_description = "Transfer selected mesh to active shapekey"
    pool = IsMesh.pool

    bl_options = {'UNDO'}

    def run(self, context):
        trg = context.object
        skeys = trg.data.shape_keys
        if skeys is None:
            raise DazError("Target mesh must have shapekeys")
        idx = trg.active_shape_key_index
        if idx == 0:
            raise DazError("Cannot transfer to Basic shapekeys")
        objects = [ob for ob in BlenderStatic.selected_meshes(
            context) if ob != trg]
        if len(objects) != 1:
            raise DazError("Exactly two meshes must be selected")
        src = objects[0]
        nsverts = len(src.data.vertices)
        ntverts = len(trg.data.vertices)
        if nsverts != ntverts:
            raise DazError("Vertex count mismatch:  \n%d != %d" %
                           (nsverts, ntverts))
        skey = skeys.key_blocks[idx]
        for v in src.data.vertices:
            skey.data[v.index].co = v.co

# -------------------------------------------------------------
#   Save and load morph presets
# -------------------------------------------------------------


@Registrar()
class DAZ_OT_SaveFavoMorphs(DazOperator, SingleFile, JsonFile, IsMeshArmature):
    bl_idname = "daz.save_favo_morphs"
    bl_label = "Save Favorite Morphs"
    bl_description = "Save favorite morphs"

    def invoke(self, context, event):
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from daz_import.Lib import Json
        rig = self.rig = getRigFromObject(context.object)
        struct = {"filetype": "favo_morphs"}
        self.addMorphUrls(rig, struct)
        for ob in rig.children:
            self.addMorphUrls(ob, struct)
        filepath = bpy.path.ensure_ext(self.filepath, ".json")
        Json.save(struct, filepath)

    def addMorphUrls(self, ob, struct):
        if len(ob.DazMorphUrls) == 0:
            return
        from urllib.parse import quote
        from daz_import.Elements.Finger import getFingerPrint
        url = quote(ob.DazUrl)
        ostruct = struct[url] = {}
        if ob.type == 'MESH':
            if ob.data.DazFingerPrint:
                ostruct["finger_print"] = ob.data.DazFingerPrint
            else:
                ostruct["finger_print"] = getFingerPrint(ob)
        mstruct = ostruct["morphs"] = {}
        for item in ob.DazMorphUrls:
            if item.morphset == "Custom":
                key = "Custom/%s" % item.category
            else:
                key = item.morphset
            if key not in mstruct.keys():
                mstruct[key] = []
            mstruct[key].append((quote(item.name), item.text, item.bodypart))


@Registrar()
class DAZ_OT_LoadFavoMorphs(DazOperator, MorphLoader, SingleFile, JsonFile, IsMeshArmature):
    bl_idname = "daz.load_favo_morphs"
    bl_label = "Load Favorite Morphs"
    bl_description = "Load favorite morphs"

    ignoreFinger: BoolProperty(
        name="Ignore Fingerprint",
        description="Ignore the mesh fingerprint which describes the mesh topology",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "ignoreFinger")

    def invoke(self, context, event):
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from daz_import.Lib import Json
        filepath = bpy.path.ensure_ext(self.filepath, ".json")
        struct = Json.load(filepath)
        if ("filetype" not in struct.keys() or
                struct["filetype"] != "favo_morphs"):
            raise DazError("This file does not contain favorite morphs")
        rig = self.rig = getRigFromObject(context.object)
        rig.DazMorphUrls.clear()
        self.loadPreset(rig, rig, struct, context)
        for ob in rig.children:
            if ob.type == 'MESH':
                self.mesh = ob
                self.loadPreset(ob, rig, struct, context)

    def loadPreset(self, ob, rig, struct, context):
        from urllib.parse import quote
        from daz_import.Elements.Finger import getFingerPrint
        url = quote(ob.DazUrl).lower()
        lstruct = dict([(key.lower(), value) for key, value in struct.items()])
        if url not in lstruct.keys():
            return
        ustruct = lstruct[url]
        if (ob.type == 'MESH' and
            "finger_print" in ustruct.keys() and
                not self.ignoreFinger):
            if ob.data.DazFingerPrint:
                finger = ob.data.DazFingerPrint
            else:
                finger = getFingerPrint(ob)
            if finger != ustruct["finger_print"]:
                print("Fingerprint mismatch:\n%s != %s" %
                      (finger, ustruct["finger_print"]))
                return
        for morphset in theStandardMorphSets:
            self.adjuster = theAdjusters[morphset]
            self.loadMorphSet(context, morphset, ustruct, morphset, "", True)
        for morphset in theJCMMorphSets:
            self.adjuster = theAdjusters[morphset]
            self.loadMorphSet(context, morphset, ustruct, morphset, "", False)
        for key in ustruct["morphs"].keys():
            if key[0:7] == "Custom/":
                rig.DazCustomMorphs = True
                self.adjuster = "Adjust %s" % key
                self.loadMorphSet(context, key, ustruct,
                                  "Custom", key[7:], True)

    def loadMorphSet(self, context, key, ustruct, morphset, cat, hide):
        if key in ustruct["morphs"].keys():
            infos = ustruct["morphs"][key]
            if not infos:
                return
            self.morphset = morphset
            self.category = cat
            self.hideable = hide

            namepaths = [(name, DazPath.unquote(ref), bodypart)
                         for ref, name, bodypart in infos]
            self.getAllMorphs(namepaths, context)

    def findPropGroup(self, prop):
        if self.rig is None:
            return None
        elif self.morphset == "Custom":
            cats = self.rig.DazMorphCats
            if self.category not in cats.keys():
                cat = cats.add()
                cat.name = self.category
            else:
                cat = cats[self.category]
            return cat.morphs
        else:
            return getattr(self.rig, "Daz"+self.morphset)

# -------------------------------------------------------------
#   Property groups, for drivers
# -------------------------------------------------------------


@Registrar.func
def register():
    bpy.types.Object.DazCustomMorphs = BoolProperty(default=False)
    bpy.types.Object.DazMeshMorphs = BoolProperty(default=False)
    bpy.types.Object.DazMorphAuto = BoolProperty(default=False)

    bpy.types.Object.DazMorphPrefixes = BoolProperty(default=True)
    for morphset in theMorphSets:
        setattr(bpy.types.Object, "Daz"+morphset,
                CollectionProperty(type=DazTextGroup))
    bpy.types.Object.DazMorphUrls = CollectionProperty(type=DazMorphInfoGroup)
    bpy.types.Object.DazAutoFollow = CollectionProperty(type=DazTextGroup)
    bpy.types.Object.DazAlias = CollectionProperty(type=DazStringGroup)

    if bpy.app.version < (2, 90, 0):
        bpy.types.Object.DazActivated = CollectionProperty(type=DazActiveGroup)
        bpy.types.Object.DazMorphCats = CollectionProperty(type=DazCategory)
    else:
        bpy.types.Object.DazActivated = CollectionProperty(
            type=DazActiveGroup, override={'LIBRARY_OVERRIDABLE'})
        bpy.types.Object.DazMorphCats = CollectionProperty(
            type=DazCategory, override={'LIBRARY_OVERRIDABLE'})

    bpy.types.Mesh.DazBodyPart = CollectionProperty(type=DazStringGroup)
    bpy.types.Scene.DazMorphCatsContent = EnumProperty(
        items=[],
        name="Morph")

    bpy.types.Scene.DazNewCatName = StringProperty(
        name="New Name",
        default="Name")

    bpy.types.Scene.DazSelector = CollectionProperty(type=DazSelectGroup)
