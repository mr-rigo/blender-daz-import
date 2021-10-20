
import bpy
from mathutils import Vector
from daz_import.Lib.Settings import Settings, Settings
from daz_import.Lib import Registrar
from daz_import.Lib.Utility import PropsStatic
from daz_import.Lib.VectorStatic import VectorStatic

# ----------------------------------------------------------
#   Panels
# ----------------------------------------------------------


class DAZ_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAZ Importer"
    bl_options = {'DEFAULT_CLOSED'}

# ----------------------------------------------------------
#   Setup panel
# ----------------------------------------------------------


@Registrar()
class DAZ_PT_Setup(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Setup (version 1.6.1.%04d)" % Settings.BUILD_
    bl_options = set()

    def draw(self, context):
        scn = context.scene
        self.layout.operator("daz.daz_import")
        self.layout.separator()
        self.layout.operator("daz.easy_import_daz")
        self.layout.prop(scn, "DazFavoPath")
        self.layout.separator()
        self.layout.operator("daz.global_settings")


@Registrar()
class DAZ_PT_SetupCorrections(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupCorrections"
    bl_label = "Corrections"

    def draw(self, context):
        self.layout.operator("daz.eliminate_empties")
        self.layout.operator("daz.merge_rigs")
        self.layout.operator("daz.merge_toes")
        self.layout.separator()
        self.layout.operator("daz.copy_pose")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.change_armature")


@Registrar()
class DAZ_PT_SetupMaterials(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.update_settings")
        self.layout.operator("daz.save_local_textures")
        self.layout.operator("daz.resize_textures")
        self.layout.operator("daz.change_resolution")

        self.layout.separator()
        self.layout.operator("daz.change_colors")
        self.layout.operator("daz.change_skin_color")
        self.layout.operator("daz.merge_materials")
        self.layout.operator("daz.copy_materials")
        self.layout.operator("daz.prune_node_trees")

        self.layout.separator()
        self.layout.operator("daz.launch_editor")
        self.layout.operator("daz.reset_material")


@Registrar()
class DAZ_PT_SetupMorphs(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        ob = context.object
        if ob and ob.DazDriversDisabled:
            self.layout.label(text="Morph Drivers Disabled")
            self.layout.operator("daz.enable_drivers")
        elif ob and ob.type in ['ARMATURE', 'MESH']:
            if ob.DazMorphPrefixes:
                self.layout.label(text="Object with obsolete morphs")
                return
            self.layout.operator("daz.import_units")
            self.layout.operator("daz.import_expressions")
            self.layout.operator("daz.import_visemes")
            self.layout.operator("daz.import_facs")
            self.layout.operator("daz.import_facs_expressions")
            self.layout.operator("daz.import_body_morphs")
            self.layout.separator()
            self.layout.operator("daz.import_jcms")
            self.layout.operator("daz.import_flexions")
            self.layout.separator()
            self.layout.operator("daz.import_standard_morphs")
            self.layout.operator("daz.import_custom_morphs")
            self.layout.separator()
            self.layout.operator("daz.save_favo_morphs")
            self.layout.operator("daz.load_favo_morphs")
            self.layout.separator()
            self.layout.label(text="Create low-poly meshes before transfers.")
            self.layout.operator("daz.transfer_shapekeys")
            self.layout.operator("daz.apply_all_shapekeys")
            self.layout.operator("daz.mix_shapekeys")


@Registrar()
class DAZ_PT_SetupFinishing(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupFinishing"
    bl_label = "Finishing"

    def draw(self, context):
        self.layout.operator("daz.merge_geografts")
        self.layout.operator("daz.merge_uv_layers")
        if bpy.app.version >= (2, 82, 0):
            self.layout.operator("daz.set_udims")
            self.layout.operator("daz.make_udim_materials")
        self.layout.operator("daz.convert_widgets")
        self.layout.operator("daz.finalize_meshes")
        self.layout.separator()
        self.layout.operator("daz.make_all_bones_poseable")
        self.layout.operator("daz.optimize_pose")
        self.layout.operator("daz.apply_rest_pose")
        self.layout.operator("daz.connect_ik_chains")


@Registrar()
class DAZ_PT_SetupRigging(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Setup"
    bl_idname = "DAZ_PT_SetupRigging"
    bl_label = "Rigging"

    def draw(self, context):
        self.layout.operator("daz.add_custom_shapes")
        self.layout.operator("daz.add_simple_ik")
        self.layout.separator()
        self.layout.operator("daz.convert_to_mhx")
        self.layout.separator()
        self.layout.operator("daz.convert_to_rigify")
        self.layout.operator("daz.create_meta")
        self.layout.operator("daz.rigify_meta")
        self.layout.separator()
        self.layout.operator("daz.add_mannequin")

# ----------------------------------------------------------
#   Advanced setup panel
# ----------------------------------------------------------


@Registrar()
class DAZ_PT_Advanced(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Advanced Setup"

    def draw(self, context):
        pass


@Registrar()
class DAZ_PT_AdvancedLowpoly(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedLowpoly"
    bl_label = "Lowpoly"

    def draw(self, context):
        self.layout.operator("daz.print_statistics")
        self.layout.separator()
        self.layout.operator("daz.apply_morphs")
        self.layout.operator("daz.make_quick_proxy")
        self.layout.separator()
        self.layout.operator("daz.make_faithful_proxy")
        self.layout.operator("daz.split_ngons")
        self.layout.operator("daz.quadify")
        self.layout.separator()
        self.layout.operator("daz.add_push")


@Registrar()
class DAZ_PT_AdvancedVisibility(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedVisibility"
    bl_label = "Visibility"

    def draw(self, context):
        self.layout.operator("daz.add_shrinkwrap")
        self.layout.operator("daz.create_masks")
        self.layout.operator("daz.add_visibility_drivers")
        self.layout.operator("daz.remove_visibility_drivers")


@Registrar()
class DAZ_PT_AdvancedHDMesh(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedHDMesh"
    bl_label = "HDMesh"

    def draw(self, context):
        if bpy.app.version >= (2, 90, 0):
            self.layout.operator("daz.make_multires")
            self.layout.separator()
        if bpy.app.version >= (2, 82, 0):
            self.layout.operator("daz.bake_maps")
            self.layout.operator("daz.load_baked_maps")
            self.layout.separator()
        self.layout.operator("daz.load_normal_map")
        self.layout.operator("daz.load_scalar_disp")
        self.layout.operator("daz.load_vector_disp")
        self.layout.operator("daz.add_driven_value_nodes")


@Registrar()
class DAZ_PT_AdvancedMaterials(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMaterials"
    bl_label = "Materials"

    def draw(self, context):
        self.layout.operator("daz.load_uv")
        self.layout.operator("daz.prune_uv_maps")
        self.layout.separator()
        self.layout.operator("daz.collapse_udims")
        self.layout.operator("daz.restore_udims")
        self.layout.operator("daz.udims_from_textures")
        self.layout.separator()
        self.layout.operator("daz.remove_shells")
        self.layout.operator("daz.replace_shells")
        self.layout.separator()
        self.layout.operator("daz.make_decal")
        self.layout.operator("daz.make_shader_groups")


@Registrar()
class DAZ_PT_AdvancedMesh(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMesh"
    bl_label = "Mesh"

    def draw(self, context):
        self.layout.operator("daz.limit_vertex_groups")
        self.layout.operator("daz.prune_vertex_groups")
        self.layout.operator("daz.create_graft_groups")
        self.layout.operator("daz.transfer_vertex_groups")
        self.layout.operator("daz.apply_subsurf")
        self.layout.operator("daz.copy_modifiers")
        self.layout.operator("daz.find_seams")
        self.layout.operator("daz.separate_loose_parts")
        self.layout.operator("daz.mesh_add_pinning")


@Registrar()
class DAZ_PT_AdvancedSimulation(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedSimulation"
    bl_label = "Simulation"

    def draw(self, context):
        self.layout.operator("daz.make_simulation")
        self.layout.separator()
        self.layout.operator("daz.make_deflection")
        self.layout.operator("daz.make_collision")
        self.layout.operator("daz.make_cloth")


@Registrar()
class DAZ_PT_AdvancedRigging(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedRigging"
    bl_label = "Rigging"

    def draw(self, context):
        self.layout.operator("daz.change_unit_scale")
        self.layout.operator("daz.remove_custom_shapes")
        self.layout.operator("daz.copy_daz_props")
        self.layout.operator("daz.convert_rig")
        self.layout.operator("daz.add_extra_face_bones")
        self.layout.separator()
        self.layout.operator("daz.add_ik_goals")
        self.layout.operator("daz.add_winders")
        self.layout.operator("daz.change_prefix_to_suffix")
        self.layout.operator("daz.lock_bones")
        self.layout.separator()
        self.layout.operator("daz.categorize_objects")


@Registrar()
class DAZ_PT_AdvancedMorphs(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedMorphs"
    bl_label = "Morphs"

    def draw(self, context):
        self.layout.operator("daz.add_shape_to_category")
        self.layout.operator("daz.remove_shape_from_category")
        self.layout.operator("daz.rename_category")
        self.layout.operator("daz.remove_categories")
        self.layout.separator()
        self.layout.operator("daz.convert_morphs_to_shapekeys")
        self.layout.operator("daz.transfer_mesh_to_shape")
        self.layout.separator()
        self.layout.operator("daz.add_shapekey_drivers")
        self.layout.operator("daz.remove_shapekey_drivers")
        self.layout.operator("daz.remove_all_drivers")
        self.layout.separator()
        self.layout.operator("daz.copy_props")
        self.layout.operator("daz.copy_bone_drivers")
        self.layout.operator("daz.retarget_mesh_drivers")
        self.layout.separator()
        self.layout.operator("daz.update_slider_limits")
        self.layout.operator("daz.import_dbz")
        self.layout.operator("daz.update_morph_paths")


@Registrar()
class DAZ_PT_AdvancedHair(DAZ_PT_Base, bpy.types.Panel):
    bl_parent_id = "DAZ_PT_Advanced"
    bl_idname = "DAZ_PT_AdvancedHair"
    bl_label = "Hair"

    def draw(self, context):
        from daz_import.Elements.Hair import HairStatic

        self.layout.operator("daz.print_statistics")
        self.layout.operator("daz.select_strands_by_size")
        self.layout.operator("daz.select_strands_by_width")
        self.layout.operator("daz.select_random_strands")
        self.layout.separator()
        self.layout.operator("daz.make_hair")

        hair, hum = HairStatic.getHairAndHuman(context, False)

        self.layout.label(text="  Hair:  %s" % (hair.name if hair else None))
        self.layout.label(text="  Human: %s" % (hum.name if hum else None))
        self.layout.separator()
        self.layout.operator("daz.update_hair")
        self.layout.operator("daz.color_hair")
        self.layout.operator("daz.combine_hairs")

# ----------------------------------------------------------
#   Utilities panel
# ----------------------------------------------------------


@Registrar()
class DAZ_PT_Utils(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Utilities"

    def draw(self, context):
        ob = context.object
        scn = context.scene
        layout = self.layout
        layout.operator("daz.decode_file")
        layout.operator("daz.quote_unquote")
        layout.operator("daz.print_statistics")
        layout.operator("daz.update_all")
        layout.separator()
        box = layout.box()
        if ob:
            box.label(text="Active Object: %s" % ob.type)
            box.prop(ob, "name")
            box.prop(ob, "DazBlendFile")
            box.prop(ob, "DazId")
            box.prop(ob, "DazUrl")
            box.prop(ob, "DazScene")
            box.prop(ob, "DazRig")
            box.prop(ob, "DazMesh")
            if ob.type == 'MESH':
                box.prop(ob.data, "DazFingerPrint")
            box.prop(ob, "DazScale")
            factor = 1/ob.DazScale
        else:
            box.label(text="No active object")
            factor = 1
        layout.separator()
        pb = context.active_pose_bone
        box = layout.box()
        if pb:
            box.label(text="Active Bone: %s" % pb.bone.name)
            self.propRow(box, pb.bone, "DazHead")
            self.propRow(box, pb.bone, "DazTail")
            self.propRow(box, pb.bone, "DazOrient")
            self.propRow(box, pb, "DazRotMode")
            self.propRow(box, pb, "DazLocLocks")
            self.propRow(box, pb, "DazRotLocks")
            mat = ob.matrix_world @ pb.matrix
            loc, quat, scale = mat.decompose()
            self.vecRow(box, factor*loc, "Location")
            self.vecRow(box, Vector(quat.to_euler()) /
                        VectorStatic.D, "Rotation")
            self.vecRow(box, scale, "Scale")
        else:
            box.label(text="No active bone")

        layout.separator()
        icon = 'CHECKBOX_HLT' if Settings.theSilentMode_ else 'CHECKBOX_DEHLT'
        layout.operator("daz.set_silent_mode", icon=icon, emboss=False)
        layout.operator("daz.get_finger_print")
        layout.operator("daz.inspect_world_matrix")
        layout.operator("daz.enable_all_layers")

    def propRow(self, layout, rna, prop):
        row = layout.row()
        row.label(text=prop[3:])
        attr = getattr(rna, prop)
        for n in range(3):
            if isinstance(attr[n], float):
                row.label(text="%.3f" % attr[n])
            else:
                row.label(text=str(attr[n]))

    def vecRow(self, layout, vec, text):
        row = layout.row()
        row.label(text=text)
        for n in range(3):
            row.label(text="%.3f" % vec[n])

# ----------------------------------------------------------
#   Posing panel
# ----------------------------------------------------------


@Registrar()
class DAZ_PT_Posing(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Posing"

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type in ['ARMATURE', 'MESH'])

    def draw(self, context):
        from daz_import.Elements.Morph import getRigFromObject
        ob = context.object
        rig = getRigFromObject(ob)
        if rig is None:
            return
        scn = context.scene
        layout = self.layout

        layout.operator("daz.import_pose")
        layout.operator("daz.import_poselib")
        layout.operator("daz.import_action")
        layout.separator()
        layout.operator("daz.import_node_pose")
        layout.separator()
        layout.operator("daz.clear_pose")
        op = layout.operator("daz.clear_morphs")
        op.morphset = "All"
        op.category = ""
        if rig.DazDriversDisabled:
            layout.operator("daz.enable_drivers")
        else:
            layout.operator("daz.disable_drivers")
        layout.operator("daz.prune_action")
        layout.separator()
        layout.operator("daz.impose_locks_limits")
        layout.operator("daz.bake_pose_to_fk_rig")
        layout.operator("daz.save_pose_preset")

        layout.separator()
        prop = "Adjust Morph Strength"
        if prop in rig.keys():
            layout.prop(rig, PropsStatic.ref(prop))
        split = layout.split(factor=0.6)
        layout.prop(rig, "DazLocLocks")
        layout.prop(rig, "DazRotLocks")
        layout.prop(rig, "DazLocLimits")
        layout.prop(rig, "DazRotLimits")

        return
        layout.separator()
        layout.operator("daz.save_poses")
        layout.operator("daz.load_poses")
        layout.separator()
        layout.operator("daz.rotate_bones")

# ----------------------------------------------------------
#   Morphs panel
# ----------------------------------------------------------


class DAZ_PT_Morphs:
    useMesh = False

    @classmethod
    def poll(self, context):
        rig = self.getCurrentRig(self, context)
        return (rig and
                not rig.DazDriversDisabled and
                (self.hasTheseMorphs(self, rig) or self.hasAdjustProp(self, rig)))

    def getCurrentRig(self, context):
        rig = context.object
        if rig is None:
            return None
        elif rig.type == 'MESH':
            rig = rig.parent
        if rig and rig.type == 'ARMATURE':
            return rig
        else:
            return None

    def hasTheseMorphs(self, rig):
        return getattr(rig, "Daz"+self.morphset)

    def hasAdjustProp(self, rig):
        from daz_import.Elements.Morph import theAdjusters
        adj = theAdjusters[self.morphset]
        return (adj in rig.keys())

    def draw(self, context):
        scn = context.scene
        rig = self.getCurrentRig(context)
        from daz_import.Elements.Morph import theAdjusters
        adj = theAdjusters[self.morphset]
        if adj in rig.keys():
            self.layout.prop(rig, PropsStatic.ref(adj))
        if not self.hasTheseMorphs(rig):
            return
        self.preamble(self.layout, rig)
        self.drawItems(scn, rig)

    def preamble(self, layout, rig):
        self.activateLayout(layout, "", rig)
        self.keyLayout(layout, "")

    def activateLayout(self, layout, category, rig):
        split = layout.split(factor=0.333)
        op = split.operator("daz.activate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op = split.operator("daz.deactivate_all")
        op.morphset = self.morphset
        op.category = category
        op.useMesh = self.useMesh
        op = split.operator("daz.set_morphs")
        op.morphset = self.morphset
        op.category = category

    def keyLayout(self, layout, category):
        split = layout.split(factor=0.25)
        op = split.operator("daz.add_keyset", text="", icon='KEYINGSET')
        op.morphset = self.morphset
        op.category = category
        op = split.operator("daz.key_morphs", text="", icon='KEY_HLT')
        op.morphset = self.morphset
        op.category = category
        op = split.operator("daz.unkey_morphs", text="", icon='KEY_DEHLT')
        op.morphset = self.morphset
        op.category = category
        op = split.operator("daz.clear_morphs", text="", icon='X')
        op.morphset = self.morphset
        op.category = category

    def drawItems(self, scn, rig):
        self.layout.prop(scn, "DazFilter", icon='VIEWZOOM', text="")
        self.layout.separator()
        filter = scn.DazFilter.lower()
        pg = getattr(rig, "Daz"+self.morphset)
        items = [(data[1].text, n, data[1])
                 for n, data in enumerate(pg.items())]
        items.sort()
        for _, _, item in items:
            if filter in item.text.lower():
                self.displayProp(item, "", rig, rig.data, self.layout, scn)

    def showBool(self, layout, ob, key, text=""):
        from daz_import.Elements.Morph import getExistingActivateGroup
        pg = getExistingActivateGroup(ob, key)
        if pg is not None:
            layout.prop(pg, "active", text=text)

    def displayProp(self, morph, category, rig, amt, layout, scn):
        key = morph.name
        if key not in rig.keys():
            return
        split = layout.split(factor=0.8)
        final = PropsStatic.final(key)
        if Settings.showFinalProps and final in amt.keys():
            split2 = split.split(factor=0.8)
            split2.prop(rig, PropsStatic.ref(key), text=morph.text)
            split2.label(text="%.3f" % amt[final])
        else:
            split.prop(rig, PropsStatic.ref(key), text=morph.text)
        row = split.row()
        self.showBool(row, rig, key)
        op = row.operator("daz.pin_prop", icon='UNPINNED')
        op.key = key
        op.morphset = self.morphset
        op.category = category


@Registrar()
class DAZ_PT_MorphGroup(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Morphs"
    morphset = "All"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        rig = self.getCurrentRig(context)
        if not rig:
            return
        if rig.DazDriversDisabled:
            self.layout.label(text="Morph Drivers Disabled")
            self.layout.operator("daz.enable_drivers")
            return
        else:
            self.layout.operator("daz.disable_drivers")
        self.preamble(self.layout, rig)
        self.layout.operator("daz.morph_armature")


@Registrar()
class DAZ_PT_Standard(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Unclassified Standard Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Standard"


@Registrar()
class DAZ_PT_Units(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Face Units"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Units"


@Registrar()
class DAZ_PT_Head(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Head"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Head"


@Registrar()
class DAZ_PT_Expressions(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Expressions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Expressions"


@Registrar()
class DAZ_PT_Visemes(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Visemes"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Visemes"

    def draw(self, context):
        self.layout.operator("daz.load_moho")
        DAZ_PT_Morphs.draw(self, context)


@Registrar()
class DAZ_PT_FacsUnits(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "FACS Units"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facs"

    def preamble(self, layout, rig):
        layout.operator("daz.import_facecap")
        layout.operator("daz.import_livelink")
        DAZ_PT_Morphs.preamble(self, layout, rig)


@Registrar()
class DAZ_PT_FacsExpressions(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "FACS Expressions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Facsexpr"


@Registrar()
class DAZ_PT_BodyMorphs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Body Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Body"


@Registrar()
class DAZ_PT_JCMs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "JCMs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Jcms"


@Registrar()
class DAZ_PT_Flexions(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs):
    bl_label = "Flexions"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Flexions"

# ------------------------------------------------------------------------
#    Custom panels
# ------------------------------------------------------------------------


class CustomDrawItems:
    def drawItems(self, scn, ob):
        row = self.layout.row()
        op = row.operator("daz.toggle_all_cats", text="Open All Categories")
        op.useOpen = True
        op.useMesh = self.useMesh
        op = row.operator("daz.toggle_all_cats", text="Close All Categories")
        op.useOpen = False
        op.useMesh = self.useMesh
        self.layout.separator()
        filter = scn.DazFilter.lower()

        for cat in ob.DazMorphCats:
            box = self.layout.box()
            if not cat.active:
                box.prop(cat, "active", text=cat.name,
                         icon="RIGHTARROW", emboss=False)
                continue
            box.prop(cat, "active", text=cat.name,
                     icon="DOWNARROW_HLT", emboss=False)
            self.drawCustomBox(box, cat, scn, ob, filter)


@Registrar()
class DAZ_PT_CustomMorphs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs, CustomDrawItems):
    bl_label = "Custom Morphs"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"

    def hasTheseMorphs(self, ob):
        return ob.DazCustomMorphs

    def preamble(self, layout, rig):
        pass

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob

    def drawCustomBox(self, box, cat, scn, rig, filter):
        adj = "Adjust Custom/%s" % cat.name
        if adj in rig.keys():
            box.prop(rig, PropsStatic.ref(adj))
        if len(cat.morphs) == 0:
            return
        self.activateLayout(box, cat.name, rig)
        self.keyLayout(box, cat.name)
        box.prop(scn, "DazFilter", icon='VIEWZOOM', text="")
        for morph in cat.morphs:
            if (morph.name in rig.keys() and
                    filter in morph.text.lower()):
                self.displayProp(morph, cat.name, rig, rig.data, box, scn)


@Registrar()
class DAZ_PT_CustomMeshMorphs(DAZ_PT_Base, bpy.types.Panel, DAZ_PT_Morphs, CustomDrawItems):
    bl_label = "Mesh Shape Keys"
    bl_parent_id = "DAZ_PT_MorphGroup"
    morphset = "Custom"
    useMesh = True

    @classmethod
    def poll(self, context):
        ob = context.object
        return (ob and ob.type == 'MESH' and self.hasTheseMorphs(self, ob))

    def hasTheseMorphs(self, ob):
        return (ob.DazMeshMorphs or len(ob.DazAutoFollow) > 0)

    def draw(self, context):
        ob = context.object
        skeys = ob.data.shape_keys
        if skeys and len(ob.DazAutoFollow) > 0:
            box = self.layout.box()
            box.label(text="Auto Follow")
            for item in ob.DazAutoFollow:
                sname = item.name
                if (sname in ob.keys() and
                        sname in skeys.key_blocks.keys()):
                    skey = skeys.key_blocks[sname]
                    self.drawAutoItem(box, ob, skey, sname, item.text)
            self.layout.separator()
        if ob.DazMeshMorphs:
            DAZ_PT_Morphs.draw(self, context)

    def drawAutoItem(self, layout, ob, skey, sname, text):
        if Settings.showFinalProps:
            split = layout.split(factor=0.8)
            split.prop(ob, PropsStatic.ref(sname), text=text)
            split.label(text="%.3f" % skey.value)
        else:
            layout.prop(ob, PropsStatic.ref(sname), text=text)

    def getCurrentRig(self, context):
        return context.object

    def drawItems(self, scn, ob):
        CustomDrawItems.drawItems(self, scn, ob)

    def getRna(self, ob):
        return ob.data.shape_keys

    def keyLayout(self, layout, category):
        split = layout.split(factor=0.333)
        op = split.operator("daz.key_shapes", text="", icon='KEY_HLT')
        op.category = category
        op = split.operator("daz.unkey_shapes", text="", icon='KEY_DEHLT')
        op.category = category
        op = split.operator("daz.clear_shapes", text="", icon='X')
        op.category = category

    def drawCustomBox(self, box, cat, scn, ob, filter):
        skeys = ob.data.shape_keys
        if skeys is None:
            return
        self.activateLayout(box, cat.name, ob)
        self.keyLayout(box, cat.name)
        for morph in cat.morphs:
            if (morph.name in skeys.key_blocks.keys() and
                    filter in morph.text.lower()):
                skey = skeys.key_blocks[morph.name]
                self.displayProp(morph, cat.name, ob, skey, box, scn)

    def displayProp(self, morph, category, ob, skey, layout, scn):
        key = morph.name
        row = layout.split(factor=0.8)
        row.prop(skey, "value", text=morph.text)
        self.showBool(row, ob, key)
        op = row.operator("daz.pin_shape", icon='UNPINNED')
        op.key = key
        op.category = category

# ------------------------------------------------------------------------
#    Simple IK Panel
# ------------------------------------------------------------------------


@Registrar()
class DAZ_PT_SimpleRig(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Simple Rig"

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.DazCustomShapes)

    def draw(self, context):
        amt = context.object.data
        self.drawLayers(amt)
        if amt.DazSimpleIK:
            self.drawSimpleIK(amt)

    def drawSimpleIK(self, amt):
        layout = self.layout
        layout.separator()
        layout.label(text="IK Influence")
        split = layout.split(factor=0.2)
        split.label(text="")
        split.label(text="Left")
        split.label(text="Right")
        split = layout.split(factor=0.2)
        split.label(text="Arm")
        split.prop(amt, "DazArmIK_L", text="")
        split.prop(amt, "DazArmIK_R", text="")
        split = layout.split(factor=0.2)
        split.label(text="Leg")
        split.prop(amt, "DazLegIK_L", text="")
        split.prop(amt, "DazLegIK_R", text="")

        layout.label(text="Snap FK bones")
        row = layout.row()
        op = row.operator("daz.snap_simple_fk", text="Left Arm")
        op.prefix = "l"
        op.type = "Arm"
        op = row.operator("daz.snap_simple_fk", text="Right Arm")
        op.prefix = "r"
        op.type = "Arm"
        row = layout.row()
        op = row.operator("daz.snap_simple_fk", text="Left Leg")
        op.prefix = "l"
        op.type = "Leg"
        op = row.operator("daz.snap_simple_fk", text="Right Leg")
        op.prefix = "r"
        op.type = "Leg"

        layout.label(text="Snap IK bones")
        row = layout.row()
        op = row.operator("daz.snap_simple_ik", text="Left Arm")
        op.prefix = "l"
        op.type = "Arm"
        op = row.operator("daz.snap_simple_ik", text="Right Arm")
        op.prefix = "r"
        op.type = "Arm"
        row = layout.row()
        op = row.operator("daz.snap_simple_ik", text="Left Leg")
        op.prefix = "l"
        op.type = "Leg"
        op = row.operator("daz.snap_simple_ik", text="Right Leg")
        op.prefix = "r"
        op.type = "Leg"

    def drawLayers(self, amt):
        from daz_import.figure import BoneLayers
        layout = self.layout
        layout.label(text="Layers")
        row = layout.row()
        row.operator("daz.select_named_layers")
        row.operator("daz.unselect_named_layers")
        layout.separator()
        for lnames in [("Spine", "Face"), "FK Arm", "IK Arm", "FK Leg", "IK Leg", "Hand", "Foot"]:
            row = layout.row()
            if isinstance(lnames, str):
                first, second = "Left "+lnames, "Right "+lnames
            else:
                first, second = lnames
            m = BoneLayers[first]
            n = BoneLayers[second]
            row.prop(amt, "layers", index=m, toggle=True, text=first)
            row.prop(amt, "layers", index=n, toggle=True, text=second)

# ------------------------------------------------------------------------
#   Visibility panels
# ------------------------------------------------------------------------


@Registrar()
class DAZ_PT_Visibility(DAZ_PT_Base, bpy.types.Panel):
    bl_label = "Visibility"
    prefix = "Mhh"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and ob.DazVisibilityDrivers)

    def draw(self, context):
        ob = rig = context.object
        scn = context.scene
        if ob.type == 'MESH':
            self.layout.operator("daz.set_shell_visibility")
            self.layout.separator()
            if ob.parent and ob.parent.type == 'ARMATURE':
                rig = ob.parent
            else:
                return
        split = self.layout.split(factor=0.3333)
        split.operator("daz.prettify")
        split.operator("daz.show_all_vis")
        split.operator("daz.hide_all_vis")
        props = list(rig.keys())
        props.sort()
        self.drawProps(rig, props, "Mhh")
        self.drawProps(rig, props, "DzS")

    def drawProps(self, rig, props, prefix):
        for prop in props:
            if prop[0:3] == prefix:
                icon = 'CHECKBOX_HLT' if rig[prop] else 'CHECKBOX_DEHLT'
                op = self.layout.operator(
                    "daz.toggle_vis", text=prop[3:], icon=icon, emboss=False)
                op.name = prop

# ------------------------------------------------------------------------
#   DAZ Rigify props panels
# ------------------------------------------------------------------------


@Registrar()
class DAZ_PT_DazRigifyProps(bpy.types.Panel):
    bl_label = "DAZ Rigify Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob and
                ob.DazRig in ["rigify", "rigify2"] and
                "MhaGazeFollowsHead" in ob.data.keys())

    def draw(self, context):
        amt = context.object.data
        self.layout.prop(amt, PropsStatic.ref("MhaGazeFollowsHead"),
                         text="Gaze Follows Head")
        self.layout.prop(amt, PropsStatic.ref("MhaGaze_L"), text="Left Gaze")
        self.layout.prop(amt, PropsStatic.ref("MhaGaze_R"), text="Right Gaze")
