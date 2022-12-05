from gooey import Gooey, GooeyParser, local_resource_path

from web_autobuy import Autobuy

import gui_menu

from web_analyzer import WebAnalyzer

@Gooey(
    program_name = 'Bloodweb AutoBuy 1.1.10',
    program_description = 'Automated Bloodweb progression',
    image_dir = local_resource_path('data/images'),
    body_bg_color = '#FFFFFF',
    header_bg_color = '#C9B899',
    show_success_modal = False,
    footer_bg_color = '#717E92',
    tabbed_groups = True,
    show_stop_warning = False,
    force_stop_is_error = False,
    show_sidebar = False,
    clear_before_run = True,
    default_size = (662, 715),
    richtext_controls = True,
    menu=[{
        'name': 'Help',
        'items': gui_menu.help_items
    },
    {
        'name': 'Licenses',
        'items': gui_menu.third_party_items
        }]
)
def main():
    parser = GooeyParser()
    options_group = parser.add_argument_group('Options', description = gui_menu.options_group_desc)
    advanced_group = parser.add_argument_group('Advanced', description = gui_menu.advanced_group_desc)
    unsupported_resolution_group = parser.add_argument_group('Unsupported Resolutions', description = gui_menu.unsupported_resolution_group_desc)
                        
    ordering = options_group.add_mutually_exclusive_group(
                        gooey_options = {
                            'initial_selection': 0
                            }
                        )
    
    ordering.add_argument('-c', '--cheap',
                        metavar='Cheap Mode',
                        action='store_true', 
                        help='Buy the most common nodes first'
                        )
    ordering.add_argument('-e', '--expensive',
                        metavar='Expensive Mode',
                        action='store_true', 
                        help='Buy the rarest nodes first.'
                        )
                            
    ordering.add_argument('-s', '--shuffle',
                        metavar='Random Mode',
                        action='store_true', 
                        help='Buy the nodes in a random order.'
                        )
    
    options_group.add_argument('--should_prestige',
                        action='store_false', 
                        metavar='Auto-Prestige',
                        help='Automatically advance prestige levels. Disable to pause after level 50'
                        )
    
    options_group.add_argument('-p', '--start_paused',
                        metavar='Start Paused',
                        action='store_true', 
                        help='Start the program in the paused state. Pressing F3 is required to start.',
                        widget="BlockCheckbox",
                        gooey_options={
                            'checkbox_label' : "Enable paused start"
                            }
                        )

    
    options_group.add_argument('-w', '--activate_window',
                        action='store_false', 
                        metavar='Bring window to foreground',
                        help='Focuses the game window at the start to make sure no other windows are covering it',
                        widget="BlockCheckbox",
                        gooey_options={
                            'checkbox_label' : "AutoFocus window on start"
                            }
                        )


    options_group.add_argument('-t', '--time_limit',
                        metavar='Time limit',
                        default=0.0,
                        widget='DecimalField',
                        help='Stop after this duration (minutes), Set to 0 to disable limit.'
                        )

    
    options_group.add_argument('-m', '--monitor_index',
                        default=0,
                        metavar='Monitor index',
                        help='Leave to 0 to let the game window be found automatically.',
                        widget='IntegerField',
                        gooey_options = {
                            'min' : 0, 
                            'max' : 63, 
                            'increment' : 1
                            }
                        )
    
    advanced_group.add_argument('--first_timing_offset',
                        metavar='Fine-tune buying interval (First 5 nodes)',
                        default=0.0,
                        widget='Slider',
                        help='Add or remove buying delay before the Entity starts blocking nodes\nUnit: 10 ms',
                        gooey_options = {
                            'min' : -2, 
                            'max' : 100, 
                            'increment' : 1
                            }
                        )
    
    advanced_group.add_argument('--second_timing_offset',
                        metavar='Fine-tune buying interval (After 5 nodes)',
                        default=0.0,
                        widget='Slider',
                        help='Add or remove buying delay after the Entity starts blocking nodes\nUnit: 10 ms',
                        gooey_options = {
                            'min' : -43, 
                            'max' : 100, 
                            'increment' : 1
                            }
                        )
    
    advanced_group.add_argument('--ring_color',
                        default='#918b6a',
                        metavar='Purchasable node ring color',
                        help="""Customize the color that's used to detect whether a node is purchasable.\nSampled in the middle of a node's yellow ring. Default: [R: 145, G: 139, B: 106]""", 
                        widget='ColourChooser') 

    advanced_group.add_argument('--node_color_threshold',
                        default=20,
                        metavar='Node color detection threshold',
                        help="""Customize the detection tolerance for nodes. Too high values can result in false positives.\nDefault: 20""",
                        widget='Slider',
                        gooey_options = {
                            'min' : 0, 
                            'max' : 100, 
                            'increment' : 1
                            }
                        )

    advanced_group.add_argument('-v', '--verbose',
                        metavar='Verbose output',
                        action='store_true', 
                        help='Print debug info.'
                        )


    unsupported_resolution_group.add_argument('-r', '--unsupported_resolution_enabled',
                        metavar='Custom midpoint',
                        default=False,
                        action='store_true', 
                        help='If enabled, the program will use the provided custom X and Y coordinates as the Bloodweb midpoint',
                        widget='BlockCheckbox',
                        gooey_options = {
                            'checkbox_label' : "Use custom midpoint"
                            }
                        )

    unsupported_resolution_group.add_argument('--unsupported_resolution_debug',
                        metavar='Enable test mode',
                        default=False,
                        action='store_true', 
                        help='Generate alignment test images. Files beginning with BAB_<x>_<y>.png will be saved on the desktop.',
                        widget='BlockCheckbox',
                        gooey_options = {
                            'checkbox_label' : "Save preview images"
                            }
                        )

    unsupported_resolution_group.add_argument('-x', '--unsupported_resolution_mid_x',
                        metavar='Midpoint X-coordinate',
                        default=0,
                        help='X coordinate of the Bloodweb midpoint',
                        widget='DecimalField',
                        gooey_options = {
                            'min' : 0, 
                            'max' : 12800, 
                            'increment' : 0.5
                            }
                        )

    unsupported_resolution_group.add_argument('-y', '--unsupported_resolution_mid_y',
                        metavar='Midpoint Y-coordinate',
                        default=0,
                        help='Y coordinate of the Bloodweb midpoint',
                        widget='DecimalField',
                        gooey_options = {
                            'min' : 0, 
                            'max' : 12800, 
                            'increment' : 0.5
                            }
                        )

    
    args = parser.parse_args()

    if args.unsupported_resolution_debug:
        # Run the custom resolution debug image generator 
        analyzer = WebAnalyzer()
        analyzer.set_bring_to_front(not bool(args.activate_window))
        analyzer.set_override_monitor_index(int(args.monitor_index))
        
        if args.unsupported_resolution_enabled:
            autobuy.web_analyzer.set_custom_midpoint(
                float(args.unsupported_resolution_mid_x),
                float(args.unsupported_resolution_mid_y))
        try:
            analyzer.initialize()
        except (WebAnalyzer.GameResolutionError, WebAnalyzer.WindowNotFoundError):
            print("Failed to initialize", flush=True)
            return
        analyzer.save_debug_images()
        return


    ordering = Autobuy.Ordering.CHEAP
    if args.shuffle:
        ordering = Autobuy.Ordering.SHUFFLE
    elif args.expensive:
        ordering = Autobuy.Ordering.EXPENSIVE
        
    # Run the main program
    autobuy = Autobuy()
    autobuy.set_start_paused(bool(args.start_paused))
    autobuy.set_verbose(bool(args.verbose))
    autobuy.set_time_limit(float(args.time_limit) * 60.0)
    autobuy.set_timing_offset_1(float(args.first_timing_offset) / 100)
    autobuy.set_timing_offset_2(float(args.second_timing_offset) / 100)
    # Workaround, this version of gooey doesn't support True default checkboxes
    autobuy.set_auto_prestige(not bool(args.should_prestige)) 
    autobuy.set_ordering(ordering)
    autobuy.web_analyzer.set_bring_to_front(not bool(args.activate_window))
    autobuy.web_analyzer.set_override_monitor_index(int(args.monitor_index))
    autobuy.web_analyzer.set_node_tolerance(int(args.node_color_threshold))
    autobuy.web_analyzer.set_color_available(tuple(bytes.fromhex(args.ring_color[1:])))
    
    if args.unsupported_resolution_enabled:
        autobuy.web_analyzer.set_custom_midpoint(
                            float(args.unsupported_resolution_mid_x), 
                            float(args.unsupported_resolution_mid_y))
    
    autobuy.run()
    
if __name__ == "__main__":
    main()