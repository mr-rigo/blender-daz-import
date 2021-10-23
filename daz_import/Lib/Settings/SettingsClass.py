import os
from sys import platform
from .JsonObject import JsonObject
from .Paths import Paths

point_ = __file__
for _ in range(3):
    point_ = os.path.dirname(point_)

root_ = point_
debug_root_ = os.path.dirname(root_)


class SettingsClass(JsonObject):
    def __init__(self):
        self.is_windows_ = platform == 'win32'

        if folder := Debug.get('DAZ_LIBRARY'):
            self.contentDirs = [folder]
        else:
            self.contentDirs = [
                Paths.path_fix("~/Documents/DAZ 3D/Studio/My Library"),
                "C:/Users/Public/Documents/My DAZ 3D Library",
            ]

        if folder := Debug.get('MDL_FOLDER'):
            self.mdlDirs = [folder]
        else:
            self.mdlDirs = ["C:/Program Files/DAZ 3D/DAZStudio4/shaders/iray"]

        self.cloudDirs = []
        self.errorPath = Paths.path_fix("~/Documents/daz_importer_errors.txt")
        self.rootPath = Paths.path_fix("~/import-daz-paths.json")

        self.unitScale = 0.01
        self.verbosity = 2
        self.useDump = False
        self.zup = True
        self.unflipped = False
        self.useMakeHiddenSliders = False
        self.showHiddenObjects = False

        self.materialMethod = 'BSDF'
        self.refractiveMethod = 'BSDF'
        self.sssMethod = 'RANDOM_WALK'
        self.viewportColors = 'GUESS'

        self.useQuaternions = False
        self.caseSensitivePaths = (platform != 'win32')
        self.mergeShells = True
        self.pruneNodes = True

        self.bumpFactor = 1.0
        self.useFakeCaustics = True
        self.useFakeTranslucencyTexture = False
        self.handleRenderSettings = "UPDATE"
        self.handleLightSettings = "WARN"

        self.useDisplacement = True
        self.useEmission = True
        self.useReflection = True
        self.useVolume = True
        self.useWorld = 'DOME'

        self.reuseMaterials = False
        self.hairMaterialMethod = 'HAIR_BSDF'
        self.imageInterpolation = 'Cubic'

        self.useAdjusters = 'NONE'
        self.customMin = -1.0
        self.customMax = 1.0
        self.morphMultiplier = 1.0
        self.finalLimits = 'DAZ'
        self.sliderLimits = 'DAZ'
        self.showFinalProps = False
        self.useERC = False
        self.useStripCategory = False
        self.useModifiedMesh = False

        self.useLockLoc = True
        self.useLimitLoc = True
        self.useLockRot = True
        self.useLimitRot = True
        self.displayLimitRot = False
        self.useConnectClose = False

        self.useInstancing = True
        self.useHighDef = True
        self.useMultires = True
        self.useMultiUvLayers = True
        self.useMultiShapes = True
        self.useAutoSmooth = False
        self.useSimulation = True

        # No sync

        self.NewFaceLayer_ = 18
        self.BUILD_ = 629
        self.theSilentMode_ = True
        self.theMessage_ = ""
        self.theErrorLines_ = []

        self.theTrace_ = []

        self.theImagedDefaults_ = ";*.png;*.jpeg;*.jpg;*.bmp"
        self.theImageExtensions_ = ["png", "jpeg", "jpg", "bmp", "tif", "tiff"]

        self.theDazExtensions_ = ["dsf", "duf"]
        self.theDazUpcaseExtensions_ = [
            ext.upper() for ext in self.theDazExtensions_]

        self.theDazDefaults_ = [
            "*.%s" % ext for ext in self.theDazExtensions_+self.theDazUpcaseExtensions_]
        self.theDazDefaults_ = ";".join(self.theDazDefaults_)

        self.root_ = root_
        self.debug_root_ = debug_root_

        self.theRestPoseFolder_ = os.path.join(self.root_, "data", "restposes")
        self.theParentsFolder_ = os.path.join(self.root_, "data", "parents")
        self.theIkPoseFolder_ = os.path.join(self.root_, "data", "ikposes")

        self.theRestPoseItems_ = []

        for file in os.listdir(self.theRestPoseFolder_):
            fname = os.path.splitext(file)[0]
            name = fname.replace("_", " ").capitalize()
            self.theRestPoseItems_.append((fname, name, name))

        self.theUseDumpErrors_ = False

        path = 'daz-import.json'

        if Debug.get('local_settings'):
            path = Paths.join(self.debug_root_, path)
        else:
            path = f'~/{path}'
            path = Paths.path_fix(path)

        super().__init__(path)
        print("Load settings from", path)
        self.__post_init()

    def __post_init(self):
        self.scale_ = 0.1
        self.skinColor_ = None
        self.clothesColor_ = None
        self.fitFile_ = False
        self.autoMaterials_ = True
        self.morphStrength_ = 1.0

        self.useNodes_ = False
        self.useGeometries_ = False
        self.useImages_ = False
        self.useMaterials_ = False
        self.useModifiers_ = False
        self.useMorph_ = False
        self.useMorphOnly_ = False
        self.useFormulas_ = False
        self.useHDObjects_ = False
        self.applyMorphs_ = False
        self.useAnimations_ = False
        self.useUV_ = False
        self.useWorld_ = 'NEVER'

        self.collection_ = None
        self.hdcollection_ = None
        self.refColls_ = None
        self.duplis_ = {}
        self.fps_ = 30
        self.integerFrames_ = True
        self.missingAssets_ = {}
        self.hdFailures_ = []
        self.hdWeights_ = []
        self.hdUvMissing_ = []
        self.deflectors_ = {}
        # self.materials_ = {}
        self.textures_ = {}
        # self.gammas_ = {}
        self.customShapes_ = []
        self.singleUser_ = False
        self.scene_ = ""
        self.render_ = None
        self.hiddenMaterial_ = None

        self.nViewChildren_ = 0
        self.nRenderChildren_ = 0
        self.hairMaterialMethod_ = self.hairMaterialMethod
        self.useSkullGroup_ = False

        self.usedFeatures_ = {
            "Bounces": True,
            "Diffuse": False,
            "Glossy": False,
            "Transparent": False,
            "SSS": False,
            "Volume": False,
        }

        self.rigname_ = None
        self.rigs_ = {None: []}
        self.meshes_ = {None: []}
        self.objects_ = {None: []}
        self.hairs_ = {None: []}
        self.hdmeshes_ = {None: []}
        self.warning_ = False
        self.hide_subsurf_ = True

    def __repr__(self):
        string = "<Settings Settings"
        for key in dir(self):
            if key[0] != "_":
                #attr = getattr(self, key)
                string += "\n  %s : %s" % (key, 0)
        return string + ">"

    def reset(self):
        from daz_import.Elements.Assets import Assets
        from daz_import.Collection import Collection

        self.theTrace_ = []
        Assets.clear()
        Collection.update()

        self.useStrict = False
        self.scene_ = ""

    def forAnimation(self, btn, ob):
        self.clear()
        self.reset()

        self.scale_ = ob.DazScale
        self.useNodes_ = True
        self.useAnimations_ = True

        if hasattr(btn, "fps"):
            self.fps_ = btn.fps
            self.integerFrames_ = btn.integerFrames

    def forMorphLoad(self, ob):
        self.clear()
        self.reset()
        
        self.scale_ = ob.DazScale
        self.useMorph_ = True
        self.useMorphOnly_ = True
        self.useFormulas_ = True
        self.applyMorphs_ = False
        self.useModifiers_ = True

    def import_mode(self, fitMeshes: str):
        self.clear()
        self.reset()

        self.scale_ = self.unitScale
        self.useNodes_ = True
        self.useGeometries_ = True
        self.useImages_ = True
        self.useMaterials_ = True
        self.useModifiers_ = True
        self.useUV_ = True
        self.useWorld_ = self.useWorld

        self.skinColor_ = (0.6, 0.4, 0.25, 1.0)
        self.clothesColor_ = (0.09, 0.01, 0.015, 1.0)
        self.useStrict = True
        self.singleUser_ = True
        # self.skinColor_ = self.skinColor
        # self.clothesColor_ = self.clothesColor

        if fitMeshes == 'SHARED':
            self.singleUser_ = False
        elif fitMeshes == 'UNIQUE':
            pass
        elif fitMeshes == 'MORPHED':
            self.useMorph_ = True
            self.morphStrength_ = 1.0
            # self.morphStrength_ = self.morphStrength
        elif fitMeshes == 'DBZFILE':
            self.fitFile_ = True

    def clear(self):
        self.__post_init()


path = 'debug.env.linux.json'
if platform == 'win32':
    path = 'debug.env.win.json'

Debug = JsonObject(Paths.join(debug_root_, path))
Settings = SettingsClass()
