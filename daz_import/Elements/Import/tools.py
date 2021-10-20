import bpy


def makeRootCollection(grpname, context):
    root = bpy.data.collections.new(name=grpname)
    context.scene.collection.children.link(root)
    return root

