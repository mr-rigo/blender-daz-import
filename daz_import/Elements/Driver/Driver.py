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


class Target:
    def __init__(self, trg):
        self.id_type = trg.id_type
        self.id = trg.id
        self.bone_target = trg.bone_target
        self.transform_type = trg.transform_type
        self.transform_space = trg.transform_space
        self.data_path = trg.data_path
        words = trg.data_path.split('"')
        if len(words) > 1:
            self.name = words[1]
        else:
            self.name = words[0]

    def create(self, trg, fixDrv=False):
        if self.id_type != 'OBJECT':
            trg.id_type = self.id_type
        trg.id = self.id
        trg.bone_target = self.bone_target
        trg.transform_type = self.transform_type
        trg.transform_space = self.transform_space
        if fixDrv:
            words = self.data_path.split('"')
            if words[0] == "pose.bones[":
                words[1] = UtilityBoneStatic.drv_bone(words[1])
                self.data_path = '"'.join(words)
        trg.data_path = self.data_path


class Variable:
    def __init__(self, var):
        self.type = var.type
        self.name = var.name
        self.targets = []
        for trg in var.targets:
            self.targets.append(Target(trg))

    def create(self, var, fixDrv=False):
        var.name = self.name
        var.type = self.type
        self.targets[0].create(var.targets[0], fixDrv)

        for target in self.targets[1:]:
            trg = var.targets.new()
            target.create(trg, fixDrv)


class Driver:
    def __init__(self, fcu, isArray):
        drv = fcu.driver
        self.data_path = fcu.data_path

        if isArray:
            self.array_index = fcu.array_index
        else:
            self.array_index = -1

        self.type = drv.type
        self.use_self = drv.use_self
        self.expression = drv.expression
        self.variables = []
        for var in drv.variables:
            self.variables.append(Variable(var))

    def getChannel(self):
        words = self.data_path.split('"')
        
        if words[0] == "pose.bones[" and len(words) == 5:
            bname = words[1]
            channel = words[3]
            self.data_path = self.data_path.replace(
                PropsStatic.ref(bname), PropsStatic.ref(UtilityBoneStatic.drv_bone(bname)))
            self.array_index = -1
            return PropsStatic.ref(channel), -1
        else:
            words = self.data_path.rsplit(".", 1)
            if len(words) == 2:
                channel = words[1]
            else:
                raise RuntimeError(
                    "BUG: Cannot create channel\n%s" % self.data_path)
            return channel, self.array_index

    def create(self, rna, fixDrv=False):
        channel, idx = self.getChannel()
        fcu = rna.driver_add(channel, idx)
        removeModifiers(fcu)
        return self.fill(fcu, fixDrv)

    def fill(self, fcu, fixDrv=False):
        drv = fcu.driver
        drv.type = self.type
        drv.use_self = self.use_self
        drv.expression = self.expression
        for var in self.variables:
            var.create(drv.variables.new(), fixDrv)
        return fcu

    def getNextVar(self, prop):
        varname = "a"
        for var in self.variables:
            if var.target.name == prop:
                return var.name, False
            elif ord(var.name) > ord(varname):
                varname = var.name
        return UtilityStatic.next_letter(varname), True
