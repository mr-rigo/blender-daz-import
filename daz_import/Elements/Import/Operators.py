from __future__ import annotations
from urllib.parse import unquote

import bpy
from bpy.props import StringProperty

from .DazOptions import DazOperator
from daz_import.Lib import Registrar


@Registrar()
class DAZ_OT_Quote(DazOperator):
    bl_idname = "daz.quote"
    bl_label = "Quote"

    def execute(self, context):
        DAZ_OT_QuoteUnquote.update()
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_Unquote(DazOperator):
    bl_idname = "daz.unquote"
    bl_label = "Unquote"

    def execute(self, context):
        DAZ_OT_QuoteUnquote.update()
        return {'PASS_THROUGH'}


@Registrar()
class DAZ_OT_QuoteUnquote(bpy.types.Operator):
    quote: DAZ_OT_QuoteUnquote = None

    bl_idname = "daz.quote_unquote"
    bl_label = "Quote/Unquote"
    bl_description = "Quote or unquote specified text"

    Text: StringProperty(description="Type text to quote or unquote")

    def draw(self, context):
        self.layout.prop(self, "Text", text="")
        row = self.layout.row()
        row.operator("daz.quote")
        row.operator("daz.unquote")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        self.quote = self
        wm = context.window_manager
        return wm.invoke_popup(self, width=800)

    @classmethod
    def update(cls):
        cls.quote.Text = unquote(cls.quote.Text)
