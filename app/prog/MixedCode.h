// MixedCode.h

#pragma once
class DS5LibWrapperPrivate;

class __declspec(dllexport) DS5LibWrapper
{
	private: DS5LibWrapperPrivate* _private;

	public: DS5LibWrapper();

	public: ~DS5LibWrapper();

	public: bool CheckDS5connected();

	public: void AutoZero();

	public: void ToggleOutput(bool OnOff);

	public: void Set5mA5V();

	public: void SetBackLight();

};

