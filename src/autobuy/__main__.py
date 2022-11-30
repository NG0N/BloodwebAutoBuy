from gooey import Gooey, GooeyParser

from web_autobuy import Autobuy

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
        'items': [
            {
                'type': 'AboutDialog',
                'menuTitle': 'About',
                'name': 'Bloodweb AutoBuy',
                'description': 'Automated Bloodweb progression for Dead by Daylight',
                'version': '1.0.0',
                'copyright': '2022',
                'website': 'https://github.com/NG0N/BloodwebAutoBuy',
                'license': 'MIT'
            },
            {
            'type': 'Link',
            'menuTitle': 'Documentation',
            'url': 'https://github.com/NG0N/BloodwebAutoBuy'
        }]
    }]
)
def main():
    parser = GooeyParser()
    options_group = parser.add_argument_group(
    "Options",
    "Moving your mouse or pressing F3 will pause the program, press F3 again to resume.\nPress Esc or F2 to stop the program at any point.\nMake sure the game window is visible and in fullscreen.\nCurrently only supports 1920x1080 resolution with 100% GUI scale.")
    advanced_group = parser.add_argument_group(
    "Advanced", 
    "Customize the color detection parameters, might be required if you use strong filters. Disabling filters temporarily instead is probably easier.")
    
    options_group.add_argument('-w', '--start_paused',
                            default=False,
                            metavar='Start Paused',
                            action="store_true", 
                            help="""Start the program in the paused state. Pressing F3 is required to start.""")
        
    options_group.add_argument('-m', '--monitor_index',
                            default=1,
                            metavar='Monitor index',
                            help="Select the monitor where the game is displayed. Starts from 1",
                            widget='IntegerField')
    
    ordering = options_group.add_mutually_exclusive_group()
    
    ordering.add_argument('-r', '--reverse',
                            metavar='Buy closest nodes first',
                            action="store_true", 
                            help="""Buy the innermost available nodes first, rarer items will be less likely to be bought.\nIf disabled, the furthest away node available will be always bought first.""")
                        
    ordering.add_argument('-s', '--shuffle',
                            metavar="Randomize order",
                            action="store_true", 
                            help="Buy the nodes in a random order.")
    options_group.add_argument('-p', '--should_prestige',
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
                            default=50,
                            metavar='Node color detection threshold',
                            help="Customize the detection tolerance for nodes. Too high values can result in false positives.\nDefault: 50",
                            widget='IntegerField')    
    
    advanced_group.add_argument('--prestige_color_threshold',
                            default=50,
                            metavar='Prestige color detection threshold',
                            help="Customize the detection tolerance for prestige icon. Too high values can result in false positives.\nDefault: 4",
                            widget='IntegerField')
      
    advanced_group.add_argument('-v', '--verbose',
                                metavar='Verbose output',
                                action="store_true", 
                                help="""Print debug info.""")
        
    args = parser.parse_args()

    ordering = Autobuy.Ordering.DEFAULT
    if args.shuffle:
        ordering = Autobuy.Ordering.SHUFFLE
    elif args.reverse:
        ordering = Autobuy.Ordering.REVERSE
        
    # Run the main program
    autobuy = Autobuy()
    autobuy.set_start_paused(bool(args.start_paused))
    autobuy.set_verbose(bool(args.verbose))
    autobuy.set_monitor_index(int(args.monitor_index))
    autobuy.set_time_limit(float(args.time_limit) * 60.0)
    autobuy.set_auto_prestige(bool(args.should_prestige))
    autobuy.set_ordering(ordering)
    autobuy.set_node_tolerance(int(args.node_color_threshold))
    autobuy.set_prestige_tolerance(int(args.prestige_color_threshold))
    autobuy.set_color_available(tuple(bytes.fromhex(args.ring_color[1:])))
    autobuy.run()
    
if __name__ == "__main__":
    main()