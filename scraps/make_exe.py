import os, sys, shutil


EPOCS = os.path.realpath( '..' )
PYTHON = os.environ[ 'PYTHONHOME' ]

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

data_files = matplotlib.get_py2exe_datafiles()
data_files.append( os.path.join( PYTHON, 'tcl', 'tcl8.5', 'init.tcl' ) )
icon = os.path.join( EPOCS, 'app', 'gui', 'epocs.ico' )
data_files.append( icon )

print "copying files..."

logfile = 'make_exe.log'
oldstderr, oldstdout = sys.stderr, sys.stdout
sys.stderr = sys.stdout = open( logfile, 'wt')
setup(
	options=options,
	#zipfile=None, # uncomment if attempting to make a single .exe
	data_files=data_files,
	windows=[
		{
			        'script' : os.path.join( EPOCS, 'app', 'gui', 'epocs.py' ),
			'icon_resources' : [ ( 1, icon ) ],
		}
	],
)
sys.stderr, sys.stdout = oldstderr, oldstdout

dependencies = sorted( [ x.strip().split( ' ', 2 )[ -1 ] for x in open( logfile, 'rt' ).readlines() if x.startswith( ' ' ) and ' - ' in x ] )
dependencies_sys = [ x for x in dependencies if x.startswith( os.environ[ 'SYSTEMROOT' ] ) ]
dependencies = [ x for x in dependencies if x not in dependencies_sys ]

print '\n'.join( dependencies )
print '***********************************'
print '\n'.join( dependencies_sys )

print "copying random extra dependencies that weren't included for some bizarre reason..."
for x in dependencies:  shutil.copyfile( x, os.path.join( 'dist', os.path.split( x )[ 1 ] ) )
