
import bpy

import asyncio
import traceback
import concurrent.futures
import logging
import gc
import sys


from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtWidgets import QApplication, QPushButton, qApp


class Panel(bpy.types.Panel):
    bl_idname = "LS_SAMPLE_PT_Panel"
    bl_label = "Asyncio Examples"
    bl_category = "Asyncio Examples"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context_):
        layout = self.layout
        layout.row().operator('view3d.button', text="PyQtButton")


log = logging.getLogger(__name__)

# Keeps track of whether a loop-kicking operator is already running.
_loop_kicking_operator_running = False


def kick_async_loop(*args) -> bool:
    """Performs a single iteration of the asyncio event loop.

    :return: whether the asyncio loop should stop after this kick.
    """

    loop = asyncio.get_event_loop()

    # Even when we want to stop, we always need to do one more
    # 'kick' to handle task-done callbacks.
    stop_after_this_kick = False

    if loop.is_closed():
        log.warning('loop closed, stopping immediately.')
        return True

    all_tasks = asyncio.all_tasks(loop)
    if not len(all_tasks):
        log.debug('no more scheduled tasks, stopping after this kick.')
        stop_after_this_kick = True

    elif all(task.done() for task in all_tasks):
        log.debug('all %i tasks are done, fetching results and stopping after this kick.',
                  len(all_tasks))
        stop_after_this_kick = True

        # Clean up circular references between tasks.
        gc.collect()

        for task_idx, task in enumerate(all_tasks):
            if not task.done():
                continue

            # noinspection PyBroadException
            try:
                res = task.result()
                log.debug('   task #%i: result=%r', task_idx, res)
            except asyncio.CancelledError:
                # No problem, we want to stop anyway.
                log.debug('   task #%i: cancelled', task_idx)
            except Exception:
                print('{}: resulted in exception'.format(task))
                traceback.print_exc()

            # for ref in gc.get_referrers(task):
            #     log.debug('      - referred by %s', ref)

    loop.stop()
    loop.run_forever()

    return stop_after_this_kick

# https://github.com/lampysprites/blender-asyncio


class AsyncLoopModalOperator(bpy.types.Operator):
    bl_idname = 'asyncio.loop'
    bl_label = 'Runs the asyncio main loop'

    timer = None
    log = logging.getLogger(__name__ + '.AsyncLoopModalOperator')

    def __del__(self):
        global _loop_kicking_operator_running

        # This can be required when the operator is running while Blender
        # (re)loads a file. The operator then doesn't get the chance to
        # finish the async tasks, hence stop_after_this_kick is never True.
        _loop_kicking_operator_running = False

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        global _loop_kicking_operator_running

        if _loop_kicking_operator_running:
            self.log.debug('Another loop-kicking operator is already running.')
            return {'PASS_THROUGH'}

        context.window_manager.modal_handler_add(self)
        _loop_kicking_operator_running = True

        wm = context.window_manager
        self.timer = wm.event_timer_add(0.00001, window=context.window)

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        global _loop_kicking_operator_running

        # If _loop_kicking_operator_running is set to False, someone called
        # erase_async_loop(). This is a signal that we really should stop
        # running.
        if not _loop_kicking_operator_running:
            return {'FINISHED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        # self.log.debug('KICKING LOOP')
        stop_after_this_kick = kick_async_loop()
        if stop_after_this_kick:
            context.window_manager.event_timer_remove(self.timer)
            _loop_kicking_operator_running = False

            self.log.debug('Stopped asyncio loop kicking')
            return {'FINISHED'}

        return {'RUNNING_MODAL'}


class CloseFilter(QObject):
    is_active = True

    def eventFilter(self, obj: QObject, event: QEvent):
        if event.type() == event.Close:
            qApp.destroyed.emit()
            self.is_active = False
        return super().eventFilter(obj, event)


class PyQtButton(bpy.types.Operator):
    bl_idname = "view3d.button"
    bl_label = "PyQtButton"
    bl_description = "Center 3d cursor button"

    async def run(self):
        # await asyncio.sleep(3)
        app = QApplication(sys.argv)
        eventLoop = CloseFilter()
        from DazView import DazView

        button = DazView()
        button.installEventFilter(eventLoop)
        button.show()
        button.resize(300, 150)

        button.changed.connect(lambda x: open_file(x))

        # button.clicked.connect(
        #     lambda*_: bpy.ops.view3D.snap_cursor_to_center())

        while eventLoop.is_active:
            await asyncio.sleep(0.01)
            app.processEvents()
        QApplication.exit()

    def execute(self, context):
        async_task = asyncio.ensure_future(self.run())
        # It's also possible to handle the task when it's done like so:
        # async_task.add_done_callback(done_callback)
        log.debug('Starting asyncio loop')
        result = bpy.ops.asyncio.loop()
        log.debug('Result of starting modal operator is %r', result)
        return {'FINISHED'}

def open_file(path: str):
    print('open file')
    from daz_import.Elements.Import import import_daz_file

    try:
        import_daz_file(path)
    except:
        ...


def register():
    if sys.platform == 'win32':
        asyncio.get_event_loop().close()
        # On Windows, the default event loop is SelectorEventLoop, which does
        # not support subprocesses. ProactorEventLoop should be used instead.
        # Source: https://docs.python.org/3/library/asyncio-subprocess.html
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    loop.set_default_executor(executor)

    bpy.utils.register_class(AsyncLoopModalOperator)
    bpy.utils.register_class(PyQtButton)
    bpy.utils.register_class(Panel)


def unregister():
    bpy.utils.unregister_class(AsyncLoopModalOperator)
    bpy.utils.unregister_class(PyQtButton)
    bpy.utils.unregister_class(Panel)


if True:
    register()
    from daz_import import register
    register()
# bpy.ops.view3D.button()
