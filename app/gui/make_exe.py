import os, sys, shutil

from distutils.core import setup
import py2exe

if not hasattr( sys, 'argv' ): sys.argv = [ 'make_exe' ]
if len( sys.argv ) < 2: sys.argv.append( 'py2exe' )

import matplotlib
import matplotlib.backends.backend_tkagg

options = {
	'py2exe': {
		    'excludes' : [ 'scipy', 'BCPy2000.WavTools' ],
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

import zipfile
zinname = os.path.join( 'dist', 'library.zip' )
zoutname = os.path.join( 'dist', 'library2.zip' )
zin = zipfile.ZipFile( zinname, 'r' )
zout = zipfile.ZipFile( zoutname, 'w' )
for item in zin.infolist():
	arcname = item.filename
	buffer = zin.read( arcname )
	if 'SigTools/__init__.py' in arcname:
		print 'replacing ', arcname, 'in', zinname
		arcname = arcname.rstrip( 'c' )
		buffer = ''
	zout.writestr( arcname, buffer )
zout.close()
zin.close()
shutil.move( zoutname, zinname )


dependencies = sorted( [ x.strip().split( ' ', 2 )[ -1 ] for x in open( logfile, 'rt' ).readlines() if x.startswith( ' ' ) and ' - ' in x ] )
dependencies_sys = [ x for x in dependencies if x.startswith( os.environ[ 'SYSTEMROOT' ] ) ]
dependencies = [ x for x in dependencies if x not in dependencies_sys ]

print "copying random extra dependencies that weren't included for some stupid reason..."
print '\n'.join( dependencies )
print "\n...but omitting the following:"
print '\n'.join( dependencies_sys )
print

for x in dependencies:  shutil.copyfile( x, os.path.join( 'dist', os.path.split( x )[ 1 ] ) )
