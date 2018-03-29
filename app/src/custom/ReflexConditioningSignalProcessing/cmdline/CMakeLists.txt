BCI2000_ADD_CMDLINE_FILTER(
	IIRBandpass FROM ../../../shared/modules/signalprocessing
	INCLUDING math
	EXTRA_SOURCES
		../../../shared/modules/signalprocessing/IIRFilterBase.cpp
	EXTRA_HEADERS
		../../../shared/modules/signalprocessing/IIRFilterBase.h
		../../../extlib/math/IIRFilter.h
)
