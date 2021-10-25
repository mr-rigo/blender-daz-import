
import bpy
import os
from mathutils import Vector

from daz_import.Lib.Errors import *
from daz_import.utils import *
from daz_import.Elements.Color import ColorStatic
from daz_import.Lib.Files import SingleFile, ImageFile
from daz_import.Lib.Registrar import Registrar
from daz_import.Elements.Material import TweakableChannels, MaterialStatic, MaterialSelector
from daz_import.Elements.Morph import Selector

# OtherOperators


@Registrar()
class DAZ_OT_SelectAllMaterials(bpy.types.Operator):
    bl_idname = "daz.select_all_materials"
    bl_label = "All"
    bl_description = "Select all materials"

    def execute(self, context):
        MaterialStatic.getMaterialSelector().selectAll(context)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_SelectSkinMaterials(bpy.types.Operator):
    bl_idname = "daz.select_skin_materials"
    bl_label = "Skin"
    bl_description = "Select skin materials"

    def execute(self, context):
        MaterialStatic.getMaterialSelector().selectSkin(context)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_SelectSkinRedMaterials(bpy.types.Operator):
    bl_idname = "daz.select_skin_red_materials"
    bl_label = "Skin-Lips-Nails"
    bl_description = "Select all skin or red materials"

    def execute(self, context):
        MaterialStatic.getMaterialSelector().selectSkinRed(context)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_SelectNoMaterial(bpy.types.Operator):
    bl_idname = "daz.select_no_material"
    bl_label = "None"
    bl_description = "Select no material"

    def execute(self, context):
        MaterialStatic.getMaterialSelector().selectNone(context)
        return {'PASS_THROUGH'}


@Registrar()
class EditSlotGroup(bpy.types.PropertyGroup):
    ncomps: IntProperty(default=0)

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=4,
        min=0.0, max=1.0,
        default=(1, 1, 1, 1)
    )

    vector: FloatVectorProperty(
        name="Vector",
        size=3,
        precision=4,
        min=0.0,
        default=(0, 0, 0)
    )

    number: FloatProperty(default=0.0, precision=4)
    new: BoolProperty()


@Registrar()
class ShowGroup(bpy.types.PropertyGroup):
    show: BoolProperty(default=False)


class LaunchEditor:
    shows: CollectionProperty(type=ShowGroup)


