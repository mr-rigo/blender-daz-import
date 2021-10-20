from daz_import.utils import *


class MorphTypeOptions:
    units : BoolProperty(
        name = "Face Units",
        description = "Import all face units",
        default = False)

    expressions : BoolProperty(
        name = "Expressions",
        description = "Import all expressions",
        default = False)

    visemes : BoolProperty(
        name = "Visemes",
        description = "Import all visemes",
        default = False)

    facs : BoolProperty(
        name = "FACS",
        description = "Import all FACS units",
        default = False)

    facsexpr : BoolProperty(
        name = "FACS Expressions",
        description = "Import all FACS expressions",
        default = False)

    body : BoolProperty(
        name = "Body",
        description = "Import all body morphs",
        default = False)

    useMhxOnly : BoolProperty(
        name = "MHX Compatible Only",
        description = "Only import MHX compatible body morphs",
        default = False)

    jcms : BoolProperty(
        name = "JCMs",
        description = "Import all JCMs",
        default = False)

    flexions : BoolProperty(
        name = "Flexions",
        description = "Import all flexions",
        default = False)

    def draw(self, context):
        self.layout.prop(self, "units")
        self.layout.prop(self, "expressions")
        self.layout.prop(self, "visemes")
        self.layout.prop(self, "facs")
        self.layout.prop(self, "facsexpr")
        self.layout.prop(self, "body")
        if self.body:
            self.subprop("useMhxOnly")
        self.layout.prop(self, "jcms")
        self.layout.prop(self, "flexions")

    def subprop(self, prop):
        split = self.layout.split(factor=0.05)
        split.label(text="")
        split.prop(self, prop)
