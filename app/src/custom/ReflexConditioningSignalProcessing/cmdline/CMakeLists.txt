ADD_DEFINITIONS( -DWORKAROUND4530 ) # TODO: remove when 4530 bug is finally fixed
BCI2000_ADD_CMDLINE_FILTER( BackgroundTriggerFilter FROM .. EXTRA_HEADERS ../Workaround4530.h ) # TODO: remove EXTRA_HEADERS when 4530 bug is finally fixed
BCI2000_ADD_CMDLINE_FILTER( RangeIntegrator FROM ..         EXTRA_HEADERS ../Workaround4530.h ) # TODO: remove EXTRA_HEADERS when 4530 bug is finally fixed
BCI2000_ADD_CMDLINE_FILTER( TrapFilter FROM ..              EXTRA_HEADERS ../Workaround4530.h ) # TODO: remove EXTRA_HEADERS when 4530 bug is finally fixed
BCI2000_ADD_CMDLINE_FILTER(
	IIRBandpass FROM ../../../shared/modules/signalprocessing
	INCLUDING math
	EXTRA_SOURCES
		../../../shared/modules/signalprocessing/IIRFilterBase.cpp
	EXTRA_HEADERS
		../../../shared/modules/signalprocessing/IIRFilterBase.h
		../../../extlib/math/IIRFilter.h
		../Workaround4530.h  # TODO: remove when 4530 bug is finally fixed
)
