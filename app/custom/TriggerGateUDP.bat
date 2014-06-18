ADD STATE RequestStimOn 1 0
SET PARAMETER TriggerExpression RequestStimOn

SET PARAMETER     Connector:ConnectorInput list   ConnectorInputFilter=  1 RequestStimOn    // list of state names or signal elements to allow, "*" for any, signal elements as in "Signal(1,0)"
SET PARAMETER     Connector:ConnectorInput string ConnectorInputAddress=   10.0.0.1:20320  // IP address/port to read from, e.g. localhost:20320
