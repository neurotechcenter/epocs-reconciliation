#pragma once
#pragma warning(disable : 4200) 

/*
D188STATE_T Valid Fields values
D188_Mode
	0 = OFF
	1 = Controlled by commands from USB (PC API)
	2 = 1 to 8 control from rear panel connector (TTL)
	3 = 4 to 8 control from rear panel connector (TTL)

D188_Select
	0 = All channels off
	1 = Channel 1 selected
	2 = Channel 2 selected
	4 = Channel 3 selected
	8 = Channel 4 selected
	16 = Channel 5 selected
	32 = Channel 6 selected
	64 = Channel 7 selected
	128 = Channel 8 selected

	Only the first BIT set will enable a channel, subsequent set bits are ignored

D188_Indicator
	0 = Channel active indicators OFF
	!0 = Channel active indicators ON

D188_Delay
	n = number of 100us to delay between detecting a change on the rear panel socket and applying the change to the selected channels.
*/


#pragma pack(push, 1)
typedef struct {
	unsigned char D188_Mode;
	unsigned char D188_Select;
	unsigned char D188_Indicator;
	unsigned short D188_Delay;
} D188STATE_T;
#pragma pack(pop)

typedef struct {
	int D188_DeviceID;
	int D188_VersionID;
	int D188_Error;
	D188STATE_T D188_State;
} D188DEVICESTATE_T;

typedef struct {
	int DeviceCount;
} DEVICEHDR;

typedef struct {
	DEVICEHDR Header;
	D188DEVICESTATE_T State[];
} D188, *PD188;

typedef void(__stdcall *DGD188ClientInitialiseProc)(
	int Result,
	void * CallbackParam
	);

typedef void(__stdcall *DGD188ClientUpdateProc)(
	int Result,
	D188 * CurrentState,
	void * CallbackParam
	);

typedef void(__stdcall *DGD188ClientCloseProc)(
	int Result,
	void * CallbackParam
	);

typedef int(__stdcall *DGD188_Initialise)(
	int * Reference,
	int * InitError,
	DGD188ClientInitialiseProc CallbackProc,
	void * CallbaskParam
	);

typedef int(__stdcall *DGD188_Update)(
	int Reference,
	int * Error,
	PD188 NewState,
	int cbNewState,
	PD188 CurrentState,
	int * cbCurrentState,
	DGD188ClientUpdateProc CallbacProc,
	void * CallbackParam
	);

typedef int(__stdcall *DGD188_Close)(
	int * Reference,
	int * Error,
	DGD188ClientCloseProc CallbackProc,
	void * CallbackParam
	);



