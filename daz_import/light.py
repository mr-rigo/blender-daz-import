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
        Node.__init__(self, fileref)
        
        self.type = None
        self.info = {}
        self.presentation = {}
        self.data = None
        self.twosided = False

    def __repr__(self):
        return ("<Light %s %s>" % (self.id, self.rna))

    def parse(self, struct):
        Node.parse(self, struct)
        if "spot" in struct.keys():
            self.type = 'SPOT'
            self.info = struct["spot"]
        elif "point" in struct.keys():
            self.type = 'POINT'
            self.info = struct["point"]
        elif "directional" in struct.keys():
            self.type = 'DIRECTIONAL'
            self.info = struct["directional"]
        else:
            self.presentation = struct["presentation"]
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
        Node.build(self, context, inst)
        inst.material.build(context)

    def setCyclesProps(self, lamp):
        for attr, op, value in getMinLightSettings():
            if hasattr(lamp, attr):
                setattr(lamp, attr, value)

    def postTransform(self):
        if Settings.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2

    def postbuild(self, context, inst):
        Node.postbuild(self, context, inst)
        if self.twosided:
            if inst.rna:
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
        Instance.__init__(self, fileref, node, struct)
        self.material = CyclesLightMaterial(fileref, self)
        self.fluxFactor = 1

    def buildChannels(self, context):
        Instance.buildChannels(self, context)
        lamp = self.rna.data
        if self.channelsData.getValue(["Cast Shadows"], 0):
            lamp.cycles.cast_shadow = True
        else:
            lamp.cycles.cast_shadow = False

        lamp.color = self.channelsData.getValue(["Color"], ColorStatic.WHITE)
        flux = self.channelsData.getValue(["Flux"], 15000)
        lamp.energy = flux / 15000
        lamp.shadow_color = self.channelsData.getValue(["Shadow Color"], ColorStatic.BLACK)
        if hasattr(lamp, "shadow_buffer_soft"):
            lamp.shadow_buffer_soft = self.channelsData.getValue(["Shadow Softness"], False)
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
        CyclesMaterial.__init__(self, fileref)
        self.name = inst.name
        self.channelsData.channels = inst.channelsData.channels
        self.instance = inst

    def guessColor(self):
        return

    def build(self, context):
        if self.dontBuild():
            return
        Material.build(self, context)
        self.shader_object = LightTree(self)
        self.shader_object.build()


class LightTree(CyclesShader):

    def build(self):
        self.makeTree()
        color = self.getValue(["Color"], ColorStatic.WHITE)
        #flux = self.getValue(["Flux"], 15000)

        emit = self.addNode("ShaderNodeEmission", 1)
        emit.inputs["Color"].default_value[0:3] = color
        emit.inputs["Strength"].default_value = self.material.instance.fluxFactor
        output = self.addNode("ShaderNodeOutputLight", 2)
        self.links.new(emit.outputs[0], output.inputs["Surface"])

    def addTexco(self, slot):
        return