class ChannelSetter:
    def setChannelCycles(self, mat, item):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels.channel(
            item.name)

        for node in mat.node_tree.nodes.values():
            if self.matchingNode(node, nodeType, mat, fromType):
                socket = node.inputs[slot]
                self.setOriginal(socket, ncomps, mat, item.name)
                self.setSocket(socket, ncomps, item)
                fromnode, fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type in "MIX_RGB":
                        self.ensureColor(ncomps, item)
                        self.setSocket(fromnode.inputs[1], 4, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        self.setSocket(fromnode.inputs[0], 1, item)
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY_ADD':
                        self.setSocket(fromnode.inputs[1], 1, item)
                    elif fromnode.type in ["TEX_IMAGE", "GAMMA"]:
                        self.multiplyTex(node, fromsocket,
                                         socket, mat.node_tree, item)

    def ensureColor(self, ncomps, item):
        if ncomps == 1:
            ncomps = 4
            num = item.number
            item.color = (num, num, num, 1)

    def setSocket(self, socket, ncomps, item):
        if item.ncomps == 1:
            socket.default_value = self.getValue(item.number, ncomps)
        elif item.ncomps == 3:
            socket.default_value = self.getValue(item.vector, ncomps)
        elif item.ncomps == 4:
            socket.default_value = self.getValue(item.color, ncomps)

    def addSlots(self, context):
        ob = context.object
        ob.DazSlots.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                continue
            value, ncomps = self.getChannel(ob, key)
            if ncomps == 0:
                continue
            item = ob.DazSlots.add()
            item.name = key
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)

    def getChannel(self, ob, key):
        nodeType, slot, useAttr, factorAttr, ncomps, fromType = TweakableChannels.channel(
            key)
        mat = ob.active_material
        if mat.use_nodes:
            return self.getChannelCycles(mat, nodeType, slot, ncomps, fromType)
        else:
            return None, 0

    def getChannelCycles(self, mat, nodeType, slot, ncomps, fromType):
        for node in mat.node_tree.nodes.values():
            if (self.matchingNode(node, nodeType, mat, fromType) and
                    slot in node.inputs.keys()):
                socket = node.inputs[slot]
                fromnode, fromsocket = self.getFromNode(mat, node, socket)
                if fromnode:
                    if fromnode.type == "MIX_RGB":
                        return fromnode.inputs[1].default_value, ncomps
                    elif fromnode.type == "MATH" and fromnode.operation == 'MULTIPLY':
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == "GAMMA":
                        return fromnode.inputs[0].default_value, ncomps
                    elif fromnode.type == "TEX_IMAGE":
                        return ColorStatic.WHITE, ncomps
                else:
                    return socket.default_value, ncomps
        return None, 0

    def getValue(self, value, ncomps):
        if ncomps == 1:
            if isinstance(value, float):
                return value
            else:
                return value[0]
        elif ncomps == 3:
            if isinstance(value, float):
                return (value, value, value)
            elif len(value) == 3:
                return value
            elif len(value) == 4:
                return value[0:3]
        elif ncomps == 4:
            if isinstance(value, float):
                return (value, value, value, 1)
            elif len(value) == 3:
                return (value[0], value[1], value[2], 1)
            elif len(value) == 4:
                return value

    def inputDiffers(self, node, slot, value):
        if slot in node.inputs.keys():
            if node.inputs[slot].default_value != value:
                return True
        return False

    def getFromNode(self, mat, node, socket):
        for link in mat.node_tree.links.values():
            if link.to_node == node and link.to_socket == socket:
                return (link.from_node, link.from_socket)
        return None, None

    def matchingNode(self, node, nodeType, mat, fromType):
        if node.type == nodeType:
            if fromType is None:
                return True
            for link in mat.node_tree.links.values():
                if link.to_node == node and link.from_node.type == fromType:
                    return True
            return False
        elif (node.type == "GROUP" and
              nodeType in bpy.data.node_groups.keys()):
            return (node.node_tree == bpy.data.node_groups[nodeType])
        return False


@Registrar()
class DAZ_OT_LaunchEditor(DazPropsOperator, MaterialSelector, ChannelSetter, LaunchEditor):
    bl_idname = "daz.launch_editor"
    bl_label = "Launch Material Editor"
    bl_description = "Edit materials of selected meshes"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def draw(self, context):
        MaterialSelector.draw(self, context)
        ob = context.object
        self.layout.label(text="Active Material: %s" % ob.active_material.name)
        self.layout.separator()
        showing = False
        section = ""
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                section = key
                nchars = len(section)
                if self.shows[key].show:
                    self.layout.prop(
                        self.shows[key], "show", icon="DOWNARROW_HLT", emboss=False, text=key)
                else:
                    self.layout.prop(
                        self.shows[key], "show", icon="RIGHTARROW", emboss=False, text=key)
                showing = self.shows[key].show
            elif showing and key in ob.DazSlots.keys():
                item = ob.DazSlots[key]
                row = self.layout.row()
                if key[0:nchars] == section:
                    text = item.name[nchars+1:]
                else:
                    text = item.name
                row.label(text=text)
                if item.ncomps == 4:
                    row.prop(item, "color", text="")
                elif item.ncomps == 1:
                    row.prop(item, "number", text="")
                elif item.ncomps == 3:
                    row.prop(item, "vector", text="")
                else:
                    print("WAHT")
        self.layout.operator("daz.update_materials")

    def invoke(self, context, event):
        global theMaterialEditor
        theMaterialEditor = self
        ob = context.object
        self.setupMaterials(ob)
        self.shows.clear()
        for key in TweakableChannels.keys():
            if TweakableChannels[key] is None:
                item = self.shows.add()
                item.name = key
                item.show = False
                continue
        self.addSlots(context)
        wm = context.window_manager
        return wm.invoke_popup(self, width=300)

    def isDefaultActive(self, mat):
        return self.isSkinRedMaterial(mat)

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            for item in ob.DazSlots:
                self.setChannel(ob, item)

    def setChannel(self, ob, item):
        for mat in ob.data.materials:
            if mat and self.useMaterial(mat):
                self.setChannelCycles(mat, item)

    def getObjectSlot(self, mat, key):
        for item in mat.DazSlots:
            if item.name == key:
                return item
        item = mat.DazSlots.add()
        item.name = key
        item.new = True
        return item

    def setOriginal(self, socket, ncomps, mat, key):
        item = self.getObjectSlot(mat, key)
        if item.new:
            value = socket.default_value
            item.ncomps = ncomps
            if ncomps == 1:
                item.number = self.getValue(value, 1)
            elif ncomps == 3:
                item.vector = self.getValue(value, 3)
            elif ncomps == 4:
                item.color = self.getValue(value, 4)
            item.new = False

    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        from daz_import.Elements.Material.Cycles import XSIZE, YSIZE
        x, y = node.location
        if item.ncomps == 4 and not ColorStatic.isWhite(item.color):
            mix = tree.nodes.new(type="ShaderNodeMixRGB")
            mix.location = (x-XSIZE+50, y-YSIZE-50)
            mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0
            mix.inputs[1].default_value = item.color
            tree.link(fromsocket, mix.inputs[2])
            tree.link(mix.outputs[0], tosocket)
            return mix
        elif item.ncomps == 1 and item.number != 1.0:
            mult = tree.nodes.new(type="ShaderNodeMath")
            mult.location = (x-XSIZE+50, y-YSIZE-50)
            mult.operation = 'MULTIPLY'
            mult.inputs[0].default_value = item.number
            tree.link(fromsocket, mult.inputs[1])
            tree.link(mult.outputs[0], tosocket)
            return mult


