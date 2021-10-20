from .DazOperator import DazOperator


class DazPropsOperator(DazOperator):
    dialogWidth = 300

    def invoke(self, context, event):
        wm = context.window_manager

        return wm.invoke_props_dialog(self, width=self.dialogWidth)
