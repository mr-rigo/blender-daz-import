from typing import Any, List, Tuple, Iterable
from urllib.parse import unquote

from daz_import.Lib.Utility import UtilityStatic
from daz_import.Elements.Transform import Transform
from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *

from daz_import.Elements.Node import Node, Instance, setBoneTransform

from daz_import.fix import getSuffixName
from daz_import.Elements.Morph import buildBoneFormula
from daz_import.merge import GenesisToes
from daz_import.driver import isBoneDriven

from daz_import.Elements.Bone.data import *
from daz_import.Elements.Bone.tools import *
from daz_import.Elements.Bone.BoneInstance import BoneInstance
from mathutils import *
from daz_import.utils import *


class Bone(Node):

    def __init__(self, fileref):
        self.node: Any = None

        Node.__init__(self, fileref)

        self.translation = []
        self.rotation = []
        self.scale = []

    def __repr__(self):
        return ("<Bone %s %s>" % (self.id, self.rna))

    def getSelfId(self):
        return self.node.name

    def makeInstance(self, fileref, struct):
        return BoneInstance(fileref, self, struct)

    def getInstance(self, ref, caller=None):
        iref = UtilityStatic.inst_ref(ref)
        if iref in self.instances.keys():
            return self.instances[iref]
        iref = unquote(iref)
        if iref in self.instances.keys():
            return self.instances[iref]
        try:
            return self.instances[BoneAlternatives[iref]]
        except KeyError:
            pass
        trgfig = self.figure.sourcing
        if trgfig:
            struct = {
                "id": iref,
                "url": self.url,
                "target": trgfig,
            }
            inst = self.makeInstance(self.fileref, struct)
            self.instances[iref] = inst
            print("Creating reference to target figure:\n", inst)
            return inst
        if (Settings.verbosity <= 2 and
                len(self.instances.values()) > 0):
            return list(self.instances.values())[0]
        msg = ("Bone: Did not find instance %s in %s" %
               (iref, list(self.instances.keys())))
        ErrorsStatic.report(msg, trigger=(2, 3))
        return None

    def parse(self, struct):
        from daz_import.figure import Figure

        Node.parse(self, struct)
        for channel, data in struct.items():
            if channel == "rotation":
                self.rotation = data
            elif channel == "translation":
                self.translation = data
            elif channel == "scale":
                self.scale = data
        if isinstance(self.parent, Figure):
            self.figure = self.parent
        elif isinstance(self.parent, Bone):
            self.figure = self.parent.figure

    def build(self, context, inst=None):
        ...

    def preprocess(self, context, inst):
        ...

    def preprocess2(self, context, inst):
        ...

    def poseRig(self, context, inst):
        ...