@Registrar()
class DAZ_OT_UpdateMaterials(bpy.types.Operator):
    bl_idname = "daz.update_materials"
    bl_label = "Update Materials"
    bl_description = "Update Materials"

    def execute(self, context):
        global theMaterialEditor
        theMaterialEditor.run(context)
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_MakeDecal(DazOperator, ImageFile, SingleFile, LaunchEditor, IsMesh):
    bl_idname = "daz.make_decal"
    bl_label = "Make Decal"
    bl_description = "Add a decal to the active material"
    bl_options = {'UNDO'}

    channels = {
        "Diffuse Color": ("DIFFUSE", "Color", "Diffuse"),
        "Glossy Color": ("DAZ Glossy", "Color", "Glossy"),
        "Translucency Color": ("DAZ Translucent", "Color", "Translucency"),
        "Subsurface Color": ("DAZ SSS", "Color", "SSS"),
        "Principled Base Color": ("BSDF_PRINCIPLED", "Base Color", "Base"),
        "Principled Subsurface Color": ("BSDF_PRINCIPLED", "Subsurface Color", "SSS"),
        "Bump": ("BUMP", "Height", "Bump"),
    }

    def draw(self, context):
        ob = context.object
        mat = ob.data.materials[ob.active_material_index]
        self.layout.label(text="Material: %s" % mat.name)
        for item in self.shows:
            row = self.layout.row()
            row.prop(item, "show", text="")
            row.label(text=item.name)

    def invoke(self, context, event):
        if len(self.shows) == 0:
            for key in self.channels.keys():
                item = self.shows.add()
                item.name = key
                item.show = False
        return SingleFile.invoke(self, context, event)

    def run(self, context):
        from daz_import.Elements.ShaderGroup import DecalShaderGroup
        from daz_import.Elements.Material.Cycles import CyclesStatic, CyclesShader

        img = bpy.data.images.load(self.filepath)

        if img is None:
            raise DazError("Unable to load file %s" % self.filepath)

        img.colorspace_settings.name = "Non-Color"
        img.colorspace_settings.name = "sRGB"

        fname = os.path.splitext(os.path.basename(self.filepath))[0]
        ob = context.object

        mat = ob.data.materials[ob.active_material_index]

        tree = CyclesShader.create_shader(mat)
        coll = BlenderStatic.collection(ob)

        empty = bpy.data.objects.new(fname, None)
        coll.objects.link(empty)

        for item in self.shows:
            if item.show:
                nodeType, slot, cname = self.channels[item.name]
                fromSocket, toSocket = self.getFromToSockets(
                    tree, nodeType, slot)
                if toSocket is None:
                    print("Channel %s not found" % item.name)
                    continue
                nname = fname + "_" + cname
                node = tree.add_group(DecalShaderGroup, nname, col=3, args=[
                                     empty, img], force=True)
                node.inputs["Influence"].default_value = 1.0
                if fromSocket:
                    tree.link(fromSocket, node.inputs["Color"])
                    tree.link(node.outputs["Combined"], toSocket)
                else:
                    tree.link(node.outputs["Color"], toSocket)

    @staticmethod
    def getFromToSockets(shader, nodeType, slot):
        from daz_import.Elements.Material.Cycles import CyclesShader

        shader: CyclesShader

        for link in shader.links.values():
            if link.to_node and link.to_node.type == nodeType:
                if link.to_socket == link.to_node.inputs[slot]:
                    return link.from_socket, link.to_socket

        nodes = shader.find_nodes(nodeType)

        if nodes:
            return None, nodes[0].inputs[slot]

        return None, None


