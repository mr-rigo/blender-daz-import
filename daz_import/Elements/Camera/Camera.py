import bpy
import math
from daz_import.Elements.Camera.CameraInstance import CameraInstance
from daz_import.Elements.Node import Node, Instance
from daz_import.utils import *


class Camera(Node):

    def __init__(self, fileref):
        Node.__init__(self, fileref)
        
        self.perspective = {}
        self.orthographic = {}
        self.aspectRatio = 1.0

    def __repr__(self):
        return ("<Camera %s>" % (self.id))

    def parse(self, struct):
        Node.parse(self, struct)
        if "perspective" in struct.keys():
            self.perspective = struct["perspective"]
        elif "orthographic" in struct.keys():
            self.orthographic = struct["orthographic"]

    def postTransform(self):
        if Settings.zup:
            ob = self.rna
            ob.rotation_euler[0] += math.pi/2

    def makeInstance(self, fileref, struct):
        return CameraInstance(fileref, self, struct)

    def build(self, context, inst):
        if self.perspective:
            self.data = bpy.data.cameras.new(self.name)
            inst.setCameraProps(self.perspective)
        elif self.orthographic:
            self.data = bpy.data.cameras.new(self.name)
            inst.setCameraProps(self.orthographic)
        else:
            return None
        Node.build(self, context, inst)
