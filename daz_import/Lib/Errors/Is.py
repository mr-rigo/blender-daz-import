def is_mesh_armature(context):
    return context.object and context.object.type in ['MESH', 'ARMATURE']


def is_armature(context):
    return context.object and context.object.type == 'ARMATURE'


def is_mesh(context):
    return context.object and context.object.type == 'MESH'


def is_object(context):
    return context.object


class IsObject:
    pool = is_object


class IsMesh:
    pool = is_mesh


class IsArmature:
    pool = is_armature


class IsMeshArmature:
    pool = is_mesh_armature
