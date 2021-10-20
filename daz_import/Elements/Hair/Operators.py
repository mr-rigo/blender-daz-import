import sys
import bpy

from mathutils import Vector
from math import floor

from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import *
from daz_import.utils import *
from daz_import.Elements.Color import ColorStatic, ColorProp
from daz_import.Elements.Material.Cycles import CyclesMaterial, CyclesTree
from daz_import.Elements.Material.Data import EnumsHair
from daz_import.Elements.Morph import Selector
from daz_import.Lib import Registrar
from daz_import.Elements.Material.MaterialGroup import MaterialGroup
from .Hair import *
from .HairMaterial import HairMaterial



class IsHair:

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and ob.particle_systems.active)


@Registrar()
class DAZ_OT_UpdateHair(DazPropsOperator, HairUpdater, IsHair):
    bl_idname = "daz.update_hair"
    bl_label = "Update Hair"
    bl_description = "Change settings for particle hair"
    bl_options = {'UNDO'}

    affectMaterial: BoolProperty(
        name="Affect Material",
        description="Also change materials",
        default=False)

    def draw(self, context):
        self.layout.prop(self, "affectMaterial")

    def run(self, context):
        hum = context.object
        psys0 = hum.particle_systems.active
        idx0 = hum.particle_systems.active_index
        data = self.getAllSettings(psys0)
        for idx, psys in enumerate(hum.particle_systems):
            if idx == idx0:
                continue
            hum.particle_systems.active_index = idx
            self.setAllSettings(psys, data)
        hum.particle_systems.active_index = idx0


@Registrar()
class ColorGroup(bpy.types.PropertyGroup):
    color: FloatVectorProperty(
        name="Hair Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.2, 0.02, 0.01, 1)
    )


def getMaterialEnums(self, context):
    ob = context.object
    return [(mat.name, mat.name, mat.name) for mat in ob.data.materials]

class HairOptions:
    # Create

    strandType: EnumProperty(
        items=[('SHEET', "Sheet", "Sheets"),
               ('LINE', "Line", "Polylines"),
               ('TUBE', "Tube", "Tubes")],
        name="Strand Type",
        description="Mesh hair strand type",
        default='SHEET')

    strandOrientation: EnumProperty(
        items=[('TOP', "Top-Down", "Top-Down"),
               ('BOTTOM', "Bottom-Up", "Bottom-Up"),
               ('LEFT', "Left-Right", "Left-Right"),
               ('RIGHT', "Right-Left", "Right-Left")],
        name="Strand Orientation",
        default='TOP',
        description="How the strands are oriented in UV space"
    )

    keepMesh: BoolProperty(
        name="Keep Mesh Hair",
        default=False,
        description="Keep (reconstruct) mesh hair after making particle hair"
    )

    removeOldHairs: BoolProperty(
        name="Remove Particle Hair",
        default=False,
        description="Remove existing particle systems from this mesh"
    )

    useSeparateLoose: BoolProperty(
        name="Separate Loose Parts",
        default=True,
        description=("Separate hair mesh into loose parts before doing the conversion.\n" +
                     "Usually improves performance but can stall for large meshes")
    )

    sparsity: IntProperty(
        name="Sparsity",
        min=1,
        max=50,
        default=1,
        description="Only use every n:th hair"
    )

    size: IntProperty(
        name="Hair Length",
        min=3,
        max=100,
        default=20,
        description="Hair length"
    )

    resizeHair: BoolProperty(
        name="Resize Hair",
        default=False,
        description="Resize hair afterwards"
    )

    resizeInBlocks: BoolProperty(
        name="Resize In Blocks",
        default=False,
        description="Resize hair in blocks of ten afterwards"
    )

    # Settings

    nViewChildren: IntProperty(
        name="Viewport Children",
        description="Number of hair children displayed in viewport",
        min=0,
        default=0)

    nRenderChildren: IntProperty(
        name="Render Children",
        description="Number of hair children displayed in renders",
        min=0,
        default=0)

    nViewStep: IntProperty(
        name="Viewport Steps",
        description="How many steps paths are drawn with (power of 2)",
        min=0,
        default=3)

    nRenderStep: IntProperty(
        name="Render Steps",
        description="How many steps paths are rendered with (power of 2)",
        min=0,
        default=3)

    strandShape: EnumProperty(
        items=[('STANDARD', "Standard", "Standard strand shape"),
               ('ROOTS', "Fading Roots",
                "Root transparency (standard shape with fading roots)"),
               ('SHRINK', "Root And Tip Shrink", "Root and tip shrink.\n(Root and tip radii interchanged)")],
        name="Strand Shape",
        description="Strand shape",
        default='STANDARD')

    rootRadius: FloatProperty(
        name="Root radius (mm)",
        description="Strand diameter at the root",
        min=0,
        default=0.3)

    tipRadius: FloatProperty(
        name="Tip radius (mm)",
        description="Strand diameter at the tip",
        min=0,
        default=0.3)

    childRadius: FloatProperty(
        name="Child radius (mm)",
        description="Radius of children around parent",
        min=0,
        default=10)

    # Materials

    multiMaterials: BoolProperty(
        name="Multi Materials",
        description="Create separate particle systems for each material",
        default=True)

    keepMaterial: BoolProperty(
        name="Keep Material",
        description="Use existing material",
        default=True)

    activeMaterial: EnumProperty(
        items=getMaterialEnums,
        name="Material",
        description="Material to use as hair material")

    color: FloatVectorProperty(
        name="Hair Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.2, 0.02, 0.01, 1)
    )

    colors: CollectionProperty(type=ColorGroup)

    hairMaterialMethod: EnumProperty(
        items=EnumsHair,
        name="Hair Material Method",
        description="Type of hair material node tree",
        default='HAIR_BSDF')


