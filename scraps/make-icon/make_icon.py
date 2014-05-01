#!/usr/bin/env python

# Put this file in the appropriate place:
# 	!copy make_icon.py %USERPROFILE%\.gimp-2.8\plug-ins\
# 
# Built based on the tutorial at http://www.exp-media.com/content/extending-gimp-python-python-fu-plugins-part-2

from gimpfu import *

def make_icon_layers( image, layer ):
	import gimp
	g = gimp.pdb
	def gprint( x ): return g.gimp_message( str( x ) )
	#image = gimp.image_list()[ 0 ]
	#layer = image.layers[ 0 ]
	for size in [ 64, 48, 32, 16 ]:
		duplicate = g.gimp_layer_copy( layer, TRUE )
		g.gimp_image_insert_layer( image, duplicate, None, -1 )	
		g.gimp_item_set_name( duplicate, '%dx%d' % ( size, size ) )
		g.gimp_layer_scale_full( duplicate, size, size, FALSE, 3 )
	g.gimp_image_remove_layer( image, layer )
	g.gimp_image_resize_to_layers( image )

register(
	"make_icon_layers", # name as exported to function browser
	"Make Icon Layers",   # short description
	"Delete the current layer after creating 16x16, 32x32, 48x48 and 64x64 copies of it. The result is suitable for exporting as a Windows .ico file.", # longer description
	"Jez Hill", # author
	"Neural Engineering", # copyright info
	"April 2014", # release date
	"<Image>/Custom Scripts/Make Icon Layers", # menu location
	"*", # image types supported
	[], # input parameters of local function
	[], # output parameters of local function
	make_icon_layers,  # name of local function
)

main()
