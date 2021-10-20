import os

from typing import List, Dict, Any
from daz_import.Lib.Settings import Settings
from daz_import.Lib.ObjectDict import ObjectDict
from daz_import.Lib.Settings.Paths import Paths


class SceneStatic:
    SceneTable = {
        # General
        "DazUnitScale": "unitScale",
        "DazVerbosity": "verbosity",
        "DazErrorPath": "errorPath",
        "DazCaseSensitivePaths": "caseSensitivePaths",

        # Debugging
        "DazDump": "useDump",
        "DazZup": "zup",
        "DazMakeHiddenSliders": "useMakeHiddenSliders",
        "DazShowHiddenObjects": "showHiddenObjects",
        "DazMergeShells": "mergeShells",
        "DazPruneNodes": "pruneNodes",

        # Materials
        "DazMaterialMethod": "materialMethod",
        "DazSSSMethod": "sssMethod",
        "DazRefractiveMethod": "refractiveMethod",
        "DazHairMaterialMethod": "hairMaterialMethod",
        "DazViewportColor": "viewportColors",
        "DazUseWorld": "useWorld",
        "DazReuseMaterials": "reuseMaterials",
        "DazBumpFactor": "bumpFactor",
        "DazFakeCaustics": "useFakeCaustics",
        "DazFakeTranslucencyTexture": "useFakeTranslucencyTexture",
        "DazHandleRenderSettings": "handleRenderSettings",
        "DazHandleLightSettings": "handleLightSettings",
        "DazUseDisplacement": "useDisplacement",
        "DazUseEmission": "useEmission",
        "DazUseReflection": "useReflection",
        "DazUseVolume": "useVolume",
        "DazImageInterpolation": "imageInterpolation",

        # Properties
        "DazUseAdjusters": "useAdjusters",
        "DazCustomMin": "customMin",
        "DazCustomMax": "customMax",
        "DazMorphMultiplier": "morphMultiplier",
        "DazFinalLimits": "finalLimits",
        "DazSliderLimits": "sliderLimits",
        "DazShowFinalProps": "showFinalProps",
        "DazUseERC": "useERC",
        "DazStripCategory": "useStripCategory",
        "DazUseModifiedMesh": "useModifiedMesh",

        # Rigging
        "DazUnflipped": "unflipped",
        "DazUseQuaternions": "useQuaternions",
        "DazConnectClose": "useConnectClose",
        "DazUseLockLoc": "useLockLoc",
        "DazUseLimitLoc": "useLimitLoc",
        "DazUseLockRot": "useLockRot",
        "DazUseLimitRot": "useLimitRot",
        "DazDisplayLimitRot": "displayLimitRot",

        # Meshes
        "DazUseInstancing": "useInstancing",
        "DazHighdef": "useHighDef",
        "DazMultires": "useMultires",
        "DazMultiUvLayers": "useMultiUvLayers",
        "DazUseAutoSmooth": "useAutoSmooth",
        "DazSimulation": "useSimulation",
    }

    @classmethod
    def pathsToScene(cls, paths: List[str], pgs):
        pgs.clear()
        for path in paths:
            pg = pgs.add()
            pg.name = Paths.path_fix(path)

    @classmethod
    def pathsFromScene(cls, pgs) -> List[str]:
        paths = []
        for pg in pgs:
            path = Paths.path_fix(pg.name)
            if os.path.exists(path):
                paths.append(path)
            else:
                print("Skip non-existent path:", path)
        return paths

    @classmethod
    def toScene(cls, scn):
        data = ObjectDict(Settings)
        scn_data = ObjectDict(scn)

        for prop, key in SceneStatic.SceneTable.items():
            if not(scn_data.exists(prop) and key in data.keys()):
                print("MIS", prop, key)
                continue
            try:
                scn_data[prop] = data.get(key)
            except TypeError:
                print("Type Error", prop, key)

        SceneStatic.pathsToScene(data['contentDirs'], scn.DazContentDirs)
        SceneStatic.pathsToScene(data['mdlDirs'], scn.DazMDLDirs)
        SceneStatic.pathsToScene(data['cloudDirs'], scn.DazCloudDirs)

        scn_data["DazErrorPath"] = Paths.path_fix(data.get('errorPath'))

    @classmethod
    def readSettingsDirs(cls, prefix: str, settings: Dict[str, Any]) -> List:
        paths = []

        n = len(prefix)
        pathlist = [(key, path)
                    for key, path in settings.items() if key[0:n] == prefix]
        pathlist.sort()

        for _prop, path in pathlist:
            path = Paths.path_fix(path)

            if not os.path.exists(path):
                print("No such path:", path)
                continue

            paths.append(path)

        return paths

    @classmethod
    def eliminateDuplicates(cls, data: Dict[str, Any]):
        content = dict([(path, True) for path in data['contentDirs']])
        mdl = dict([(path, True) for path in data['mdlDirs']])
        cloud = dict([(path, True) for path in data['cloudDirs']])

        for path in data['mdlDirs'] + data['cloudDirs']:
            if path in content.keys():
                print("Remove duplicate path: %s" % path)
                del content[path]

        data['contentDirs'] = list(content.keys())
        data['mdlDirs'] = list(mdl.keys())
        data['cloudDirs'] = list(cloud.keys())

    @classmethod
    def fromScene(cls, scn):
        out = {}
        scn_data = ObjectDict(scn)

        for prop, key in SceneStatic.SceneTable.items():
            if scn_data.exists(prop):
                out[key] = scn_data.get(prop)
            else:
                print("MIS", prop, key)

        out['contentDirs'] = SceneStatic.pathsFromScene(scn.DazContentDirs)
        out['mdlDirs'] = SceneStatic.pathsFromScene(scn.DazMDLDirs)
        out['cloudDirs'] = SceneStatic.pathsFromScene(scn.DazCloudDirs)
        out['errorPath'] = Paths.path_fix(getattr(scn, "DazErrorPath"))
        cls.eliminateDuplicates(out)
        Settings.deserialize(out)

    @classmethod
    def readDazPaths(cls, struct: Dict[str, Any], btn):
        data = ObjectDict(Settings)
        data['contentDirs'] = []
        if btn.useContent:
            data['contentDirs'] = cls.readAutoDirs("content", struct)
            data['contentDirs'] += cls.readAutoDirs("builtin_content", struct)

        data['mdlDirs'] = []
        if btn.useMDL:
            data['mdlDirs'] = cls.readAutoDirs("builtin_mdl", struct)
            data['mdlDirs'] += cls.readAutoDirs("mdl_dirs", struct)

        data['cloudDirs'] = []
        if btn.useCloud:
            data['cloudDirs'] = cls.readCloudDirs("cloud_content", struct)

        cls.eliminateDuplicates(data)
