from gooey import Gooey, GooeyParser

from web_autobuy import Autobuy

import gui_menu

from web_analyzer import WebAnalyzer

@Gooey(
    program_name='Bloodweb AutoBuy',
    program_description="Automated Bloodweb progression for Dead by Daylight",
    #image_dir='data',
    body_bg_color="#BBBDC0",
    header_bg_color="#C9B899",
    footer_bg_color="#717E92",
    tabbed_groups=True,
    show_stop_warning=False,
    force_stop_is_error=False,
    show_sidebar=False,
    default_size=(600, 700),
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
    options_group = parser.add_argument_group(
    "Options",
"""Moving your mouse or pressing F3 will pause the program, press F3 again to resume.
Press Esc or F2 to stop the program at any point.
Make sure that the game is in fullscreen mode and that the GUI scale is set to 100%.""")
    advanced_group = parser.add_argument_group(
    "Advanced", 
    """Customize the color detection parameters, might be required if you use strong filters. Disabling filters temporarily instead is probably easier.
If your monitor resolution is unsupported, you can calibrate the sample points yourself
All you have to do is to supply the X and Y pixel coordinates of the bloodweb center
Use the debug with the Bloodweb open to see the results""")
    
    
    options_group.add_argument('-m', '--monitor_index',
                            default=0,
                            metavar='Monitor index',
                            help="Leave to 0 to let the game window be found automatically.",
                            widget='IntegerField')
    
    options_group.add_argument('-w', '--activate_window',
                        default=True,
                        action="store_true", 
                        metavar="Bring window to foreground",
                        help="Focuses the game window at the start to make sure no other windows are covering it")

    options_group.add_argument('-p', '--start_paused',
                            default=False,
                            metavar='Start Paused',
                            action="store_true", 
                            help="""Start the program in the paused state. Pressing F3 is required to start.""")
        

    ordering = options_group.add_mutually_exclusive_group()
    
    ordering.add_argument('-e', '--expensive',
                            metavar='Buy the most expensive nodes first',
                            action="store_true", 
                            help="""Buy the rarest nodes first""")
                        
    ordering.add_argument('-s', '--shuffle',
                            metavar="Randomize order",
                            action="store_true", 
                            help="Buy the nodes in a random order.")
    
    options_group.add_argument('--should_prestige',
                            default=True,
                            action="store_true", 
                            metavar='Auto-Prestige',
                            help="Automatically advance prestige levels. Disable to pause after level 50")
    
    
    options_group.add_argument('-t', '--time_limit',
                            metavar='Time limit',
                            default=0.0,
                            widget="DecimalField",
                            help="Stop after this duration (minutes), Set to 0 to disable limit.")
    
    advanced_group.add_argument('--ring_color',
                                default="#9C9575",
                                metavar='Purchasable node ring color',
                                help="Customize the color that's used to detect whether a node is purchasable.\nSampled in the middle of a node's yellow ring. Default: [R: 156, G: 149, B: 117]", 
                                widget='ColourChooser') 
    
    advanced_group.add_argument('--node_color_threshold',
                            default=20,
                            metavar='Node color detection threshold',
                            help="Customize the detection tolerance for nodes. Too high values can result in false positives.\nDefault: 20",
                            widget='IntegerField')    
    
    advanced_group.add_argument('-v', '--verbose',
                                metavar='Verbose output',
                                action="store_true", 
                                help="""Print debug info.""")
    
    advanced_group.add_argument('--unsupported_resolution_debug',
                                metavar='For unsupported resolutions: Save test images',
                                default=False,
                                action="store_true", 
                                help="""Turn on to save test images to preview the custom midpoint. Files beginnning with BAB_<x>_<y> will be saved on the desktop.""",
                                widget="BlockCheckbox")
    
    
    advanced_group.add_argument('--unsupported_resolution_mid_x',
                                metavar='For unsupported resolutions: Midpoint X',
                                default=0,
                                help="""X coordinate of the Bloodweb midpoint"""
                                )
                                

    advanced_group.add_argument('--unsupported_resolution_mid_y',
                                metavar='For unsupported resolutions: Midpoint Y',
                                default=0,
                                help="""X coordinate of the Bloodweb midpoint""")


    args = parser.parse_args()

    if args.unsupported_resolution_debug:
        analyzer = WebAnalyzer()
        analyzer.set_override_monitor_index(int(args.monitor_index))
        analyzer.set_custom_midpoint(int(args.unsupported_resolution_mid_x), int(args.unsupported_resolution_mid_y))
        analyzer.initialize()
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
    autobuy.set_auto_prestige(bool(args.should_prestige))
    autobuy.set_ordering(ordering)
    autobuy.web_analyzer.set_override_monitor_index(int(args.monitor_index))
    autobuy.web_analyzer.set_node_tolerance(int(args.node_color_threshold))
    autobuy.web_analyzer.set_color_available(tuple(bytes.fromhex(args.ring_color[1:])))
    
    custom_x = int(args.unsupported_resolution_mid_x)
    custom_y = int(args.unsupported_resolution_mid_y)
    if custom_x != 0 and custom_y != 0:
        autobuy.web_analyzer.set_custom_midpoint(custom_x, custom_y)
    
    autobuy.run()
    
if __name__ == "__main__":
    main()