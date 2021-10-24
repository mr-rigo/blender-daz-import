from daz_import.Elements.Color import ColorStatic
from daz_import.Elements.Material.Cycles import CyclesShader, CyclesStatic
from daz_import.Lib.VectorStatic import VectorStatic


class WorldShader(CyclesShader):
    type = "WORLD"

    def __init__(self, material):
        super().__init__(material)

    def build(self):
        backdrop = self.material.backdrop
        background = self.material.background
        envmap = self.material.envmap
        self.texco = self.makeTree()
        self.column = 5
        envnode = bgnode = socket = None

        if envmap:
            envnode, socket = self.buildEnvmap(envmap)
        if background:
            bgnode, socket = self.buildBackground(background, backdrop)

        if envnode and bgnode:
            self.column += 1
            mix = self.add_node("ShaderNodeMixShader")
            self.link(bgnode.outputs["Fac"], mix.inputs[0])
            self.link(envnode.outputs["Background"], mix.inputs[1])
            self.link(bgnode.outputs["Color"], mix.inputs[2])
            socket = mix.outputs[0]

        self.column += 1
        output = self.add_node("ShaderNodeOutputWorld")

        if socket:
            self.link(socket, output.inputs["Surface"])

        self.pruneNodeTree(self)

    def buildEnvmap(self, envmap):
        from mathutils import Euler

        texco = self.texco.outputs["Generated"]
        rot = self.getValue(["Dome Rotation"], 0)
        orx = self.getValue(["Dome Orientation X"], 0)
        ory = self.getValue(["Dome Orientation Y"], 0)
        orz = self.getValue(["Dome Orientation Z"], 0)

        if rot != 0 or orx != 0 or ory != 0 or orz != 0:
            mat1 = Euler((0, 0, -rot*VectorStatic.D)).to_matrix()
            mat2 = Euler((0, -orz*VectorStatic.D, 0)).to_matrix()
            mat3 = Euler((orx*VectorStatic.D, 0, 0)).to_matrix()
            mat4 = Euler((0, 0, ory*VectorStatic.D)).to_matrix()
            mat = mat1 @ mat2 @ mat3 @ mat4
            scale = (1, 1, 1)
            texco = self.addMapping(mat.to_euler(), scale, texco, 2)

        value = self.material.channelsData.getChannelValue(envmap, 1)
        img = self.getImage(envmap, "NONE")
        tex = None
        if img:
            tex = self.add_node("ShaderNodeTexEnvironment", 3)
            self.setColorSpace(tex, "NONE")
            if img:
                tex.image = img
                tex.name = img.name
            self.link(texco, tex.inputs["Vector"])
        strength = self.getValue(["Environment Intensity"], 1) * value

        envnode = self.add_node("ShaderNodeBackground")
        envnode.inputs["Strength"].default_value = strength
        self.linkColor(tex, envnode, ColorStatic.WHITE)
        socket = envnode.outputs["Background"]
        return envnode, socket

    def buildBackground(self, background, backdrop):
        tex = None
        texco = self.texco.outputs["Window"]
        if backdrop:
            if (backdrop["rotation"] != "NO_ROTATION" or
                backdrop["flip_horizontal"] or
                    backdrop["flipped_vertical"]):
                if backdrop["rotation"] == "ROTATE_LEFT_90":
                    zrot = 90*VectorStatic.D
                elif backdrop["rotation"] == "ROTATE_RIGHT_90":
                    zrot = -90*VectorStatic.D
                elif backdrop["rotation"] == "ROTATE_180":
                    zrot = 180*VectorStatic.D
                else:
                    zrot = 0
                scale = [1, 1, 1]
                if backdrop["flip_horizontal"]:
                    scale[0] = -1
                    zrot *= -1
                if backdrop["flipped_vertical"]:
                    scale[1] = -1
                    zrot *= -1
                texco = self.addMapping([0, 0, zrot], scale, texco, 2)
            img = self.getImage(backdrop, "COLOR")
            if img:
                tex = self.addTextureNode(3, img, img.name, "COLOR")
                self.linkVector(texco, tex)
        from .BackgroundGroup import BackgroundGroup

        bgnode = self.add_group(BackgroundGroup, "DAZ Background")
        self.linkColor(tex, bgnode, background)
        bgnode.inputs["Color"].default_value[0:3] = background
        socket = bgnode.outputs["Color"]
        return bgnode, socket

    def addMapping(self, rot, scale, texco, col):
        mapping = self.add_node("ShaderNodeMapping", col)
        mapping.vector_type = 'TEXTURE'
        if hasattr(mapping, "rotation"):
            mapping.rotation = rot
            mapping.scale = scale
        else:
            mapping.inputs['Rotation'].default_value = rot
            mapping.inputs['Scale'].default_value = scale
        self.link(texco, mapping.inputs["Vector"])
        return mapping.outputs["Vector"]

    def getImage(self, channel, colorSpace):
        textures, _ = self.material.getTextures(channel)
        if not textures:
            return None

        texture = textures[0]
        img = texture.images.get(colorSpace)
        if img is None:
            img = texture.buildCycles(colorSpace)
        return img