@Registrar()
class DAZ_OT_ResetMaterial(DazOperator, ChannelSetter):
    bl_idname = "daz.reset_material"
    bl_label = "Reset Material"
    bl_description = "Reset material to original"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def run(self, context):
        for ob in BlenderStatic.selected_meshes(context):
            self.resetObject(ob)

    def resetObject(self, ob):
        for mat in ob.data.materials:
            if mat:
                for item in mat.DazSlots:
                    self.setChannelCycles(mat, item)
                    item.new = True
                mat.DazSlots.clear()

    def setOriginal(self, socket, ncomps, item, key):
        pass

    def useMaterial(self, mat):
        return True

    def multiplyTex(self, node, fromsocket, tosocket, tree, item):
        pass


@Registrar()
class DAZ_OT_SetShellVisibility(DazPropsOperator):
    bl_idname = "daz.set_shell_visibility"
    bl_label = "Set Shell Visibility"
    bl_description = "Control the visility of geometry shells"
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    def draw(self, context):
        for item in context.scene.DazFloats:
            self.layout.prop(item, "f", text=item.name)

    def run(self, context):
        for item in context.scene.DazFloats:
            for node in self.shells[item.name]:
                node.inputs["Influence"].default_value = item.f

    def invoke(self, context, event):
        self.shells = {}
        scn = context.scene
        scn.DazFloats.clear()
        for ob in BlenderStatic.selected_meshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if (node.type == 'GROUP' and
                                "Influence" in node.inputs.keys()):
                            key = node.label
                            if key not in self.shells.keys():
                                self.shells[key] = []
                                item = scn.DazFloats.add()
                                item.name = key
                                item.f = node.inputs["Influence"].default_value
                            self.shells[key].append(node)
        return DazPropsOperator.invoke(self, context, event)


class ShellRemover:
    def getShells(self, context):
        ob = context.object
        self.shells = {}
        for mat in ob.data.materials:
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if (node.type == 'GROUP' and
                            "Influence" in node.inputs.keys()):
                        self.addShell(mat, node, node.node_tree)

    def addShell(self, mat, shell, tree):
        data = (mat, shell)
        if tree.name in self.shells.keys():
            struct = self.shells[tree.name]
            if mat.name in struct.keys():
                struct[mat.name].append(data)
            else:
                struct[mat.name] = [data]
        else:
            self.shells[tree.name] = {mat.name: [data]}

    def deleteNodes(self, mat, shell):
        print("Delete shell '%s' from material '%s'" % (shell.name, mat.name))
        linkFrom = {}
        linkTo = {}
        tree = mat.node_tree
        for link in tree.links:
            if link.to_node == shell:
                linkFrom[link.to_socket.name] = link.from_socket
            if link.from_node == shell:
                linkTo[link.from_socket.name] = link.to_socket
        for key in linkFrom.keys():
            if key in linkTo.keys():
                tree.link(linkFrom[key], linkTo[key])
        tree.nodes.remove(shell)


@Registrar()
class DAZ_OT_RemoveShells(DazOperator, Selector, ShellRemover, IsMesh):
    bl_idname = "daz.remove_shells"
    bl_label = "Remove Shells"
    bl_description = "Remove selected shells from active object"
    bl_options = {'UNDO'}

    columnWidth = 350

    def run(self, context):
        for item in self.getSelectedItems():
            for data in self.shells[item.text].values():
                for mat, node in data:
                    self.deleteNodes(mat, node)

    def invoke(self, context, event):
        self.getShells(context)
        self.selection.clear()
        for name, nodes in self.shells.items():
            item = self.selection.add()
            item.name = name
            item.text = name
            item.select = False
        return self.invokeDialog(context)


