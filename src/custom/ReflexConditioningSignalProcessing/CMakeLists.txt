###########################################################################
## $Id:  $
## Authors: Jeremy Hill <jezhill@gmail.com>
## Description: Build information for the ReflexConditioningSignalProcessing project
##              
##              
###########################################################################

IF( NOT WIN32 )
	RETURN()  # ever since NIDAQFilter became part of the signal-processing module, no hope of compiling on non-Windows
ENDIF( NOT WIN32 )

ADD_SUBDIRECTORY( cmdline )

# Set the executable name
SET( EXECUTABLE_NAME ReflexConditioningSignalProcessing )

# Set the project specific sources
SET( SRC_PROJECT
  PipeDefinition.cpp         # Edit this file to specify which filters are used in what order.
  BackgroundTriggerFilter.cpp
  TrapFilter.cpp
  RangeIntegrator.cpp
  ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/NIDAQ-Logging/NIDAQFilter.cpp
  ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/nidaq/NIDAQmx.imports.cpp
  SharedMemoryOutputConnector.cpp
)

SET( HDR_PROJECT
  BackgroundTriggerFilter.h
  TrapFilter.h
  RangeIntegrator.h
  ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/NIDAQ-Logging/NIDAQFilter.h
  ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/nidaq/NIDAQmx.imports.h
  ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/nidaq/NIDAQmx.h
  SharedMemoryOutputConnector.h
)

IF( NOT WIN32 ) # TODO: remove this section when BCI2000 can build on OSX again
  ADD_DEFINITIONS( -DWORKAROUND4530 ) 
  SET( HDR_PROJECT
    ${HDR_PROJECT}
    Workaround4530.h
  )
ENDIF( NOT WIN32 )


INCLUDE_DIRECTORIES( ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/nidaq )
IF( USE_DYNAMIC_IMPORTS )
ELSE()
  LINK_DIRECTORIES( ${BCI2000_SRC_DIR}/contrib/SignalSource/NIDAQ-MX/nidaq )
ENDIF()

LIST( APPEND SRC_PROJECT ${BCI2000_SRC_DIR}/shared/modules/CoreMain.cpp )
BCI2000_ADD_SIGNAL_PROCESSING_MODULE( 
  "${EXECUTABLE_NAME}" 
  "${SRC_PROJECT}" "${HDR_PROJECT}" 
)





