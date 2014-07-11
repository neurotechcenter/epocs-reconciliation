import os, sys, shutil

from distutils.core import setup
import py2exe

if not hasattr( sys, 'argv' ): sys.argv = [ 'make_exe' ]
if len( sys.argv ) < 2: sys.argv.append( 'py2exe' )

import matplotlib
import matplotlib.backends.backend_tkagg

options = {
	'py2exe': {
		    'includes' : [ 'matplotlib.backends.backend_tkagg' ],
		#'bundle_files' : 1,      # uncomment if attempting to make a single .exe
		  'compressed' : True,    # uncomment if attempting to make a single .exe
	},
}

data_files = [
	'epocs.ico',
	'ExampleData.pk',
	os.path.join( os.environ[ 'PYTHONHOME' ], 'tcl', 'tcl8.5', 'init.tcl' ),
]
data_files += matplotlib.get_py2exe_datafiles()

print "running py2exe..."

logfile = 'make_exe.log'
oldstderr, oldstdout = sys.stderr, sys.stdout
sys.stderr = sys.stdout = open( logfile, 'wt')
setup(
	options=options,
	zipfile=None, # uncomment if attempting to make a single .exe
	data_files=data_files,
	windows=[
		{
			        'script' : 'epocs.py',
			'icon_resources' : [ ( 1, 'epocs.ico' ) ],
		}
	],
)
sys.stderr, sys.stdout = oldstderr, oldstdout

dependencies = sorted( [ x.strip().split( ' ', 2 )[ -1 ] for x in open( logfile, 'rt' ).readlines() if x.startswith( ' ' ) and ' - ' in x ] )
dependencies_sys = [ x for x in dependencies if x.startswith( os.environ[ 'SYSTEMROOT' ] ) ]
dependencies = [ x for x in dependencies if x not in dependencies_sys ]

print "copying random extra dependencies that weren't included for some bizarre reason..."
print '\n'.join( dependencies )
print "\nbut omitting the following:"
print '\n'.join( dependencies_sys )

for x in dependencies:  shutil.copyfile( x, os.path.join( 'dist', os.path.split( x )[ 1 ] ) )
