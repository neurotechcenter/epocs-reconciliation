import os, sys, shutil

from distutils.core import setup
import py2exe

if not hasattr( sys, 'argv' ): sys.argv = [ 'make_exe' ]
if len( sys.argv ) < 2: sys.argv.append( 'py2exe' )



import matplotlib
import matplotlib.backends.backend_tkagg
includes = [ 'matplotlib.backends.backend_tkagg' ]
excludes = [ 'scipy', 'BCPy2000.SigTools' ]

options = {
	'py2exe': {
		    'excludes' : excludes,
		    'includes' : includes,
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

# awkward kludge to include BCPy2000.SigTools.NumTools.py by hand but do not include the rest of SigTools
numtools_src = [ os.path.join( x, 'BCPy2000', 'SigTools', 'NumTools.py' ) for x in sys.path ]
numtools_src = [ x for x in numtools_src if os.path.isfile( x ) ][ 0 ]
shutil.copyfile( numtools_src, 'NumTools.py' ); import NumTools; includes.append( 'NumTools' ) 
# remember to delete ./NumTools.py and ./NumTools.pyc again afterwards

print "running py2exe..."
logfile = 'make_exe.log'
oldstderr, oldstdout = sys.stderr, sys.stdout
sys.stderr = sys.stdout = open( logfile, 'wt')
setup(
	options=options,
	#zipfile=None, # uncomment if attempting to make a single .exe (incompatible with the zipfile manipulations below however)
	data_files=data_files,
	windows=[
		{
			        'script' : 'epocs.py',
			'icon_resources' : [ ( 1, 'epocs.ico' ) ],
		}
	],
)
sys.stderr, sys.stdout = oldstderr, oldstdout
os.remove( 'NumTools.py' )
os.remove( 'NumTools.pyc' )

dependencies = sorted( [ x.strip().split( ' ', 2 )[ -1 ] for x in open( logfile, 'rt' ).readlines() if x.startswith( ' ' ) and ' - ' in x ] )
dependencies_sys = [ x for x in dependencies if x.startswith( os.environ[ 'SYSTEMROOT' ] ) ]
dependencies = [ x for x in dependencies if x not in dependencies_sys ]

print "copying random extra dependencies that weren't included for some stupid reason..."
print '\n'.join( dependencies )
print "\n...but omitting the following:"
print '\n'.join( dependencies_sys )
print

for x in dependencies:  shutil.copyfile( x, os.path.join( 'dist', os.path.split( x )[ 1 ] ) )