@Registrar()
class DAZ_OT_CombineHairs(DazOperator, CombineHair, HairUpdater, Selector, HairOptions):
    bl_idname = "daz.combine_hairs"
    bl_label = "Combine Hairs"
    bl_description = "Combine several hair particle systems into a single one"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and len(ob.particle_systems) > 0)

    def draw(self, context):
        self.layout.prop(self, "size")
        Selector.draw(self, context)

    def invoke(self, context, event):
        return Selector.invoke(self, context, event)

    def getKeys(self, rig, ob):
        enums = []
        for n, psys in enumerate(ob.particle_systems):
            if psys.settings.type == 'HAIR':
                text = "(%3d)   %s" % (psys.settings.hair_step+1, psys.name)
                enum = (str(n), text, "All")
                enums.append(enum)
        return enums

    def getStrand(self, strand):
        return 0, len(strand), strand

    def getHairKey(self, n, mnum):
        mat = self.materials[0]
        return ("%d_%s" % (n, mat.name)), 0

    def getStrandsFromPsys(self, psys):
        strands = []
        for hair in psys.particles:
            strand = [v.co.copy() for v in hair.hair_keys]
            strands.append(strand)
        return strands

    def run(self, context):
        scn = context.scene
        ob = context.object
        psystems = []
        hsystems = {}
        haircount = -1
        for item in self.getSelectedItems():
            idx = int(item.name)
            psys = ob.particle_systems[idx]
            psystems.append((idx, psys))
        if len(psystems) == 0:
            raise DazError("No particle system selected")
        idx0, psys0 = psystems[0]
        self.affectMaterial = False
        data = self.getAllSettings(psys0)
        mname = psys0.settings.material_slot
        mat = ob.data.materials[mname]
        self.materials = [mat]

        for idx, psys in psystems:
            ob.particle_systems.active_index = idx
            psys = HairStatic.update(context, ob, psys)
            strands = self.getStrandsFromPsys(psys)
            haircount = self.addStrands(ob, strands, hsystems, haircount)
        psystems.reverse()
        for idx, psys in psystems:
            ob.particle_systems.active_index = idx
            bpy.ops.object.particle_system_remove()
        hsystems = self.hairResize(self.size, hsystems, ob)
        for hsys in hsystems.values():
            hsys.build(context, ob)
        psys = ob.particle_systems.active
        self.setAllSettings(psys, data)


@Registrar()
class DAZ_OT_ColorHair(DazPropsOperator, IsHair, ColorProp):
    bl_idname = "daz.color_hair"
    bl_label = "Color Hair"
    bl_description = "Change particle hair color"
    bl_options = {'UNDO'}

    def run(self, context):
        scn = context.scene
        hum = context.object
        fade = False
        mats = {}
        for mat in hum.data.materials:
            mats[mat.name] = (mat, True)
        for psys in hum.particle_systems:
            pset = psys.settings
            mname = pset.material_slot
            if mname in mats.keys() and mats[mname][1]:
                mat = HairMaterial.buildHairMaterial(mname, self.color, context, force=True)
                if fade:
                    FadeHairTree.addFade(mat)
                mats[mname] = (mat, False)

        for _, keep in mats.values():
            if not keep:
                hum.data.materials.pop()
        for mat, keep in mats.values():
            if not keep:
                hum.data.materials.append(mat)


@Registrar()
class DAZ_OT_MeshAddPinning(DazPropsOperator, Pinning):
    bl_idname = "daz.mesh_add_pinning"
    bl_label = "Add Pinning Group"
    bl_description = "Add HairPin group to mesh hair"
    bl_options = {'UNDO'}
    
    pool = IsMesh.pool

    def run(self, context):
        ob = context.object
        x0, x1, w0, w1, k = self.pinCoeffs()

        if "HairPinning" in ob.vertex_groups.keys():
            vgrp = ob.vertex_groups["HairPinning"]
            ob.vertex_groups.remove(vgrp)

        vgrp = ob.vertex_groups.new(name="HairPinning")
        uvs = ob.data.uv_layers.active.data
        m = 0
        for f in ob.data.polygons:
            for n, vn in enumerate(f.vertices):
                x = 1-uvs[m+n].uv[1]
                if x < x0:
                    w = w0
                elif x > x1:
                    w = w1
                else:
                    w = w0 + k*(x-x0)
                vgrp.add([vn], w, 'REPLACE')
            m += len(f.vertices)


@Registrar()
class DAZ_OT_HairAddPinning(DazPropsOperator, IsMesh, Pinning):
    bl_idname = "daz.hair_add_pinning"
    bl_label = "Hair Add Pinning"
    bl_description = "Add HairPin group to hair strands"
    bl_options = {'UNDO'}

    def run(self, context):
        ob = context.object
        x0, x1, w0, w1, k = self.pinCoeffs()


@Registrar()
class DAZ_OT_ConnectHair(DazOperator, IsHair):
    bl_idname = "daz.connect_hair"
    bl_label = "Connect Hair"
    bl_description = "(Re)connect hair"
    bl_options = {'UNDO'}

    def run(self, context):
        hum = context.object
        for mod in hum.modifiers:
            if isinstance(mod, bpy.types.ParticleSystemModifier):
                print(mod)

        nparticles = len(hum.particle_systems)
        for n in range(nparticles):
            hum.particle_systems.active_index = n
            print(hum.particle_systems.active_index,
                  hum.particle_systems.active)
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.disconnect_hair()
            bpy.ops.particle.particle_edit_toggle()
            bpy.ops.particle.connect_hair()
            bpy.ops.particle.particle_edit_toggle()
