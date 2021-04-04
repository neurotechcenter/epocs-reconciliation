// D188.h

#include "D188API.h"
#include "windows.h"
#include "winbase.h"

#pragma once

namespace D188library
{
	class D188Functions
	{
		private :
			HMODULE libD188API; //API Module
			//DS8 Functional Variables
			DGD188_Initialise procInitialise;
			DGD188_Update procUpdate;
			DGD188_Close procClose;		
			int apiRef;
			int retAPIError;
			int retError;
			int cbState;
			int devIdx;
			PD188 CurrentState;
			PD188 NewState;
			byte * pbMem;
			int soMem;
			int cbMem;
			int MODE,CHANNEL,INDICATOR,DELAY;
			int nD188;
		public :
			int ErrorCode; //Error codes (will have a seperate header)
			D188Functions(); 
			~D188Functions();
			//Load Library
			bool loadD188APILibrary();
			//Initialize CurrentState of DS8
			int SetState();
			//Enable/Diable the Output
			void SetChannel(int channel);
			int GetState();
			void CloseD188();

	};
}