@Registrar()
class DAZ_OT_ReplaceShells(DazPropsOperator, ShellRemover):
    bl_idname = "daz.replace_shells"
    bl_label = "Replace Shells"
    bl_description = "Display shell node groups so they can be displaced."
    bl_options = {'UNDO'}
    pool = IsMesh.pool

    dialogWidth = 800

    def draw(self, context):
        rows = []
        n = 0
        for tname, struct in self.shells.items():
            for mname, data in struct.items():
                for mat, node in data:
                    rows.append((node.name, n, node))
                    n += 1
        rows.sort()
        for nname, n, node in rows:
            row = self.layout.row()
            row.label(text=nname)
            row.prop(node, "node_tree")

    def run(self, context):
        pass

    def invoke(self, context, event):
        self.getShells(context)
        return DazPropsOperator.invoke(self, context, event)


@Registrar()
class DAZ_OT_ChangeUnitScale(DazPropsOperator, IsMeshArmature):
    bl_idname = "daz.change_unit_scale"
    bl_label = "Change Unit Scale"
    bl_description = "Safely change the unit scale of selected object and children"
    bl_options = {'UNDO'}

    unit: FloatProperty(
        name="New Unit Scale",
        description="Scale used to convert between DAZ and Blender units. Default unit meters",
        default=0.01,
        precision=3,
        min=0.001, max=100.0)

    def draw(self, context):
        self.layout.prop(self, "unit")

    def invoke(self, context, event):
        if context.object:
            self.unit = context.object.DazScale
        return DazPropsOperator.invoke(self, context, event)

    def run(self, context):
        ob = context.object
        while ob.parent:
            ob = ob.parent
        self.meshes = []
        self.rigs = []
        self.parents = {}
        self.addObjects(ob)
        for ob in self.meshes:
            self.applyScale(context, ob)
            self.fixMesh(ob)
        for rig in self.rigs:
            self.applyScale(context, rig)
        for rig in self.rigs:
            self.restoreParent(context, rig)
        for ob in self.meshes:
            self.restoreParent(context, ob)

    def addObjects(self, ob):
        if ob.type == 'MESH':
            if ob not in self.meshes:
                self.meshes.append(ob)
        elif ob.type == 'ARMATURE':
            if ob not in self.rigs:
                self.rigs.append(ob)
        for child in ob.children:
            self.addObjects(child)

    def applyScale(self, context, ob):
        scale = self.unit / ob.DazScale
        if BlenderStatic.activate(context, ob):
            self.parents[ob.name] = (ob.parent, ob.parent_type, ob.parent_bone)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            lock = list(ob.lock_scale)
            ob.lock_scale = (False, False, False)
            ob.scale *= scale
            bpy.ops.object.transform_apply(
                location=False, rotation=False, scale=True)

    def fixMesh(self, ob):
        scale = self.unit / ob.DazScale
        for mat in ob.data.materials:
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'GROUP':
                        self.fixNode(node, node.node_tree.name, scale)
                    else:
                        self.fixNode(node, node.type, scale)

    NodeScale = {
        "BUMP": ["Distance"],
        "PRINCIPLED": ["Subsurface Radius"],
        "DAZ Translucent": ["Radius"],
        "DAZ Top Coat": ["Distance"],
    }

    def fixNode(self, node, nodetype, scale):
        if nodetype in self.NodeScale.keys():
            for sname in self.NodeScale[nodetype]:
                socket = node.inputs[sname]
                if isinstance(socket.default_value, float):
                    socket.default_value *= scale
                else:
                    socket.default_value = scale*Vector(socket.default_value)

    def restoreParent(self, context, ob):
        ob.DazScale = self.unit
        if ob.name in self.parents.keys():
            wmat = ob.matrix_world.copy()
            (ob.parent, ob.parent_type, ob.parent_bone) = self.parents[ob.name]
            ob.matrix_world = wmat


@Registrar.func
def register():
    from daz_import.Elements.Groups import DazFloatGroup
    bpy.types.Scene.DazFloats = CollectionProperty(type=DazFloatGroup)

    bpy.types.Material.DazSlots = CollectionProperty(type=EditSlotGroup)
    bpy.types.Object.DazSlots = CollectionProperty(type=EditSlotGroup)
