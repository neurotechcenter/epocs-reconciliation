# add all the subdirectories that contain a CMakeLists.txt file
FILE( GLOB subdirs RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} * )
FOREACH( dir ${subdirs} )
	IF( EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${dir}/CMakeLists.txt )
		ADD_SUBDIRECTORY( ${dir} )
	ENDIF()
ENDFOREACH()

