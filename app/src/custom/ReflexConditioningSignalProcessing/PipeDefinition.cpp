////////////////////////////////////////////////////////////////////////////////
// $Id: $
// Authors:
// Description: Pipe definition for the ReflexConditioningSignalProcessing module.
//
//
// $BEGIN_BCI2000_LICENSE$
//
// This file is part of BCI2000, a platform for real-time bio-signal research.
// [ Copyright (C) 2000-2012: BCI2000 team and many external contributors ]
//
// BCI2000 is free software: you can redistribute it and/or modify it under the
// terms of the GNU General Public License as published by the Free Software
// Foundation, either version 3 of the License, or (at your option) any later
// version.
//
// BCI2000 is distributed in the hope that it will be useful, but
//                         WITHOUT ANY WARRANTY
// - without even the implied warranty of MERCHANTABILITY or FITNESS FOR
// A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License along with
// this program.  If not, see <http://www.gnu.org/licenses/>.
//
// $END_BCI2000_LICENSE$
////////////////////////////////////////////////////////////////////////////////
#include "PCHIncludes.h"
#pragma hdrstop


// This file defines which filters will be used, and the sequence in which they are
// applied. Each Filter() entry consists of the name of a filter and a location token:
// the BCI2000 framework will then determine the order of the filters by string-sorting
// these location tokens.  By convention:
//   - filters locations for SignalSource modules begin with "1."
//   - filters locations for SignalProcessing modules begin with "2."
//   - filters locations Application modules begin with "3."
//
// Locations defined here using the Filter() macro override the defaults set by
// RegisterFilter() in the individual filters' implementation files.


#include "IIRBandpass.h"
Filter( IIRBandpass, 2.A );

#include "BackgroundTriggerFilter.h"
Filter( BackgroundTriggerFilter, 2.B );

#include "NIDAQFilter.h"
Filter( NIDAQFilter, 2.C );

#include "TrapFilter.h"
Filter( TrapFilter, 2.D );

#include "RangeIntegrator.h"
Filter( RangeIntegrator, 2.E );

#include "SharedMemoryOutputConnector.h"
Filter( SharedMemoryOutputConnector, 2.F );

