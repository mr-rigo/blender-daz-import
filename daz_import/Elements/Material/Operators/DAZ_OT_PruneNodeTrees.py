from daz_import.Lib import Registrar, BlenderStatic
from daz_import.Lib.Errors import DazOperator, IsMesh


@Registrar()
class DAZ_OT_PruneNodeTrees(DazOperator):
    bl_idname = "daz.prune_node_trees"
    bl_label = "Prune Node Trees"
    bl_description = "Prune all material node trees for selected meshes"
    bl_options = {'UNDO'}
    pool = IsMesh.pool
    
    def run(self, context):
        from daz_import.Elements.Material.Cycles import CyclesStatic

        for ob in BlenderStatic.selected_meshes(context):
            for mat in ob.data.materials:
                if mat.node_tree:
                    CyclesStatic.pruneNodeTree(mat.node_tree)
