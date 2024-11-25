_is_imported = False

import dearpygui.dearpygui as dpg

def main():
    try:
        dpg.create_context()

        dpg.show_documentation()
        dpg.show_style_editor()
        dpg.show_debug()
        dpg.show_about()
        dpg.show_metrics()
        dpg.show_font_manager()
        dpg.show_item_registry()

        with dpg.window(label="Example Window"):
            dpg.add_text("Hello, world")
            dpg.add_button(label="Save")
            dpg.add_input_text(label="string", default_value="Quick brown fox")
            dpg.add_slider_float(label="float", default_value=0.273, max_value=1)

        dpg.create_viewport(title='be6502emu', width=800, height=600)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        
        # raise Exception("Something went wrong :(")

        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()

        dpg.destroy_context()
    except: return True
    else: return False

if __name__ == '__main__':
    main()

_is_imported = True