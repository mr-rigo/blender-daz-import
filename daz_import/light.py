import bpy
import math
from daz_import.Elements.Node import Node, Instance

from daz_import.Elements.Material.Cycles import CyclesMaterial, CyclesShader
from daz_import.Elements.Material import Material
from daz_import.Elements.Color import ColorStatic
from daz_import.Lib.Errors import ErrorsStatic

from daz_import.utils import *

# -------------------------------------------------------------
#   Light base class
# -------------------------------------------------------------


def getMinLightSettings():
    return [("use_shadow", "=", True),
            ("shadow_buffer_clip_start", "<", 1.0*Settings.scale_),
            ("shadow_buffer_bias", "<", 0.01),
            ("use_contact_shadow", "=", True),
            ("contact_shadow_bias", "<", 0.01),
            ("contact_shadow_distance", "<", 1.0*Settings.scale_),
            ("contact_shadow_thickness", "<", 10*Settings.scale_),
            ]


class Light(Node):

    def __init__(self, fileref):
        super().__init__(fileref)
        self.type = None

        self.info = {}
        self.presentation = {}
        self.data = None
        self.twosided = False

    def __repr__(self):
        return ("<Light %s %s>" % (self.id, self.rna))

    def parse(self, data: dict):
        super().parse(data)

        if cache := data.get("spot"):
            self.type = 'SPOT'
            self.info = cache
        elif cache := data.get("point"):
            self.type = 'POINT'
            self.info = cache
        elif cache := data.get("directional"):
            self.type = 'DIRECTIONAL'
            self.info = cache
        else:
            self.presentation = data["presentation"]
            print("Strange lamp", self)

    def makeInstance(self, fileref, struct):
        return LightInstance(fileref, self, struct)

    def build(self, context, inst):
        lgeo = inst.channelsData.getValue(["Light Geometry"], -1)
        usePhoto = inst.channelsData.getValue(["Photometric Mode"], False)

        self.twosided = inst.channelsData.getValue(["Two Sided"], False)
        height = inst.channelsData.getValue(["Height"], 0) * Settings.scale_
        width = inst.channelsData.getValue(["Width"], 0) * Settings.scale_

        # [ "Point", "Rectangle", "Disc", "Sphere", "Cylinder" ]
        if lgeo == 1:
            lamp = bpy.data.lights.new(self.name, "AREA")
            lamp.shape = 'RECTANGLE'
            lamp.size = width
            lamp.size_y = height
        elif lgeo == 2:
            lamp = bpy.data.lights.new(self.name, "AREA")
            lamp.shape = 'DISK'
            lamp.size = height
        elif lgeo > 1:
            lamp = bpy.data.lights.new(self.name, "POINT")
            lamp.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'POINT':
            lamp = bpy.data.lights.new(self.name, "POINT")
            lamp.shadow_soft_size = 0
            inst.fluxFactor = 3
            self.twosided = False
        elif self.type == 'SPOT':
            lamp = bpy.data.lights.new(self.name, "SPOT")
            lamp.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'DIRECTIONAL':
            lamp = bpy.data.lights.new(self.name, "SUN")
            lamp.shadow_soft_size = height/2
            self.twosided = False
        elif self.type == 'light':
            lamp = bpy.data.lights.new(self.name, "AREA")
        else:
            msg = ("Unknown light type: %s" % self.type)
            ErrorsStatic.report(msg, trigger=(1, 3))
            lamp = bpy.data.lights.new(self.name, "SPOT")
            lamp.shadow_soft_size = height/2
            self.twosided = False

        self.setCyclesProps(lamp)
        self.data = lamp
        super().build(context, inst)
        inst.material.build(context)

    @staticmethod
    def setCyclesProps(lamp):
        for attr, _, value in getMinLightSettings():
            if hasattr(lamp, attr):
                setattr(lamp, attr, value)

    def postTransform(self):
        if Settings.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2

    def postbuild(self, context, inst):
        super().postbuild(context, inst)
        if not self.twosided or not inst.rna:
            return

        ob = inst.rna

        BlenderStatic.activate(context, ob)
        bpy.ops.object.duplicate_move()

        nob = BlenderStatic.active_object(context)
        nob.data = ob.data
        nob.scale = -ob.scale


# -------------------------------------------------------------
#   LightInstance
# -------------------------------------------------------------


class LightInstance(Instance):
    def __init__(self, fileref, node, struct):
        super().__init__(fileref, node, struct)
        self.material = CyclesLightMaterial(fileref, self)
        self.fluxFactor = 1

    def buildChannels(self, context):
        super().buildChannels(context)
        lamp = self.rna.data

        if self.channelsData.getValue(["Cast Shadows"], 0):
            lamp.cycles.cast_shadow = True
        else:
            lamp.cycles.cast_shadow = False

        lamp.color = self.channelsData.getValue(["Color"], ColorStatic.WHITE)
        flux = self.channelsData.getValue(["Flux"], 15000)
        lamp.energy = flux / 15000
        lamp.shadow_color = self.channelsData.getValue(
            ["Shadow Color"], ColorStatic.BLACK)
        if hasattr(lamp, "shadow_buffer_soft"):
            lamp.shadow_buffer_soft = self.channelsData.getValue(
                ["Shadow Softness"], False)
        # if hasattr(lamp, "shadow_buffer_bias"):
        #    bias = self.channelsData.getValue(["Shadow Bias"], None)
        #    if bias:
        #        lamp.shadow_buffer_bias = bias
        if hasattr(lamp, "falloff_type"):
            value = self.channelsData.getValue(["Decay"], 2)
            dtypes = ['CONSTANT', 'INVERSE_LINEAR', 'INVERSE_SQUARE']
            lamp.falloff_type = dtypes[value]

# -------------------------------------------------------------
#   Cycles Light Material
# -------------------------------------------------------------


class CyclesLightMaterial(CyclesMaterial):

    def __init__(self, fileref, inst):
        super().__init__(fileref)
        self.name = inst.name
        self.channelsData.channels = inst.channelsData.channels
        self.instance = inst

    def guessColor(self):
        ...

    def get_shader(self, _=None) -> CyclesShader:
        return LightShader(self)


class LightShader(CyclesShader):

    def build(self):
        self.makeTree()
        color = self.getValue(["Color"], ColorStatic.WHITE)
        #flux = self.getValue(["Flux"], 15000)

        emit = self.add_node("ShaderNodeEmission", 1)
        emit.inputs["Color"].default_value[0:3] = color
        emit.inputs["Strength"].default_value = self.material.instance.fluxFactor
        output = self.add_node("ShaderNodeOutputLight", 2)
        self.link(emit.outputs[0], output.inputs["Surface"])

    def addTexco(self, slot):
        ...
