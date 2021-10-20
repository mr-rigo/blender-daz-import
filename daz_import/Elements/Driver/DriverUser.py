import bpy
from bpy.props import BoolProperty

from daz_import.Lib import Registrar
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.Settings import Settings
from daz_import.Lib.Errors import DazOperator, IsArmature,\
    IsObject, DazError
from daz_import.Lib.Utility import Props, PropsStatic,\
    UtilityBoneStatic, UtilityStatic, Updating
from .Static import *


class DriverUser:
    def __init__(self):
        self.tmp = None

    def createTmp(self):
        if self.tmp is None:
            self.tmp = bpy.data.objects.new("Tmp", None)

    def deleteTmp(self):
        if self.tmp:
            bpy.data.objects.remove(self.tmp)
            del self.tmp
            self.tmp = None

    def getTmpDriver(self, idx):
        self.tmp.driver_remove("rotation_euler", idx)
        fcu = self.tmp.driver_add("rotation_euler", idx)
        removeModifiers(fcu)
        return fcu

    def clearTmpDriver(self, idx):
        self.tmp.driver_remove("rotation_euler", idx)

    def getArrayIndex(self, fcu):
        if (not fcu.data_path or
            fcu.data_path[-1] == "]" or
                fcu.data_path.endswith("value")):
            return -1
        else:
            return fcu.array_index

    def removeDriver(self, rna, path, idx=-1):
        if idx < 0:
            rna.driver_remove(path)
        else:
            rna.driver_remove(path, idx)

    def copyDriver(self, fcu, rna, old=None, new=None, assoc=None):
        channel = fcu.data_path
        idx = self.getArrayIndex(fcu)
        fcu2 = self.getTmpDriver(0)
        self.copyFcurve(fcu, fcu2)
        if old or assoc:
            self.setId(fcu2, old, new, assoc)
        if rna.animation_data is None:
            if idx > 0:
                rna.driver_add(channel, idx)
            else:
                rna.driver_add(channel)
        if idx >= 0:
            rna.driver_remove(channel, idx)
        else:
            rna.driver_remove(channel)
        fcu3 = rna.animation_data.drivers.from_existing(src_driver=fcu2)
        fcu3.data_path = channel
        if idx >= 0:
            fcu3.array_index = idx
        removeModifiers(fcu3)
        self.clearTmpDriver(0)
        return fcu3

    def copyFcurve(self, fcu1, fcu2):
        fcu2.driver.type = fcu1.driver.type
        fcu2.driver.use_self = fcu1.driver.use_self
        fcu2.driver.expression = fcu1.driver.expression
        for var1 in fcu1.driver.variables:
            var2 = fcu2.driver.variables.new()
            self.copyVariable(var1, var2)

    def copyVariable(self, var1, var2):
        var2.type = var1.type
        var2.name = var1.name
        for n, trg1 in enumerate(var1.targets):
            if n > 1:
                trg2 = var2.targets.add()
            else:
                trg2 = var2.targets[0]
            if trg1.id_type != 'OBJECT':
                trg2.id_type = trg1.id_type
            trg2.id = trg1.id
            trg2.bone_target = trg1.bone_target
            trg2.data_path = trg1.data_path
            trg2.transform_type = trg1.transform_type
            trg2.transform_space = trg1.transform_space

    def setId(self, fcu, old, new, assoc=None):
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.id_type == 'OBJECT' and trg.id == old:
                    trg.id = new
                elif trg.id_type == 'ARMATURE' and trg.id == old.data:
                    trg.id = new.data
                if assoc and var.type == 'TRANSFORMS':
                    trg.bone_target = assoc[trg.bone_target]

    def getTargetBones(self, fcu):
        targets = {}
        for var in fcu.driver.variables:
            if var.type == 'TRANSFORMS':
                for trg in var.targets:
                    targets[trg.bone_target] = True
        return targets.keys()

    def getVarBoneTargets(self, fcu):
        vstruct = {}
        bstruct = {}
        for var in fcu.driver.variables:
            if var.type == 'TRANSFORMS':
                for trg in var.targets:
                    bstruct[var.name] = (trg.bone_target, var)
            elif var.type == 'SINGLE_PROP':
                for trg in var.targets:
                    vstruct[var.name] = (trg.data_path, var)
        vtargets = [(key, data[0], data[1]) for key, data in vstruct.items()]
        btargets = [(key, data[0], data[1]) for key, data in bstruct.items()]
        vtargets.sort()
        btargets.sort()
        return vtargets, btargets

    def getDriverTargets(self, fcu):
        return [var.targets[0].data_path for var in fcu.driver.variables]

    def setBoneTarget(self, fcu, bname):
        for var in fcu.driver.variables:
            for trg in var.targets:
                if trg.bone_target:
                    trg.bone_target = bname

    def getShapekeyDrivers(self, ob, drivers={}):
        if (ob.data.shape_keys is None or
                ob.data.shape_keys.animation_data is None):
            #print(ob, ob.data.shape_keys, ob.data.shape_keys.animation_data)
            return drivers

        for fcu in ob.data.shape_keys.animation_data.drivers:
            words = fcu.data_path.split('"')
            if (words[0] == "key_blocks[" and
                len(words) == 3 and
                    words[2] == "].value"):
                drivers[words[1]] = fcu

        return drivers

    def copyShapeKeyDrivers(self, ob, drivers):
        if not drivers:
            return
        skeys = ob.data.shape_keys
        self.createTmp()
        try:
            for sname, fcu in drivers.items():
                if (getShapekeyDriver(skeys, sname) or
                        sname not in skeys.key_blocks.keys()):
                    continue
                #skey = skeys.key_blocks[sname]
                self.copyDriver(fcu, skeys)
        finally:
            self.deleteTmp()

    def copyDrivers(self, src, trg, old, new):
        if src.animation_data is None:
            return
        self.createTmp()
        try:
            for fcu in src.animation_data.drivers:
                self.copyDriver(fcu, trg, old, new)
        finally:
            self.deleteTmp()
