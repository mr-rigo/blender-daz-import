import os
import bpy
from daz_import.driver import DriverUser
from daz_import.Lib.Errors import ErrorsStatic, DazError
from daz_import.Lib.Files.Json import Json
from urllib.parse import unquote
from daz_import.Collection import Collection, DazPath
from daz_import.utils import *
from .static import *
from daz_import.Elements.Assets.FileAsset import FileAsset


class LoadMorph(DriverUser):
    morphset = None
    usePropDrivers = True
    treatHD = 'ERROR'

    def __init__(self, rig, mesh):
        self.rig = rig
        self.mesh = mesh
        self.initAmt()
        self.mult = []
        self.mults = {}

    def getAdjustProp(self):
        return None

    def addToMorphSet(self, prop, asset, hidden):
        return

    def initAmt(self):
        if self.rig:
            self.amt = self.rig.data
        else:
            self.amt = None

    def loadAllMorphs(self, namepaths):
        DriverUser.__init__(self)
        self.alias = {}
        self.loaded = []
        self.referred = {}
        self.primary = {}
        self.visible = {}
        self.erc = False
        self.drivers = {}
        self.shapekeys = {}
        self.mults = {}
        self.sumdrivers = {}
        self.restdrivers = {}
        self.iked = []
        self.origRestored = []
        self.initAmt()
        self.getAdjustedBones()

        print("Making morphs")
        self.makeAllMorphs(namepaths, True)
        if self.loadMissing:
            print("Making missing morphs")
            bodypart = namepaths[0][2]
            self.makeMissingMorphs(bodypart)
        else:
            print("Cannot make missing morphs for this type")
        if self.rig:
            self.createTmp()
            try:
                self.buildDrivers()
                self.buildSumDrivers()
                self.buildRestDrivers()
                self.correctScaleParents()
            finally:
                self.deleteTmp()
            self.rig.update_tag()
            if self.mesh:
                self.mesh.update_tag()
        if self.origRestored:
            from daz_import.geometry import clearMeshProps
            for ob in self.origRestored:
                clearMeshProps(ob.data)
            self.origRestored = []

    # ------------------------------------------------------------------
    #   Make all morphs
    # ------------------------------------------------------------------

    def makeAllMorphs(self, namepaths, force):
        namepaths.sort()
        idx = 0
        npaths = len(namepaths)
        for name, path, bodypart in namepaths:
            Progress.show(idx, npaths)
            idx += 1
            char = self.makeSingleMorph(name, path, bodypart, force)
            print(char, name)

    # ------------------------------------------------------------------
    #   First pass: collect data
    # ------------------------------------------------------------------

    def makeSingleMorph(self, name, filepath, bodypart, force):        
        asset: FileAsset = FileAsset.create_by_url(filepath)
        fileref = self.getFileRef(filepath)

        self.loaded.append(fileref)

        if not force and self.alreadyLoaded(asset):
            return " ."

        if not asset or not asset.is_instense('ChannelAsset'):
            return " -"
        elif asset.is_instense('Alias'):
            return " _"

        skey, ok = self.buildShape(asset, bodypart)

        if not ok:
            return " #"
        elif self.rig:
            self.makeFormulas(asset, skey)

        aliaspath = self.getAliasFile(filepath)
        aliases = {}

        if aliaspath is not None:
            aliases = self.loadAlias(aliaspath)

        self.addUrl(asset, aliases, filepath, bodypart)

        return " *"

    def alreadyLoaded(self, asset):
        raw = asset.getName()
        final = PropsStatic.final(raw)
        if self.rig and raw in self.rig.keys() and final in self.amt.keys():
            self.adjustMults(raw, final)
            return True
        return False

    def getAliasFile(self, filepath):
        folder = os.path.dirname(filepath)
        file1 = os.path.basename(filepath)

        for file in os.listdir(folder):
            if (file[0:5] == "alias" and
                    file.endswith(file1)):
                return os.path.join(folder, file)
        return None

    def loadAlias(self, filepath: str) -> dict:
        struct = Json.load(filepath)
        aliases = {}

        if self.rig is None:
            return aliases
        elif "modifier_library" in struct.keys():
            for mod in struct["modifier_library"]:
                if "channel" in mod.keys():
                    channel = mod["channel"]
                    if ("type" in channel.keys() and
                            channel["type"] == "alias"):
                        alias = channel["name"]
                        prop = channel["target_channel"].rsplit(
                            '#')[-1].split("?")[0]
                        if alias != prop:
                            self.setAlias(prop, alias)
                            aliases[alias] = prop
                            if "label" in channel.keys():
                                self.setLabel(prop, channel["label"])
        return aliases

    def setAlias(self, prop, alias):
        pgs = self.rig.DazAlias

        if alias in pgs.keys():
            pg = pgs[alias]
            print(" == %s %s %s" % (prop, alias, pg.s))
            return
        else:
            pg = pgs.add()
            pg.name = alias
            print(" = %s %s" % (prop, alias))

        pg.s = prop

    def setLabel(self, prop, label):
        pgs = self.findPropGroup(prop)
        if pgs and prop in pgs.keys():
            item = pgs[prop]
            item.text = label

    def buildShape(self, asset, bodypart, useBuild=True):
        from daz_import.Elements.Modifier import Morph
        from daz_import.driver import makePropDriver
        from daz_import.hdmorphs import addSkeyToUrls
        if not (isinstance(asset, Morph) and
                self.mesh and
                asset.deltas):
            return None, True
        useBuild = True
        nverts = len(self.mesh.data.vertices)

        if Settings.useModifiedMesh and self.modded:
            from daz_import.geometry import restoreOrigVerts
            hasOrig, restored = restoreOrigVerts(self.mesh, asset.vertex_count)
            if restored and self.mesh not in self.origRestored:
                self.origRestored.append(self.mesh)
            if hasOrig:
                finger = self.mesh.data.DazFingerPrint
                nverts = int(finger.split("-")[0])

        if asset.vertex_count < 0:
            print("Vertex count == %d" % asset.vertex_count)
        elif asset.vertex_count != nverts:
            msg = ("Vertex count mismatch: %d != %d" %
                   (asset.vertex_count, len(self.mesh.data.vertices)))
            if Settings.verbosity > 2:
                print(msg)
            if asset.hd_url:
                if self.treatHD == 'CREATE':
                    useBuild = False
                elif self.treatHD == 'ACTIVE':
                    skey = self.getActiveShape(asset)
                else:
                    ErrorsStatic.report(msg, trigger=(2, 3))
                    return None, False
            else:
                ErrorsStatic.report(msg, trigger=(2, 3))
                return None, False
        if not asset.rna:
            asset.buildMorph(self.mesh, useBuild=useBuild)
        skey, _, sname = asset.rna
        if skey:
            prop = unquote(skey.name)
            self.alias[prop] = skey.name
            skey.name = prop
            self.shapekeys[prop] = skey
            addSkeyToUrls(self.mesh, asset, skey)
            if self.rig:
                final = self.addNewProp(prop)
                adj = self.getGlobalAdjuster()
                self.adjustShapekey(skey, adj, final)
                if adj:
                    makePropDriver(PropsStatic.ref(adj), skey,
                                   "slider_max", self.rig, "x")
            pgs = self.mesh.data.DazBodyPart
            if prop in pgs.keys():
                item = pgs[prop]
            else:
                item = pgs.add()
                item.name = prop
            item.s = bodypart
            return skey, True
        else:
            return None, True

    def makeFormulas(self, asset, skey):
        from daz_import.Elements.Formula import Formula
        prop = asset.getName()
        
        if prop != asset.name:
            self.setAlias(asset.name, prop)
        
        self.addNewProp(prop, asset, skey)
        
        if not isinstance(asset, Formula):
            return
        
        exprs = asset.formulaData.evalFormulas(self.rig, self.mesh)

        for output, data in exprs.items():
            for key, data1 in data.items():
                if key == "*fileref":
                    ref, channel = data1
                    if channel == "value" and len(ref) > 3:
                        self.referred[ref.lower()] = True
                    continue
                for idx, expr in data1.items():
                    if key == "value":
                        self.makeValueFormula(output, expr)
                    elif key == "rotation":
                        self.makeRotFormula(output, idx, expr)
                    elif key == "translation":
                        self.makeTransFormula(output, idx, expr)
                    elif key == "scale":
                        self.makeScaleFormula(output, idx, expr)
                    elif key == "center_point":
                        self.erc = True
                        if Settings.useERC:
                            self.makeCenterFormula(output, idx, expr)
                    elif key == "end_point":
                        self.erc = True

    def adjustProp(self, adj, prop, final):
        from daz_import.driver import setFloatProp, removeModifiers
        if adj not in self.rig.keys():
            self.addNewProp(adj)
            setFloatProp(self.rig, adj, 1.0, 0.0, 1000.0)
        adjprop = ("%s(adj)" % prop)
        self.amt[adjprop] = 0.0
        channel = PropsStatic.ref(adjprop)
        self.amt.driver_remove(channel)
        fcu = self.amt.driver_add(channel)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        fcu.driver.expression = "a*b"
        self.addPathVar(fcu, "a", self.amt, PropsStatic.ref(final))
        self.addPathVar(fcu, "b", self.rig, PropsStatic.ref(adj))
        return adjprop

    def getLocalAdjuster(self):
        if Settings.useAdjusters not in ['TYPE', 'BOTH']:
            return None

        return self.getAdjuster(self.getAdjustProp())

    def getGlobalAdjuster(self):
        if Settings.useAdjusters not in ['STRENGTH', 'BOTH']:
            return None
        adj = "Adjust Morph Strength"
        return self.getAdjuster(adj)

    def getAdjuster(self, adj):
        from daz_import.driver import setFloatProp, makePropDriver
        if adj and adj not in self.rig.keys():
            final = PropsStatic.final(adj)
            setFloatProp(self.rig, adj, 1.0, 0.0, 1000.0)
            setFloatProp(self.amt, final, 1.0, 0.0, 1000.0)
            makePropDriver(PropsStatic.ref(adj), self.amt,
                           PropsStatic.ref(final), self.rig, "x")
        return adj

    def adjustShapekey(self, skey, adj, final):
        from daz_import.driver import removeModifiers
        skey.driver_remove("value")
        fcu = skey.driver_add("value")
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        self.addPathVar(fcu, "a", self.amt, PropsStatic.ref(final))
        if adj:
            self.addPathVar(fcu, "L", self.rig, PropsStatic.ref(adj))
            fcu.driver.expression = "L*a"
        else:
            fcu.driver.expression = "a"

    def getAdjustedBones(self):
        if Settings.useAdjusters not in ['STRENGTH', 'BOTH']:
            return
        self.adjustedBones = {}
        if self.rig and self.rig.animation_data:
            for fcu in self.rig.animation_data.drivers:
                words = fcu.data_path.split('"')
                if (len(words) > 3 and
                        words[3] == "Limit Location"):
                    self.adjustedBones[words[1]] = True

    def adjustTranslation(self, adj, pb, string, vars):
        if pb is None or Settings.useAdjusters not in ['STRENGTH', 'BOTH']:
            return string
        from daz_import.driver import makePropDriver
        string = "L*(%s)" % string
        vars.append(("L", PropsStatic.final(adj)))
        if pb.name in self.adjustedBones.keys():
            return string
        cns = BlenderStatic.constraint(pb, 'LIMIT_LOCATION')
        if cns:
            self.adjustedBones[pb.name] = True
            for channel in ["min_x", "min_y", "min_z", "max_x", "max_y", "max_z"]:
                factor = getattr(cns, channel)
                makePropDriver(PropsStatic.ref(adj), cns, channel,
                               self.rig, "%g*x" % factor)
        return string

    def getFileRef(self, filepath):
        filepath = filepath.replace("\\", "/").lower()
        words = filepath.rsplit("/data/", 1)
        if len(words) == 2:
            return "/data/%s" % words[1]
        elif filepath[1:3] == ":/":
            return filepath
        else:
            msg = ('Did not find file:\n"%s"' % filepath)
            raise DazError(msg)

    def addNewProp(self, raw, asset=None, skey=None):
        from daz_import.driver import setBoolProp
        from daz_import.Elements.Morph import setActivated
        final = PropsStatic.final(raw)
        if raw not in self.drivers.keys():
            self.drivers[raw] = []
            self.visible[raw] = False
            self.primary[raw] = False
        if asset:
            visible = (asset.visible or Settings.useMakeHiddenSliders)
            self.visible[raw] = visible
            self.primary[raw] = True
            if skey and not visible:
                return final
            elif asset.type == "bool":
                setBoolProp(self.rig, raw, asset.value)
                setBoolProp(self.amt, final, asset.value)
            elif asset.type == "float":
                self.setFloatLimits(
                    self.rig, raw, Settings.sliderLimits, asset, skey)
                self.setFloatLimits(
                    self.amt, final, Settings.finalLimits, asset, skey)
            elif asset.type == "int":
                self.rig[raw] = 0
                self.amt[final] = 0
            else:
                self.setFloatLimits(
                    self.rig, raw, Settings.sliderLimits, asset, skey)
                self.setFloatLimits(
                    self.amt, final, Settings.finalLimits, asset, skey)
                ErrorsStatic.report("BUG: Unknown asset type: %s.\nAsset: %s" % (
                    asset.type, asset), trigger=(2, 3))
            if visible:
                setActivated(self.rig, raw, True)
                self.addToMorphSet(raw, asset, False)
        return final

    def setFloatLimits(self, rna, prop, limits, asset, skey):
        from daz_import.driver import setFloatProp
        if limits == 'DAZ' or "jcm" in prop.lower():
            min = Settings.morphMultiplier * asset.min
            max = Settings.morphMultiplier * asset.max
            setFloatProp(rna, prop, 0.0, min, max)
            if skey:
                skey.slider_min = min
                skey.slider_max = max
        elif limits == 'CUSTOM':
            setFloatProp(rna, prop, 0.0, Settings.customMin, Settings.customMax)
            if skey:
                skey.slider_min = Settings.customMin
                skey.slider_max = Settings.customMax
        else:
            setFloatProp(rna, prop, 0.0, None, None)
            if skey:
                skey.slider_min = 0.0
                skey.slider_max = 1.0

    def makeValueFormula(self, output, expr):
        if expr["prop"]:
            self.addNewProp(output)
            prop = expr["prop"]
            self.drivers[output].append(("PROP", prop, expr["factor"]))
        if expr["mult"]:
            mult = expr["mult"]
            if output not in self.mults.keys():
                self.mults[output] = []
            self.mults[output].append(mult)
            self.addNewProp(mult)
        if expr["bone"]:
            bname = self.getRealBone(expr["bone"])
            if bname:
                if output not in self.drivers.keys():
                    self.drivers[output] = []
                self.drivers[output].append(("BONE", bname, expr))
            else:
                print("Missing bone (makeValueFormula):", expr["bone"])

    def getRealBone(self, bname):
        from daz_import.Elements.Bone import getTargetName
        nname = getTargetName(bname, self.rig)
        return nname

    def getDrivenBone(self, bname):
        bname = self.getRealBone(bname)
        if bname:
            dname = UtilityBoneStatic.drv_bone(bname)
            if dname in self.rig.pose.bones.keys():
                return dname
        return bname

    def getBoneData(self, bname, expr):
        from daz_import.Elements.Transform import Transform
        bname = self.getDrivenBone(bname)
        if bname is None:
            return
        pb = self.rig.pose.bones[bname]
        factor = expr["factor"]
        if "points" in expr.keys():
            factor = self.cheatSplineTCB(expr["points"], factor)
        raw = expr["prop"]
        final = self.addNewProp(raw)
        tfm = Transform()
        return tfm, pb, final, factor

    def cheatSplineTCB(self, points, factor):
        x0 = y0 = None
        for n, point in enumerate(points):
            x, y = point[0:2]
            if x == 0 and y == 0:
                x0 = x
                y0 = y
                n0 = n
                break
        if x0 is None:
            return factor
        if n0 == 0:
            x1, y1 = points[-1][0:2]
        else:
            x1, y1 = points[0][0:2]
        factor = (y1-y0)/(x1-x0)
        return factor

    def makeRotFormula(self, bname, idx, expr):
        tfm, pb, prop, factor = self.getBoneData(bname, expr)
        tfm.setRot(factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)

    def makeTransFormula(self, bname, idx, expr):
        tfm, pb, prop, factor = self.getBoneData(bname, expr)
        tfm.setTrans(factor, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)

    def makeScaleFormula(self, bname, idx, expr):
        tfm, pb, prop, factor = self.getBoneData(bname, expr)
        tfm.setScale(factor, True, prop, index=idx)
        self.addPoseboneDriver(pb, tfm)

    def makeCenterFormula(self, bname, idx, expr):
        _tfm, pb, prop, factor = self.getBoneData(bname, expr)
        if "HdOffset" not in pb.keys():
            pb.HdOffset = VectorStatic.zero
        vec = Vector((0, 0, 0))
        vec[idx] = factor
        self.setFcurves(pb, vec, prop, "HdOffset", "pose")

    # -------------------------------------------------------------
    #   Add posebone driver
    # -------------------------------------------------------------

    def addPoseboneDriver(self, pb, tfm):
        from daz_import.Elements.Node import getBoneMatrix
        mat = getBoneMatrix(tfm, pb)
        loc, quat, scale = mat.decompose()
        success = False
        if (tfm.transProp and loc.length > 0.01*self.rig.DazScale):
            self.setFcurves(pb, loc, tfm.transProp, "location")
            success = True
        if tfm.rotProp:
            if Vector(quat.to_euler()).length < 1e-4:
                pass
            elif pb.rotation_mode == 'QUATERNION':
                quat[0] -= 1
                self.setFcurves(pb, quat, tfm.rotProp, "rotation_quaternion")
                success = True
            else:
                euler = mat.to_euler(pb.rotation_mode)
                self.setFcurves(pb, euler, tfm.rotProp, "rotation_euler")
                success = True
        if (tfm.scaleProp and scale.length > 1e-4):
            self.setFcurves(pb, scale-VectorStatic.one, tfm.scaleProp, "scale")
            success = True
        elif tfm.generalProp:
            self.setFcurves(pb, scale-VectorStatic.one,
                            tfm.generalProp, "scale")
            success = True
        return success

    def setFcurves(self, pb, vec, prop, channel, pose="pose"):
        def getBoneFcurves(pb, channel):
            path = '%s.bones["%s"].%s' % (pose, pb.name, channel)
            fcurves = {}
            if self.rig.animation_data:
                for fcu in self.rig.animation_data.drivers:
                    if path == fcu.data_path:
                        fcurves[fcu.array_index] = fcu
            return fcurves

        fcurves = getBoneFcurves(pb, channel)
        for idx, factor in self.getFactors(vec):
            if idx in fcurves.keys():
                fcu = fcurves[idx]
            else:
                fcu = None
            bname, drivers = self.findSumDriver(
                pb, channel, idx, (pb, fcu, {}))
            drivers[prop] = factor

    def getFactors(self, vec):
        maxfactor = max([abs(factor) for factor in vec])
        return [(idx, factor) for idx, factor in enumerate(vec) if abs(factor) > 0.01*maxfactor]

    def findSumDriver(self, pb, channel, idx, data):
        bname = pb.name
        if UtilityBoneStatic.drv_bone(bname) in self.rig.data.bones.keys():
            bname = UtilityBoneStatic.drv_bone(bname)
        if bname not in self.sumdrivers.keys():
            self.sumdrivers[bname] = {}
        if channel not in self.sumdrivers[bname].keys():
            self.sumdrivers[bname][channel] = {}
        if idx not in self.sumdrivers[bname][channel].keys():
            self.sumdrivers[bname][channel][idx] = data
        return bname, self.sumdrivers[bname][channel][idx][2]

    def clearProp(self, pgs, prop, idx):
        for n, pg in enumerate(pgs):
            if pg.name == prop and pg.index == idx:
                pgs.remove(n)
                return

    # ------------------------------------------------------------------
    #   Second pass: Load missing morphs
    # ------------------------------------------------------------------

    def makeMissingMorphs(self, bodypart):
        for fileref in self.loaded:
            self.referred[fileref] = False
        morphset = self.morphset
        namepaths = []
        groupedpaths, morphfiles = self.setupMorphGroups()
        for ref, unloaded in self.referred.items():
            if unloaded:
                path = Collection.path(ref)
                if not path:
                    continue

                name = ref.rsplit("/", 1)[-1]
                data = (name, path, bodypart)
                morphset = self.getPathMorphSet(path, morphfiles)

                if morphset:
                    groupedpaths[morphset].append(data)
                else:
                    namepaths.append(data)
        if namepaths:
            self.makeAllMorphs(namepaths, False)
        for mset, namepaths in groupedpaths.items():
            if namepaths:
                self.morphset = mset
                self.makeAllMorphs(namepaths, False)
        self.morphset = morphset

    def setupMorphGroups(self):
        from daz_import.Elements.Morph import getMorphPaths
        if self.char is None:
            return {}, {}
        morphrefs = {}
        groupedpaths = {}
        for morphset, paths in getMorphPaths(self.char).items():
            groupedpaths[morphset] = []
            morphrefs[morphset] = [self.getFileRef(path) for path in paths]
        return groupedpaths, morphrefs

    def getPathMorphSet(self, path, morphrefs):
        ref = self.getFileRef(path)
        for morphset, refs in morphrefs.items():
            if ref in refs:
                return morphset
        return None

    # ------------------------------------------------------------------
    #   Third pass: Build the drivers
    # ------------------------------------------------------------------

    def buildDrivers(self):
        print("Building drivers")
        for output, drivers in self.drivers.items():
            if drivers:
                if self.isDriverType('BONE', drivers):
                    for dtype, bname, expr in drivers:
                        if dtype == 'BONE':
                            self.buildBoneDriver(output, bname, expr, False)
                elif self.isDriverType('PROP', drivers):
                    self.buildPropDriver(output, drivers)
            else:
                self.buildPropDriver(output, drivers)

    def isDriverType(self, dtype, drivers):
        for driver in drivers:
            if driver[0] == dtype:
                return True
        return False

    def buildPropDriver(self, raw, drivers):
        from daz_import.driver import getRnaDriver, Variable, removeModifiers
        isJcm = ("jcm" in raw.lower() and
                 "ejcm" not in raw.lower() and
                 raw[0:6] != "JCMs O")
        rna, channel = self.getDrivenChannel(raw)
        bvars = []
        vvars = {}
        string = ""
        fcu0 = getRnaDriver(rna, channel, None)
        if fcu0 and fcu0.driver.type == 'SCRIPTED':
            if not self.primary[raw]:
                self.extendPropDriver(fcu0, raw, drivers)
                return
            vtargets, btargets = self.getVarBoneTargets(fcu0)
            if isJcm:
                string = fcu0.driver.expression
            elif btargets:
                varname = btargets[-1][0]
                string = self.extractBoneExpression(
                    fcu0.driver.expression, varname)
            for _, _, var0 in btargets:
                bvars.append(Variable(var0))
            for vname, _, var0 in vtargets:
                vvars[vname] = Variable(var0)
        rna.driver_remove(channel)
        fcu = rna.driver_add(channel)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        for bvar in bvars:
            var = fcu.driver.variables.new()
            bvar.create(var)
        if isJcm and string:
            fcu.driver.expression = string
        else:
            ok = self.buildNewPropDriver(
                fcu, rna, channel, string, raw, drivers)
            if not ok:
                return
        self.addMissingVars(fcu, vvars)
        self.removeUnusedVars(fcu)

    def buildNewPropDriver(self, fcu, rna, channel, string, raw, drivers):
        varname = "a"
        if self.visible[raw] or not self.primary[raw]:
            string += varname
            self.addPathVar(fcu, varname, self.rig, PropsStatic.ref(raw))
            if raw not in self.rig.keys():
                self.rig[raw] = 0.0
        string, rdrivers = self.addDriverVars(
            fcu, string, varname, raw, drivers)
        if not string:
            print("Empty string: %s" % raw)
            rna.driver_remove(channel)
            return False
        if self.getMultipliers(raw):
            string = self.multiplyMults(fcu, string)
        fcu.driver.expression = string
        if rdrivers:
            self.extendPropDriver(fcu, raw, rdrivers)
        return True

    def extractBoneExpression(self, string, varname):
        string = string.split("(", 1)[-1]
        mult = string.split(varname, 1)[0]
        if mult == "0":
            mult = "0*"
        return "%s%s+" % (mult, varname)

    def addDriverVars(self, fcu, string, varname, raw, drivers):
        def multiply(factor, varname):
            if factor == 1:
                return "+%s" % varname
            elif factor == -1:
                return "-%s" % varname
            else:
                return "%+g*%s" % (factor, varname)

        channels = [var.targets[0].data_path for var in fcu.driver.variables]
        for dtype, subraw, factor in drivers[0:MAX_TERMS2]:
            if dtype != 'PROP':
                continue
            subfinal = PropsStatic.final(subraw)
            channel = PropsStatic.ref(subfinal)
            if channel in channels:
                continue
            varname = UtilityStatic.next_letter(varname)
            string += multiply(factor, varname)
            self.ensureExists(subraw, subfinal, 0.0)
            self.addPathVar(fcu, varname, self.amt, channel)
        if len(drivers) > MAX_TERMS2:
            return string, drivers[MAX_TERMS2:]
        else:
            return string, []

    def addMissingVars(self, fcu, vvars):
        vnames = [var.name for var in fcu.driver.variables]
        for vname, vvar in vvars.items():
            if vname not in vnames:
                var = fcu.driver.variables.new()
                vvar.create(var)

    def removeUnusedVars(self, fcu):
        for var in list(fcu.driver.variables):
            if var.name not in fcu.driver.expression:
                fcu.driver.variables.remove(var)

    def extendPropDriver(self, fcu, raw, drivers):
        string = fcu.driver.expression
        char = ""
        while string[-1] == ")":
            char += ")"
            string = string[:-1]
        if string[-1] == "R":
            rest = PropsStatic.rest(raw)
            self.addRestDrivers(rest, drivers)
            return
        else:
            string += "+R"
            rest = PropsStatic.rest(raw)
            self.amt[rest] = 0.0
            self.addPathVar(fcu, "R", self.amt, PropsStatic.ref(rest))
            self.addRestDrivers(rest, drivers)
        string += char
        if len(string) > MAX_EXPRESSION_SIZE:
            errtype = "Driving expressions too long for the following properties:"
            if errtype not in self.errors.keys():
                self.errors[errtype] = []
            self.errors[errtype].append(raw)
        else:
            fcu.driver.expression = string

    def addRestDrivers(self, rest, drivers):
        struct = self.restdrivers[rest] = {}
        for dtype, raw, factor in drivers:
            if dtype == 'PROP':
                struct[PropsStatic.final(raw)] = factor

    def addPathVar(self, fcu, varname, rna, path):
        from daz_import.driver import addDriverVar
        addDriverVar(fcu, varname, path, rna)

    def getDrivenChannel(self, raw):
        rna = self.amt
        final = PropsStatic.final(raw)
        self.ensureExists(raw, final, 0.0)
        channel = PropsStatic.ref(final)
        return rna, channel

    def getMultipliers(self, raw):
        adj = self.getLocalAdjuster()
        if adj:
            self.mult = [adj]
        else:
            self.mult = []
        if raw and raw in self.mults.keys():
            self.mult += self.mults[raw]
        return self.mult

    def multiplyMults(self, fcu, string):
        if self.mult:
            mstring = ""
            if len(string) == 0:
                ErrorsStatic.report(
                    "Trying to multiply empty string", trigger=(1, 1))
            elif len(string) > 1 and string[1] == '*' and string[0].isupper():
                varname = UtilityStatic.next_letter(string[0])
            else:
                varname = "M"
                string = "(%s)" % string
            targets = self.getDriverTargets(fcu)
            for mult in self.mult:
                multfinal = PropsStatic.final(mult)
                if PropsStatic.ref(multfinal) not in targets:
                    mstring += "%s*" % varname
                    self.ensureExists(mult, multfinal, 1)
                    self.addPathVar(fcu, varname, self.amt,
                                    PropsStatic.ref(multfinal))
                    varname = UtilityStatic.next_letter(varname)
            return "%s%s" % (mstring, string)
        else:
            return string

    def adjustMults(self, raw, final):
        from daz_import.driver import getRnaDriver
        if self.getMultipliers(raw):
            fcu = getRnaDriver(self.amt, PropsStatic.ref(final))
        else:
            return
        if fcu:
            string = self.multiplyMults(fcu, fcu.driver.expression)
            fcu.driver.expression = string

    def ensureExists(self, raw, final, default):
        from daz_import.driver import removeModifiers
        if self.rig is None:
            return
        if raw not in self.rig.keys():
            self.rig[raw] = default
        if final not in self.amt.keys():
            self.amt[final] = default
            fcu = self.amt.driver_add(PropsStatic.ref(final))
            fcu.driver.type = 'SCRIPTED'
            removeModifiers(fcu)
            fcu.driver.expression = "a"
            self.addPathVar(fcu, "a", self.rig, PropsStatic.ref(raw))

    def buildBoneDriver(self, raw, bname, expr, keep):
        def getSplinePoints(expr, pb, comp):
            points = expr["points"]
            n = len(points)
            if (points[0][0] > points[n-1][0]):
                points.reverse()

            diff = points[n-1][0] - points[0][0]
            uvec = getBoneVector(unit/diff, comp, pb)
            xys = []
            for k in range(n):
                x = points[k][0]/diff
                y = points[k][1]
                xys.append((x, y))
            return uvec, xys

        self.mult = []
        if raw in self.mults.keys():
            self.mult = self.mults[raw]

        pb = self.rig.pose.bones[bname]
        rna, channel = self.getDrivenChannel(raw)
        # rna.driver_remove(channel)
        path = expr["path"]
        comp = expr["comp"]
        unit = getUnit(path, self.rig)
        if "points" in expr.keys():
            uvec, xys = getSplinePoints(expr, pb, comp)
            self.makeSplineBoneDriver(
                path, uvec, xys, rna, channel, -1, bname, keep)
        else:
            factor = expr["factor"]
            uvec = unit*getBoneVector(factor, comp, pb)
            bname2 = None
            uvec2 = None
            if expr["bone2"]:
                bname2 = self.getRealBone(expr["bone2"])
                if bname2:
                    pb2 = self.rig.pose.bones[bname2]
                    factor2 = expr["factor2"]
                    comp2 = expr["comp2"]
                    uvec2 = unit*getBoneVector(factor2, comp2, pb2)
            self.makeSimpleBoneDriver(
                path, uvec, rna, channel, -1, bname, keep, bname2, uvec2)

    # -------------------------------------------------------------
    #   Bone drivers
    # -------------------------------------------------------------

    def getVarData(self, uvec, bname, vname):
        vals = [(abs(x), n, x) for n, x in enumerate(uvec)]
        vals.sort()
        _, n, umax = vals[-1]
        if UtilityBoneStatic.drv_bone(bname) in self.rig.pose.bones.keys():
            vars = [(n, vname, UtilityBoneStatic.fin_bone(bname))]
        else:
            vars = [(n, vname, bname)]
        return vname, vars, umax

    def makeSimpleBoneDriver(self, channel, vec, rna, path, idx, bname, keep, bname2=None, vec2=None):
        var, vars, umax = self.getVarData(vec, bname, "A")
        string = getMult(umax, var)
        if bname2:
            var2, vars2, umax2 = self.getVarData(vec2, bname2, "B")
            string2 = getMult(umax2, var2)
            vars = vars + vars2
            string = "%s+%s" % (string, string2)
        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)

    def makeSplineBoneDriver(self, channel, uvec, points, rna, path, idx, bname, keep):
        # Only make spline for one component
        #[1 if x< -1.983 else -x-0.983 if x< -0.983  else 0 for x in [+0.988*A]][0]
        #1 if A< -1.983/0.988 else -0.988*A-0.983 if A< -0.983/0.988  else 0

        var, vars, umax = self.getVarData(uvec, bname, "A")
        lt = ("<" if umax > 0 else ">")

        n = len(points)
        xi, yi = points[0]
        string = "(%s if %s%s %s" % (getPrint(yi), var, lt, getPrint(xi/umax))
        for i in range(1, n):
            xj, yj = points[i]
            kij = (yj-yi)/(xj-xi)
            zs, zi = getSign((yi - kij*xi)/umax)
            zstring = ""
            if abs(zi) > 5e-4:
                zstring = ("%s%s" % (zs, getPrint(zi*umax)))
            string += (" else %s%s if %s%s %s " %
                       (getMult(kij*umax, var), zstring, var, lt, getPrint(xj/umax)))
            xi, yi = xj, yj
        string += " else %s)" % getPrint(yj)

        if len(string) > 254:
            msg = "String driver too long:\n"
            for n in range(5):
                msg += "%s         \n" % (string[30*n, 30*(n+1)])
            raise DazError(msg)

        self.makeBoneDriver(string, vars, channel, rna, path, idx, keep)

    def makeBoneDriver(self, string, vars, channel, rna, path, idx, keep):
        from daz_import.driver import addTransformVar, Variable, getRnaDriver, removeModifiers
        bvars = []
        vvars = {}
        if keep:
            fcu0 = getRnaDriver(rna, path, None)
            if fcu0 and fcu0.driver.type == 'SCRIPTED':
                vtargets, btargets = self.getVarBoneTargets(fcu0)
                if btargets:
                    varname = btargets[-1][0]
                    string0 = self.extractBoneExpression(
                        fcu0.driver.expression, varname)
                    for _, _, var0 in btargets:
                        bvars.append(Variable(var0))
                    nvars = []
                    vname = varname
                    for (n, varname, prop) in vars:
                        vname = UtilityStatic.next_letter(vname)
                        string = string.replace(varname, vname)
                        nvars.append((n, vname, prop))
                    vars = nvars
                    string = string0 + string
                for vname, _, var0 in vtargets:
                    vvars[vname] = Variable(var0)

        rna.driver_remove(path, idx)
        fcu = rna.driver_add(path, idx)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        for bvar in bvars:
            var = fcu.driver.variables.new()
            bvar.create(var)
        if Settings.useMakeHiddenSliders and isPath(path) and "u" not in vvars.keys():
            final = unPath(path)
            if UtilityBoneStatic.is_final(final):
                raw = PropsStatic.base(final)
                if string[0] == "-":
                    string = "u%s" % string
                else:
                    string = "u+%s" % string
                self.rig[raw] = 0.0
                self.addPathVar(fcu, "u", self.rig, PropsStatic.ref(raw))
                self.addToMorphSet(raw, None, True)
        adj = self.getLocalAdjuster()
        if adj:
            string = "K*(%s)" % string
            self.addPathVar(fcu, "K", self.rig, PropsStatic.ref(adj))
        fcu.driver.expression = string
        if channel == "rotation":
            ttypes = ["ROT_X", "ROT_Y", "ROT_Z"]
        elif channel == "translation":
            ttypes = ["LOC_X", "LOC_Y", "LOC_Z"]
        else:
            ErrorsStatic.report("Unknown channel: %s" %
                                channel, trigger=(2, 3))
        for j, vname, bname in vars:
            addTransformVar(fcu, vname, ttypes[j], self.rig, bname)
        self.addMissingVars(fcu, vvars)
        return fcu

    # ------------------------------------------------------------------
    #   Build sum drivers
    #   For Xin's non-python drivers
    # ------------------------------------------------------------------

    def buildSumDrivers(self):
        print("Building sum drivers")
        for bname, bdata in self.sumdrivers.items():
            for channel, cdata in bdata.items():
                for idx, idata in cdata.items():
                    pb, fcu0, drivers = idata
                    if pb in self.iked:
                        print("IKE", pb.name)
                        continue
                    pathids = {}
                    if channel == "rotation_quaternion" and idx == 0:
                        path = self.getConstant("Unity", 1.0, pb, idx)
                        pathids[path] = 'ARMATURE'
                    if fcu0:
                        if fcu0.driver.type == 'SUM':
                            self.recoverOldDrivers(fcu0, drivers)
                        elif channel == "scale":
                            fcu1 = self.findScaleSumDriver(fcu0)
                            if fcu1:
                                self.recoverOldDrivers(fcu1, drivers)
                        else:
                            path = self.getOrigo(fcu0, pb, channel, idx)
                            pathids[path] = 'ARMATURE'

                    pb.driver_remove(channel, idx)
                    prefix = self.getChannelPrefix(pb, channel, idx)
                    fcu = self.addSumDriver(prefix, drivers, pathids)
                    if channel == "scale":
                        self.ensureAnimData(self.amt)
                        sumfcu = self.amt.animation_data.drivers.from_existing(
                            src_driver=fcu)
                        prop = self.getFinalScaleProp(pb, idx)
                        self.amt[prop] = 0.0
                        sumfcu.data_path = PropsStatic.ref(prop)
                        self.addScaleDriver(pb, idx)
                    else:
                        self.ensureAnimData(self.rig)
                        sumfcu = self.rig.animation_data.drivers.from_existing(
                            src_driver=fcu)
                        sumfcu.data_path = 'pose.bones["%s"].%s' % (
                            pb.name, channel)
                        sumfcu.array_index = idx
                    self.clearTmpDriver(0)
            print(" + %s" % bname)

    def ensureAnimData(self, rna):
        if rna.animation_data is None:
            print("Make dummy driver for %s" % rna)
            rna["Dummy"] = 0.0
            fcu = rna.driver_add(PropsStatic.ref("Dummy"))

    def getChannelPrefix(self, pb, channel, idx):
        key = channel[0:3].capitalize()
        return "%s:%s:%s" % (pb.name, key, idx)

    def getFinalScaleProp(self, pb, idx):
        return "%s:Sca:%d" % (pb.name, idx)

    def getTermDriverName(self, prefix, n):
        return ("%s:%02d" % (prefix, n))

    def buildRestDrivers(self):
        from daz_import.driver import getRnaDriver
        if self.restdrivers:
            print("Building rest drivers")
        else:
            print("No rest drivers")
        for rest, drivers in self.restdrivers.items():
            self.amt[rest] = 0.0
            fcu = getRnaDriver(self.amt, PropsStatic.ref(rest))
            if fcu:
                self.recoverOldDrivers(fcu, drivers)
            self.amt.driver_remove(PropsStatic.ref(rest))
            fcu = self.addSumDriver(rest, drivers, {})
            self.ensureAnimData(self.amt)
            sumfcu = self.amt.animation_data.drivers.from_existing(
                src_driver=fcu)
            self.amt.driver_remove(rest)
            sumfcu.data_path = PropsStatic.ref(rest)
            self.clearTmpDriver(0)

    def findScaleSumDriver(self, fcu):
        from daz_import.driver import getRnaDriver
        for var in fcu.driver.variables:
            trg = var.targets[0]
            if trg.id_type == 'ARMATURE':
                return getRnaDriver(self.amt, trg.data_path)
        return None

    def recoverOldDrivers(self, sumfcu, drivers):
        from daz_import.driver import getRnaDriver
        for var in sumfcu.driver.variables:
            trg = var.targets[0]
            if trg.id_type == 'OBJECT':
                fcu2 = getRnaDriver(self.rig, trg.data_path)
            else:
                fcu2 = getRnaDriver(self.amt, trg.data_path)
            if fcu2:
                targets = {}
                for var2 in fcu2.driver.variables:
                    if var2.type == 'SINGLE_PROP':
                        trg2 = var2.targets[0]
                        targets[var2.name] = trg2
                string = fcu2.driver.expression
                while string and string[0] == "(":
                    string = string[1:-1]
                words = string.split("*")
                word1 = words[0]
                for word2 in words[1:]:
                    varname = word2[0]
                    if varname in targets.keys():
                        trg2 = targets[varname]
                        prop = unPath(trg2.data_path)
                        if prop not in drivers.keys():
                            try:
                                factor = float(word1)
                            except ValueError:
                                msg = ("BUG recoverOldDrivers: not a float\n" +
                                       "FCU2 %s %d" % (fcu2.data_path, fcu2.array_index) +
                                       "EXPR %s" % fcu2.driver.expression +
                                       "TARGETS %s" % list(targets.keys()))
                                ErrorsStatic.report(msg, trigger=(0, 0))
                            drivers[prop] = factor
                    word1 = word2[1:]

    def getOrigo(self, fcu0, pb, channel, idx):
        from daz_import.driver import Driver, removeModifiers
        prefix = self.getChannelPrefix(pb, channel, idx)
        prop = self.getTermDriverName(prefix, 0)
        self.amt[prop] = 0.0
        fcu = self.amt.driver_add(PropsStatic.ref(prop))
        driver = Driver(fcu0, True)
        driver.fill(fcu)
        removeModifiers(fcu)
        return PropsStatic.ref(prop)

    def getConstant(self, prop, value, pb, idx):
        from daz_import.driver import getRnaDriver, removeModifiers
        self.amt[prop] = value
        path = PropsStatic.ref(prop)
        if not getRnaDriver(self.amt, path):
            fcu = self.amt.driver_add(path)
            fcu.driver.type = 'SCRIPTED'
            removeModifiers(fcu)
            fcu.driver.expression = "%.1f" % value
        return path

    def addScaleDriver(self, pb, idx):
        from daz_import.driver import removeModifiers
        fcu = pb.driver_add("scale", idx)
        fcu.driver.type = 'SCRIPTED'
        removeModifiers(fcu)
        if pb.parent and UtilityBoneStatic.inherit_scale(pb):
            prop = self.getFinalScaleProp(pb, idx)
            fcu.driver.expression = "(1+a)/parscale"
            self.addPathVar(fcu, "a", self.amt, PropsStatic.ref(prop))
            self.correctScaleFcurve(fcu, pb, idx)
        else:
            fcu.driver.expression = "1+a"
            self.addPathVar(fcu, "a", self.amt, PropsStatic.ref(prop))
        return fcu

    def correctScaleFcurve(self, fcu, pb, idx):
        var = fcu.driver.variables.new()
        var.name = "parscale"
        var.type = 'TRANSFORMS'
        trg = var.targets[0]
        trg.id = self.rig
        trg.bone_target = pb.parent.name
        trg.transform_type = 'SCALE_%s' % chr(ord('X')+idx)
        trg.transform_space = 'LOCAL_SPACE'

    def correctScaleParents(self):
        from daz_import.driver import getDriver, removeModifiers
        for pb in self.rig.pose.bones:
            if UtilityBoneStatic.inherit_scale(pb) and pb.parent:
                parchannel = 'pose.bones["%s"].scale' % pb.parent.name
                channel = 'pose.bones["%s"].scale' % pb.name
                for idx in range(3):
                    if getDriver(self.rig, parchannel, idx):
                        fcu = getDriver(self.rig, channel, idx)
                        if fcu is None:
                            fcu = pb.driver_add("scale", idx)
                            fcu.driver.type = 'SCRIPTED'
                            removeModifiers(fcu)
                            fcu.driver.expression = "1/parscale"
                            self.correctScaleFcurve(fcu, pb, idx)

    def getBatches(self, drivers, prefix):
        batches = []
        string = ""
        nterms = 0
        varname = "a"
        vars = []
        adj = None
        pb = None
        bname = prefix[:-6]
        if prefix[-6:-1] == ":Loc:" and bname in self.rig.pose.bones.keys():
            adj = self.getGlobalAdjuster()
            pb = self.rig.pose.bones[bname]
        for final, factor in drivers.items():
            string += "%+.4g*%s" % (factor, varname)
            nterms += 1
            vars.append((varname, final))
            varname = UtilityStatic.next_letter(varname)
            if (nterms > MAX_TERMS or
                    len(string) > MAX_EXPR_LEN):
                string = self.adjustTranslation(adj, pb, string, vars)
                batches.append((string, vars))
                string = ""
                nterms = 0
                varname = "a"
                vars = []
        if vars:
            string = self.adjustTranslation(adj, pb, string, vars)
            batches.append((string, vars))
        return batches

    def addSumDriver(self, prefix, drivers, pathids):
        batches = self.getBatches(drivers, prefix)
        sumfcu = self.getTmpDriver(0)
        sumfcu.driver.type = 'SUM'
        for n, batch in enumerate(batches):
            string, vars = batch
            drvprop = self.getTermDriverName(prefix, n+1)
            self.amt[drvprop] = 0.0
            path = PropsStatic.ref(drvprop)
            self.amt.driver_remove(path)
            fcu = self.getTmpDriver(1)
            fcu.driver.type = 'SCRIPTED'
            fcu.driver.expression = string
            for varname, final in vars:
                self.addPathVar(fcu, varname, self.amt, PropsStatic.ref(final))
            pathids[path] = 'ARMATURE'
            self.ensureAnimData(self.amt)
            fcu2 = self.amt.animation_data.drivers.from_existing(
                src_driver=fcu)
            fcu2.data_path = path
            self.clearTmpDriver(1)
        for n, data in enumerate(pathids.items()):
            path, idtype = data
            if idtype == 'OBJECT':
                rna = self.rig
            else:
                rna = self.amt
            self.addPathVar(sumfcu, "t%.02d" % n, rna, path)
        return sumfcu

    def getActiveShape(self, asset):
        ob = self.mesh
        sname = asset.name
        skey = None
        if ob.data.shape_keys:
            skey = ob.data.shape_keys.key_blocks[ob.active_shape_key_index]
            skey.name = sname
        return skey, ob, sname
