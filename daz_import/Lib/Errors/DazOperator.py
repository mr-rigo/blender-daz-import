import bpy
from daz_import.Lib.Settings import Settings
from daz_import.Lib.BlenderStatic import BlenderStatic
from .ErrorsStatic import DazError, ErrorsStatic
from daz_import.Collection import Collection


class DazOperator(bpy.types.Operator):
    pool = lambda *_: None

    def execute(self, context):
        self.prequel(context)

        try:
            self.run(context)
        except DazError:
            ErrorsStatic.handle_daz(context)
        except KeyboardInterrupt:
            Settings.theMessage_ = "Keyboard interrupt"
            bpy.ops.daz.error('INVOKE_DEFAULT')
        finally:
            self.sequel(context)
            Collection.clear_import()

        return{'FINISHED'}

    def prequel(self, context):
        self.storeState(context)
        ErrorsStatic.clear()

    def sequel(self, context):
        wm = bpy.context.window_manager
        wm.progress_update(100)
        wm.progress_end()
        self.restoreState(context)

    def storeState(self, context):

        self.mode = None
        self.activeObject = context.object
        self.selectedObjects = [
            ob.name for ob in BlenderStatic.selected(context)]

        if context.object:
            self.mode = context.object.mode

            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass

    def restoreState(self, context):
        try:
            if self.activeObject:
                BlenderStatic.active_object(context, self.activeObject)

            for obname in self.selectedObjects:
                if obname in bpy.data.objects.keys():
                    bpy.data.objects[obname].select_set(True)

            if self.mode:
                bpy.ops.object.mode_set(mode=self.mode)
        except RuntimeError:
            pass

    def run(self, *args):
        ...
