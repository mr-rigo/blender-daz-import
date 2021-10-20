from mathutils import Vector
from daz_import.Lib import BlenderStatic


class HairStatic:

    @staticmethod
    def update(context, ob, psys):
        dg = context.evaluated_depsgraph_get()
        return ob.evaluated_get(dg).particle_systems.active

    @staticmethod
    def getHairAndHuman(context, strict):
        hair = context.object
        hum = None
        for ob in BlenderStatic.selected_meshes(context):
            if ob != hair:
                hum = ob
                break
        if strict and hum is None:
            raise ValueError("Select hair and human")
            # raise DazError("Select hair and human")
        return hair, hum

    @staticmethod
    def createSkullGroup(hum, skullType):  # unused
        if skullType == 'TOP':
            maxheight = -1e4
            for v in hum.data.vertices:
                if v.co[2] > maxheight:
                    maxheight = v.co[2]
                    top = v.index
            vgrp = hum.vertex_groups.new(name="Skull")
            vgrp.add([top], 1.0, 'REPLACE')
            return vgrp
        elif skullType == 'ALL':
            vgrp = hum.vertex_groups.new(name="Skull")
            for vn in range(len(hum.data.vertices)):
                vgrp.add([vn], 1.0, 'REPLACE')
            return vgrp
        else:
            return None

    @staticmethod
    def printPsys(psys):  # unused
        for m, hair in enumerate(psys.particles):
            print("\n")
            print(hair.location)
            for v in hair.hair_keys:
                print(v.co)

    @classmethod
    def makeDeflector(cls, pair, rig, bnames, cfg):  # unused
        _, ob = pair

        cls.shiftToCenter(ob)

        if rig:
            for bname in bnames:
                if bname in cfg.bones.keys():
                    bname = cfg.bones[bname]
                if bname in rig.pose.bones.keys():
                    ob.parent = rig
                    ob.parent_type = 'BONE'
                    ob.parent_bone = bname
                    pb = rig.pose.bones[bname]
                    ob.matrix_basis = pb.matrix.inverted() @ ob.matrix_basis
                    ob.matrix_basis.col[3] -= Vector((0, pb.bone.length, 0, 0))
                    break

        ob.draw_type = 'WIRE'
        ob.field.type = 'FORCE'
        ob.field.shape = 'SURFACE'
        ob.field.strength = 240.0
        ob.field.falloff_type = 'SPHERE'
        ob.field.z_direction = 'POSITIVE'
        ob.field.falloff_power = 2.0
        ob.field.use_max_distance = True
        ob.field.distance_max = 0.125*ob.DazScale

    @staticmethod
    def shiftToCenter(ob):
        sum = Vector()

        for v in ob.data.vertices:
            sum += v.co

        offset = sum/len(ob.data.vertices)
        
        for v in ob.data.vertices:
            v.co -= offset

        ob.location = offset



