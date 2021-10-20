import bpy
import os
from bpy.props import StringProperty, FloatProperty,\
    EnumProperty, BoolProperty, IntProperty

from daz_import.Lib import Registrar
from daz_import.Lib.BlenderStatic import BlenderStatic
from daz_import.Lib.Settings import Settings as Settings_
from daz_import.Lib.Errors import ErrorsStatic, IsMesh,\
    DazOperator, DazPropsOperator
from daz_import.Lib.Utility import UtilityStatic

theSimPresets = {}

# -------------------------------------------------------------
#  dForce simulation
# -------------------------------------------------------------


class DForce:
    def __init__(self, inst, mod, extra):
        self.instance = inst
        self.modifier = mod
        self.extra = extra
        # print("\nCREA", self)

    def __repr__(self):
        return "<DForce %s\ni: %s\nm: %s\ne: %s>" % (self.type, self.instance, self.modifier, self.instance.rna)

    def build(self, _):
        print("Build", self)
        pass

# -------------------------------------------------------------
#  studio/modifier/dynamic_generate_hair
# -------------------------------------------------------------


class DynGenHair(DForce):
    type = "DynGenHair"

# -------------------------------------------------------------
#  studio/modifier/dynamic_simulation
# -------------------------------------------------------------


class DynSim(DForce):
    type = "DynSim"

    def build(self, context):
        if not Settings_.useSimulation:
            return
        from daz_import.Elements.Node import Instance
        from daz_import.geometry import GeoNode
        if isinstance(self.instance, Instance):
            geonode = self.instance.geometries[0]
        elif isinstance(self.instance, GeoNode):
            geonode = self.instance
        else:
            ErrorsStatic.report("Bug DynSim %s" %
                                self.instance, trigger=(2, 3))
            return
        ob = geonode.rna
        if ob and ob.type == 'MESH':
            ob.DazCloth = True
            self.addPinVertexGroup(ob, geonode)

    def addPinVertexGroup(self, ob, geonode):
        nverts = len(ob.data.vertices)

        # Influence group
        useInflu = False
        if "influence_weights" in self.extra.keys():
            vcount = self.extra["vertex_count"]
            if vcount == nverts:
                useInflu = True
                influ = dict([(vn, 0.0) for vn in range(nverts)])
                vgrp = ob.vertex_groups.new(name="dForce Influence")
                weights = self.extra["influence_weights"]["values"]
                for vn, w in weights:
                    influ[vn] = w
                    vgrp.add([vn], w, 'REPLACE')
            else:
                msg = ("Influence weight mismatch: %d != %d" %
                       (vcount, nverts))
                ErrorsStatic.report(msg, trigger=(2, 4))
        if not useInflu:
            influ = dict([(vn, 1.0) for vn in range(nverts)])

        # Constant per material vertex group
        vgrp = ob.vertex_groups.new(name="dForce Pin")
        geo = geonode.data
        mnums = dict([(mgrp, mn)
                      for mn, mgrp in enumerate(geo.polygon_material_groups)])
        for simset in geonode.simsets:            
            strength = simset.modifier.channelsData.getValue(["Dynamics Strength"], 0.0)
            if strength == 1.0 and not useInflu:
                continue
            for mgrp in simset.modifier.groups:
                mn = mnums[mgrp]
                for f in ob.data.polygons:
                    if f.material_index == mn:
                        for vn in f.vertices:
                            vgrp.add([vn], 1-strength*influ[vn], 'REPLACE')
        return vgrp

# -------------------------------------------------------------
#   Make Collision
# -------------------------------------------------------------


class Collision:
    collDist: FloatProperty(
        name="Collision Distance",
        description="Minimun collision distance (mm)",
        min=1.0, max=20.0,
        default=1.0)

    def draw(self, context):
        self.layout.prop(self, "collDist")

    def addCollision(self, ob):
        subsurf = hideModifier(ob, 'SUBSURF')
        multires = hideModifier(ob, 'MULTIRES')
        mod = BlenderStatic.modifier(ob, 'COLLISION')
        if mod is None:
            mod = ob.modifiers.new("Collision", 'COLLISION')
        ob.collision.thickness_outer = 0.1*ob.DazScale*self.collDist
        if subsurf:
            subsurf.restore(ob)
        if multires:
            multires.restore(ob)


@Registrar()
class DAZ_OT_MakeCollision(DazPropsOperator, Collision):
    bl_idname = "daz.make_collision"
    bl_label = "Make Collision"
    bl_description = "Add collision modifiers to selected meshes"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.addCollision(ob)

# -------------------------------------------------------------
#   Make Cloth
# -------------------------------------------------------------


