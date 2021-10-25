import bpy
import math
from mathutils import Matrix
from daz_import.Lib.Settings import Settings
from daz_import.Elements.Color import ColorStatic
from daz_import.Elements.Material.Cycles.CyclesStatic import CyclesStatic
from daz_import.Elements.Material.Cycles.CyclesTree import CyclesShader
from daz_import.Elements.Material.Material import Material
from daz_import.Lib import BlenderStatic


class CyclesMaterial(Material):

    def __init__(self, fileref):
        super().__init__(fileref)
        self.shader_object: CyclesShader = None
        self.useEevee = False

    def __repr__(self):
        treetype = None

        if self.shader_object:
            treetype = self.shader_object.type

        geoname = None

        if self.geometry:
            geoname = self.geometry.name

        return ("<%sMaterial %s r:%s g:%s i:%s t:%s>" % (treetype, self.id, self.rna, geoname, self.ignore, self.hasAnyTexture()))

    def guessColor(self):
        from daz_import.Elements.Material import MaterialStatic
        from daz_import.geometry import GeoNode
        from daz_import.Elements.Finger import isCharacter

        color = Settings.clothesColor_

        if isinstance(self.geometry, GeoNode):
            ob = self.geometry.rna

            if ob is None:
                pass
            elif isCharacter(ob):
                color = Settings.skinColor_
            elif ob.data and ob.data.DazGraftGroup:
                color = Settings.skinColor_

        MaterialStatic.guessMaterialColor(
            self.rna, Settings.viewportColors, False, color)

    def build(self, context, color=None):
        if self.dontBuild():
            return

        super().build(context)

        self.shader_object = self.get_shader(color)
        self.shader_object.build()

    def get_shader(self, color=None) -> CyclesShader:
        from daz_import.Elements.Material.PbrTree import PBRShader
        from daz_import.Elements.Hair import HairBSDFShader, HairEeveeShader, HairPBRShader

        if self.isHair:
            ...
        elif self.metallic:
            return PBRShader(self)
        elif Settings.materialMethod == 'PRINCIPLED':
            return PBRShader(self)
        else:
            return CyclesShader(self)

        geo = self.geometry

        if geo and geo.isStrandHair:
            geo.hairMaterials.append(self)

        if color is None:
            color = ColorStatic.BLACK

        if Settings.hairMaterialMethod_ == 'HAIR_PRINCIPLED':
            return HairPBRShader(self, color)
        elif Settings.hairMaterialMethod_ == 'PRINCIPLED':
            return HairEeveeShader(self, color)
        else:
            return HairBSDFShader(self, color)

    def postbuild(self):
        super().postbuild()
                
        geonode = self.geometry
        me = None

        if geonode and geonode.data and geonode.data.rna:
            geo = geonode.data
            me = geo.rna
            mnum = -1

            for mn, mat in enumerate(me.materials):
                if mat == self.rna:
                    mnum = mn
                    break

            if mnum < 0:
                return

            nodes = list(geo.nodes.values())
            
            if self.geoemit:
                self.correctEmitArea(nodes, me, mnum)
            
            if self.geobump:
                area = geo.getBumpArea(me, self.geobump.keys())
                self.correctBumpArea(area)

        if self.shader_object and Settings.pruneNodes:
            marked = self.shader_object.pruneNodeTree()
            self.shader_object.selectDiffuse(marked)

    def addGeoBump(self, tex, socket):
        bumpmin = self.channelsData.getValue("getChannelBumpMin", -0.01)
        bumpmax = self.channelsData.getValue("getChannelBumpMax", 0.01)
        socket.default_value = (bumpmax-bumpmin) * Settings.scale_
        key = tex.name
        
        if key not in self.geobump.keys():
            self.geobump[key] = (tex, [])

        self.geobump[key][1].append(socket)

    def correctBumpArea(self, area):
        if area <= 0.0:
            return

        for tex, sockets in self.geobump.values():
            if not hasattr(tex, "image") or tex.image is None:
                continue

            width, height = tex.image.size
            density = width * height / area

            if density == 0.0:
                continue

            link = CyclesStatic.getLinkTo(self.shader_object, tex, "Vector")

            if link and link.from_node.type == 'MAPPING':
                scale = link.from_node.inputs["Scale"]
                density *= scale.default_value[0] * scale.default_value[1]
                if density == 0.0:
                    continue

            if density > 0:
                height = 3.0/math.sqrt(density)

            for socket in sockets:
                socket.default_value = height

    def correctEmitArea(self, nodes, me, mnum):
        ob = nodes[0].rna
        ob.data = me2 = me.copy()
        wmat = ob.matrix_world.copy()
        me2.transform(wmat)
        
        BlenderStatic.world_matrix(ob, Matrix())
        
        area = sum([f.area for f in me2.polygons if f.material_index == mnum])
        ob.data = me

        BlenderStatic.world_matrix(ob, wmat)
        bpy.data.meshes.remove(me2, do_unlink=True)

        area *= 1e-4/(Settings.scale_*Settings.scale_)
        
        for socket in self.geoemit:
            socket.default_value /= area            
            for link in self.shader_object.shader_graph.links:
                if link.to_socket != socket:
                    continue
                node = link.from_node
                if node.type == 'MATH':
                    node.inputs[0].default_value /= area

    def setTransSettings(self, useRefraction, useBlend, color, alpha):
        Settings.usedFeatures_["Transparent"] = True
        mat = self.rna

        if useBlend:
            mat.blend_method = 'BLEND'
            mat.show_transparent_back = False
        else:
            mat.blend_method = 'HASHED'

        mat.use_screen_refraction = useRefraction

        if hasattr(mat, "transparent_shadow_method"):
            mat.transparent_shadow_method = 'HASHED'
        else:
            mat.shadow_method = 'HASHED'

        if not self.isShellMat:
            mat.diffuse_color[0:3] = color
            mat.diffuse_color[3] = alpha
