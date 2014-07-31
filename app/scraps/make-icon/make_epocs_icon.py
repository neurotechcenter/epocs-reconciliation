import matplotlib, pylab, numpy, time

#thickness = 10; height = 0.9;  offset =  0;   circle_edge = 'none'; start, stop = 100, 600; color = 'g'; fontsize = None
#thickness = 8;  height = 0.8;  offset =  0;   circle_edge = 'none'; start, stop = 150, 500; color = 'g'; fontsize = None
thickness = 10; height = 0.55;  offset = -0.4; circle_edge = 'g';    start, stop = 130, 520; color = 'g'; fontsize = 150; textcolor = 'g'; textoffset = ( 0, +0.4 ); fontname = 'Aharoni'; fontweight = 'normal'

def gzipfile( infilename='060221012_tp.txt' ):
	import gzip
	outfilename = infilename + '.gz'
	out = gzip.open( outfilename, 'wb' )
	for line in open( infilename, 'rt' ): out.write( line.strip() + '\n' )
	out.close()
	return outfilename

pylab.ion()
filename = '060221012_tp.txt.gz';  cut = [ 250, 255 ]
if filename.lower().endswith( '.gz' ): import gzip; opener = gzip.open
else: opener = open
traces = numpy.array( [ [ float( x ) for x in a.split() ] for a in opener( filename ) ], dtype=float )
traces = traces[ : : 5 ].T  # every fifth line of the file corresponds to a new trial in the same channel
traces = traces[ range( 0, cut[ 0 ] ) + range( cut[ 1 ], traces.shape[ 0 ] ), : ] # cut out some of the artifact (make it look more like a spike)
traces = traces[ start:stop, : ]
traces /= numpy.abs( traces ).max()
traces = traces * height + offset
t = numpy.expand_dims( numpy.linspace( -1, 1, traces.shape[ 0 ] ), 1 )
r = ( t ** 2 + traces ** 2 ) ** 0.5
traces[ r >= 1 - thickness / 500.0 ] = numpy.nan

pylab.clf()
pylab.gcf().canvas._tkcanvas.master.geometry( '1280x962+0+0' )
pylab.draw(); time.sleep( 0.2 )
pylab.plot( t, traces, color=color, hold=False, linewidth=thickness )
c = matplotlib.patches.Circle( ( 0, 0 ), 1, facecolor='w', edgecolor=circle_edge, linewidth=thickness )
pylab.gca().add_patch( c )
if fontsize:
	pylab.gca().text( textoffset[ 0 ], textoffset[ 1 ], 'epocs', horizontalalignment='center', verticalalignment='center', fontsize=fontsize, color=textcolor, fontweight=fontweight, fontname=fontname )
pylab.gca().set( xticks=[], yticks=[] )
pylab.axis( 'image' )
r = 1.03
pylab.axis( ( -r, r, -r, r ) )
pylab.gcf().patch.set_facecolor( 'r' )
pylab.axis( 'off' )

print 'now say save() now that the figure has had time to recognize what size it is supposed to be'

def save( filestem='epocs_icon' ):
	pylab.savefig( filestem + '.png', transparent=True, bbox_inches='tight', pad_inches=0 )
	pylab.savefig( filestem + '.svg', transparent=True, bbox_inches='tight', pad_inches=0 )
	#pylab.savefig( filestem + '.pdf', transparent=True, bbox_inches='tight', pad_inches=0 )