class Cloth:
    simPreset: EnumProperty(
        items=[('cotton.json', "Cotton", "Cotton"),
               ('denim.json', "Denim", "Denim"),
               ('leather.json', "Leather", "Leather"),
               ('rubber.json', "Rubber", "Rubber"),
               ('silk.json', "Silk", "Silk")],
        name="Preset",
        description="Simulation preset")

    pinGroup: StringProperty(
        name="Pin Group",
        description="Use this group as pin group",
        default="dForce Pin")

    simQuality: IntProperty(
        name="Simulation Quality",
        description="Simulation Quality",
        default=16)

    collQuality: IntProperty(
        name="Collision Quality",
        description="Collision Quality",
        default=4)

    gsmFactor: FloatProperty(
        name="GSM Factor",
        description="GSM Factor (vertex mass multiplier)",
        min=0.0,
        default=0.5)

    def draw(self, context):
        self.layout.prop(self, "simPreset")
        self.layout.prop(self, "pinGroup")
        self.layout.prop(self, "simQuality")
        self.layout.prop(self, "collQuality")
        self.layout.prop(self, "gsmFactor")

    def addCloth(self, ob):
        scale = ob.DazScale
        collision = hideModifier(ob, 'COLLISION')
        subsurf = hideModifier(ob, 'SUBSURF')
        multires = hideModifier(ob, 'MULTIRES')

        cloth = BlenderStatic.modifier(ob, 'CLOTH')
        if cloth is None:
            cloth = ob.modifiers.new("Cloth", 'CLOTH')
        cset = cloth.settings
        self.setPreset(cset)
        cset.mass *= self.gsmFactor
        cset.quality = self.simQuality
        # Collision settings
        colset = cloth.collision_settings
        colset.distance_min = 0.1*scale*self.collDist
        colset.self_distance_min = 0.1*scale*self.collDist
        colset.collision_quality = self.collQuality
        colset.use_self_collision = True
        # Pinning
        cset.vertex_group_mass = self.pinGroup
        cset.pin_stiffness = 1.0

        if collision:
            collision.restore(ob)
        if subsurf:
            subsurf.restore(ob)
        if multires:
            multires.restore(ob)

    def setPreset(self, cset):
        global theSimPresets

        if not theSimPresets:
            from daz_import.Lib import Json

            folder = os.path.dirname(__file__) + "/data/presets"

            for file in os.listdir(folder):
                filepath = os.path.join(folder, file)
                theSimPresets[file] = Json.load(filepath)

        struct = theSimPresets[self.simPreset]

        for key, value in struct.items():
            setattr(cset, key, value)


@Registrar()
class DAZ_OT_MakeCloth(DazPropsOperator, Cloth, Collision):
    
    bl_idname = "daz.make_cloth"
    bl_label = "Make Cloth"
    bl_description = "Add cloth modifiers to selected meshes"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def draw(self, context):
        Cloth.draw(self, context)
        Collision.draw(self, context)

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.addCloth(ob)

# -------------------------------------------------------------
#  studio/modifier/dynamic_hair_follow
# -------------------------------------------------------------


class DynHairFlw(DForce):
    type = "DynHairFlw"

# -------------------------------------------------------------
#  studio/modifier/line_tessellation
# -------------------------------------------------------------


class LinTess(DForce):
    type = "LinTess"

# -------------------------------------------------------------
#  studio/simulation_settings/dynamic_simulation
# -------------------------------------------------------------


class SimSet(DForce):
    type = "SimSet"

# -------------------------------------------------------------
#  class for storing modifiers
# -------------------------------------------------------------


def hideModifier(ob, mtype):
    mod = BlenderStatic.modifier(ob, mtype)
    if mod:
        store = ModStore(mod)
        ob.modifiers.remove(mod)
        return store
    else:
        return None


class ModStore:
    def __init__(self, mod):
        self.name = mod.name
        self.type = mod.type
        self.data = {}
        self.store(mod, self.data)
        self.settings = {}
        if hasattr(mod, "settings"):
            self.store(mod.settings, self.settings)
        self.collision_settings = {}
        if hasattr(mod, "collision_settings"):
            self.store(mod.collision_settings, self.collision_settings)

    def store(self, data, struct):
        for key in dir(data):
            if (key[0] == '_' or
                key == "name" or
                    key == "type"):
                continue
            value = getattr(data, key)
            if UtilityStatic.is_simple_type(value) or \
                    isinstance(value, bpy.types.Object):
                struct[key] = value

    def restore(self, ob):
        mod = ob.modifiers.new(self.name, self.type)
        self.restoreData(self.data, mod)
        if self.settings:
            self.restoreData(self.settings, mod.settings)
        if self.collision_settings:
            self.restoreData(self.collision_settings, mod.collision_settings)

    def restoreData(self, struct, data):
        for key, value in struct.items():
            try:
                setattr(data, key, value)
            except:
                pass

# -------------------------------------------------------------
#   Make Simulation
# -------------------------------------------------------------


class Settings:
    filepath = "~/daz_importer_simulations.json"

    props = ["simPreset", "pinGroup", "simQuality",
             "collQuality", "gsmFactor", "collDist"]

    def invoke(self, context, event):
        from daz_import.Lib.Files import Json

        if struct := Json.load_setting(self.filepath):
            print("Load settings from", self.filepath)
            self.readSettings(struct)
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def readSettings(self, struct):
        if "simulation-settings" in struct.keys():
            settings = struct["simulation-settings"]
            for key, value in settings.items():
                if key in self.props:
                    setattr(self, key, value)

    def saveSettings(self):
        from daz_import.Lib import Json
        struct = {}
        for key in self.props:
            value = getattr(self, key)
            struct[key] = value
        filepath = os.path.expanduser(self.filepath)
        Json.save({"simulation-settings": struct}, filepath)
        print("Settings file %s saved" % filepath)


@Registrar()
class DAZ_OT_MakeSimulation(DazOperator, Collision, Cloth, Settings):
    bl_idname = "daz.make_simulation"
    bl_label = "Make Simulation"
    bl_description = "Create simulation from Daz data"
    bl_options = {'UNDO'}

    def draw(self, context):
        Cloth.draw(self, context)
        Collision.draw(self, context)

    def run(self, context):
        for ob in BlenderStatic.visible_meshes(context):
            if ob.DazCollision:
                self.addCollision(ob)
            if ob.DazCloth:
                self.addCloth(ob)
        self.saveSettings()

# -------------------------------------------------------------
#   Initialize
# -------------------------------------------------------------


@Registrar.func
def register():
    bpy.types.Object.DazCollision = BoolProperty(default=True)
    bpy.types.Object.DazCloth = BoolProperty(default=False)
