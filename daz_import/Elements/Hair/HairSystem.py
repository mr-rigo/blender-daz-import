import bpy
from math import floor

from daz_import.Lib.Settings import Settings, Settings, Settings
from daz_import.Lib.Errors import DazError
from daz_import.utils import *
from daz_import.Elements.Material.Data import EnumsHair
from .HairStatic import HairStatic


class HairSystem:
    def __init__(self, key, n, hum, mnum, btn):
        self.name = ("Hair_%s" % key)
        self.scale = hum.DazScale
        self.button = btn
        self.npoints = n
        self.mnum = mnum
        self.strands = []
        self.useEmitter = True
        self.vertexGroup = None
        self.material = btn.materials[mnum].name

    def setHairSettings(self, psys, ob):
        btn = self.button
        pset = psys.settings
        if hasattr(pset, "cycles_curve_settings"):
            ccset = pset.cycles_curve_settings
        elif hasattr(pset, "cycles"):
            ccset = pset.cycles
        else:
            ccset = pset

        if (self.material and
                self.material in ob.data.materials.keys()):
            pset.material_slot = self.material

        pset.rendered_child_count = btn.nRenderChildren
        pset.child_nbr = btn.nViewChildren
        if hasattr(pset, "display_step"):
            pset.display_step = btn.nViewStep
        else:
            pset.draw_step = btn.nViewStep
        pset.render_step = btn.nRenderStep
        pset.child_length = 1
        psys.child_seed = 0
        pset.child_radius = 0.1*btn.childRadius*self.scale

        if hasattr(ccset, "root_width"):
            ccset.root_width = 0.1*btn.rootRadius
            ccset.tip_width = 0.1*btn.tipRadius
        else:
            ccset.root_radius = 0.1*btn.rootRadius
            ccset.tip_radius = 0.1*btn.tipRadius
        if btn.strandShape == 'SHRINK':
            pset.shape = 0.99
        ccset.radius_scale = self.scale

    def addStrand(self, strand):
        self.strands.append(strand[0])

    def resize(self, size):
        nstrands = []
        for strand in self.strands:
            nstrand = self.resizeStrand(strand, size)
            nstrands.append(nstrand)
        return nstrands

    def resizeBlock(self):
        n = 10*((self.npoints+5)//10)
        if n < 10:
            n = 10
        return n, self.resize(n)

    def resizeStrand(self, strand, n):
        m = len(strand)
        if m == n:
            return strand
        step = (m-1)/(n-1)
        nstrand = []
        for i in range(n-1):
            j = floor(i*step + 1e-4)
            x = strand[j]
            y = strand[j+1]
            eps = i*step - j
            z = eps*y + (1-eps)*x
            nstrand.append(z)
        nstrand.append(strand[m-1])
        return nstrand

    def build(self, context, ob):
        from time import perf_counter
        t1 = perf_counter()
        if len(self.strands) == 0:
            raise DazError("No strands found")
        btn = self.button

        hlen = int(len(self.strands[0]))
        if hlen < 3:
            return
        bpy.ops.object.particle_system_add()
        psys = ob.particle_systems.active
        psys.name = self.name

        if self.vertexGroup:
            psys.vertex_group_density = self.vertexGroup

        pset = psys.settings
        pset.type = 'HAIR'
        pset.use_strand_primitive = True
        if hasattr(pset, "use_render_emitter"):
            pset.use_render_emitter = self.useEmitter
        elif hasattr(ob, "show_instancer_for_render"):
            ob.show_instancer_for_render = self.useEmitter
        pset.render_type = 'PATH'
        if btn.nViewChildren or btn.nRenderChildren:
            pset.child_type = 'SIMPLE'
        else:
            pset.child_type = 'NONE'

        #pset.material = len(ob.data.materials)
        pset.path_start = 0
        pset.path_end = 1
        pset.count = int(len(self.strands))
        pset.hair_step = hlen-1
        pset.use_hair_bspline = True
        if hasattr(pset, "display_step"):
            pset.display_step = 3
        else:
            pset.draw_step = 3
        self.setHairSettings(psys, ob)

        psys.use_hair_dynamics = False

        t2 = perf_counter()
        bpy.ops.particle.disconnect_hair(all=True)
        bpy.ops.particle.connect_hair(all=True)
        psys = HairStatic.update(context, ob, psys)
        t3 = perf_counter()
        self.buildStrands(psys)
        t4 = perf_counter()
        psys = HairStatic.update(context, ob, psys)
        # printPsys(psys)
        t5 = perf_counter()
        self.buildFinish(context, psys, ob)
        t6 = perf_counter()
        BlenderStatic.set_mode('OBJECT')
        #print("Hair %s: %.3f %.3f %.3f %.3f %.3f" % (self.name, t2-t1, t3-t2, t4-t3, t5-t4, t6-t5))

    def buildStrands(self, psys):
        for m, hair in enumerate(psys.particles):
            verts = self.strands[m]
            hair.location = verts[0]
            if len(verts) < len(hair.hair_keys):
                continue
            for n, v in enumerate(hair.hair_keys):
                v.co = verts[n]

    def buildFinish(self, context, psys, hum):
        scn = context.scene
        #BlenderStatic.activate(context, hum)
        BlenderStatic.set_mode('PARTICLE_EDIT')
        pedit = scn.tool_settings.particle_edit
        pedit.use_emitter_deflect = False
        pedit.use_preserve_length = False
        pedit.use_preserve_root = False
        hum.data.use_mirror_x = False
        pedit.select_mode = 'POINT'
        bpy.ops.transform.translate()
        BlenderStatic.set_mode('OBJECT')
        bpy.ops.particle.disconnect_hair(all=True)
        bpy.ops.particle.connect_hair(all=True)

    def addHairDynamics(self, psys, hum):
        psys.use_hair_dynamics = True
        cset = psys.cloth.settings
        cset.pin_stiffness = 1.0
        cset.mass = 0.05
        deflector = self.findDeflector(hum)

    @staticmethod
    def findDeflector(human):
        rig = human.parent
        if rig:
            children = rig.children
        else:
            children = human.children
        for ob in children:
            if ob.field.type == 'FORCE':
                return ob
        return None
