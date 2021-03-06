import math

from marvin.helper import rule, getNow, itemLastUpdateOlderThen, getItemState, postUpdate, postUpdateIfChanged, \
    sendCommand
from core.triggers import CronTrigger, ItemCommandTrigger, ItemStateChangeTrigger

autoChangeInProgress = False


@rule("ventilation_control.py")
class FilterRuntimeRule:
    def __init__(self):
        self.triggers = [ItemStateChangeTrigger("Ventilation_Filter_Runtime")]

    def execute(self, module, input):
        laufzeit = getItemState("Ventilation_Filter_Runtime").doubleValue()

        weeks = int(math.floor(laufzeit / 168.0))
        days = int(math.floor((laufzeit - (weeks * 168.0)) / 24))

        active = []
        if weeks > 0:
            if weeks == 1:
                active.append(u"1 Woche")
            else:
                active.append(u"{} Wochen".format(weeks))

        if days > 0:
            if days == 1:
                active.append(u"1 Tag")
            else:
                active.append(u"{} Tage".format(days))

        msg = u", ".join(active)

        postUpdateIfChanged("Ventilation_Filter_Runtime_Message", msg)


@rule("ventilation_control.py")
class FilterStateMessageRule:
    def __init__(self):
        self.triggers = [
            ItemStateChangeTrigger("Ventilation_Error_Message"),
            ItemStateChangeTrigger("Ventilation_Filter_Error_I"),
            ItemStateChangeTrigger("Ventilation_Filter_Error_E")
        ]

    def execute(self, module, input):
        active = []

        Ventilation_Filter_Error_I_State = getItemState("Ventilation_Filter_Error_I").intValue()
        Ventilation_Filter_Error_E_State = getItemState("Ventilation_Filter_Error_E").intValue()
        if Ventilation_Filter_Error_I_State == 1 or Ventilation_Filter_Error_E_State == 1:
            value = u"Filter: "
            if Ventilation_Filter_Error_I_State == 1: value = u"{}I".format(value)
            if Ventilation_Filter_Error_I_State == 1 and Ventilation_Filter_Error_E_State == 1: value = u"{} & ".format(value)
            if Ventilation_Filter_Error_E_State == 1: value = u"{}E".format(value)
            active.append(value)

        if getItemState("Ventilation_Error_Message").toString() != "Ok":
            active.append(u"Error: {}".format( getItemState("Ventilation_Error_Message").toString() ))

        if len(active) == 0:
            active.append(u"Alles in Ordnung")

        msg = ", ".join(active)

        postUpdateIfChanged("Ventilation_State_Message", msg)


@rule("ventilation_control.py")
class FilterOutdoorTemperatureMessageRule:
    def __init__(self):
        self.triggers = [
            ItemStateChangeTrigger("Ventilation_Outdoor_Incoming_Temperature"),
            ItemStateChangeTrigger("Ventilation_Outdoor_Outgoing_Temperature")
        ]

    def execute(self, module, input):
        msg = u"→ {}°C, ← {}°C".format(getItemState("Ventilation_Outdoor_Incoming_Temperature").format("%.1f"),getItemState("Ventilation_Outdoor_Outgoing_Temperature").format("%.1f"))
        postUpdateIfChanged("Ventilation_Outdoor_Temperature_Message", msg)


@rule("ventilation_control.py")
class FilterIndoorTemperatureMessageRule:
    def __init__(self):
        self.triggers = [
            ItemStateChangeTrigger("Ventilation_Indoor_Incoming_Temperature"),
            ItemStateChangeTrigger("Ventilation_Indoor_Outgoing_Temperature")
        ]

    def execute(self, module, input):
        msg = u"→ {}°C, ← {}°C".format(getItemState("Ventilation_Indoor_Incoming_Temperature").format("%.1f"),getItemState("Ventilation_Indoor_Outgoing_Temperature").format("%.1f"))
        postUpdateIfChanged("Ventilation_Indoor_Temperature_Message", msg)


@rule("ventilation_control.py")
class FilterVentilationMessageRule:
    def __init__(self):
        self.triggers = [
            ItemStateChangeTrigger("Ventilation_Incoming"),
            ItemStateChangeTrigger("Ventilation_Outgoing")
        ]

    def execute(self, module, input):
        msg = u"→ {}%, ← {}%".format(getItemState("Ventilation_Incoming").toString(),getItemState("Ventilation_Outgoing").toString())
        postUpdateIfChanged("Ventilation_Fan_Message", msg)


@rule("ventilation_control.py")
class FilterManualActionRule:
    def __init__(self):
        self.triggers = [ItemCommandTrigger("Ventilation_Fan_Level")]

    def execute(self, module, input):
        if autoChangeInProgress:
            global autoChangeInProgress
            autoChangeInProgress = False
        else:
            postUpdate("Ventilation_Auto_Mode", 0)


@rule("ventilation_control.py")
class FilterFanLevelRule:
    def __init__(self):
        self.triggers = [
            ItemStateChangeTrigger("Ventilation_Auto_Mode"),
            ItemStateChangeTrigger("State_Presence"),
            CronTrigger("0 */1 * * * ?"),
        ]

    def execute(self, module, input):
        if getItemState("Ventilation_Auto_Mode").intValue() != 1:
            return

        currentLevel = getItemState("Ventilation_Fan_Level").intValue()

        raumTemperatur = getItemState("Temperature_FF_Livingroom").doubleValue()
        zielTemperatur = getItemState("Ventilation_Comfort_Temperature").doubleValue
        
        presenceSate = getItemState("State_Presence").intValue()
        
        isTooWarm = raumTemperatur >= zielTemperatur
        coolingPossible = getItemState("Temperature_Garden").doubleValue() < raumTemperatur

        # Sleep
        if presenceSate == 2:
            reducedLevel = 2    # Level 1
            defaultLevel = 2    # Level 1
            coolingLevel = 2    # Level 1
        # Away since 30 minutes
        elif presenceSate == 0 and itemLastUpdateOlderThen("State_Presence", getNow().minusMinutes(60)):
            reducedLevel = 1    # Level A
            defaultLevel = 2    # Level 1
            coolingLevel = 3    # Level 2
        else:
            reducedLevel = 2    # Level 1
            defaultLevel = 3    # Level 2
            coolingLevel = 3    # Level 2
            
        # reducedLevel if it is too warm inside and also outside
        # coolingLevel if it is too warm inside but outside colder then inside
        newLevel = (coolingLevel if coolingPossible else reducedLevel) if isTooWarm else defaultLevel

        if newLevel != currentLevel:
            # Wenn der aktuelle Level Stufe 'A' (also 1) ist, sollte vor einem erneuten umschalten gewartet werden damit ein
            # hin und herschalten vermieden wird. z.B. bei kurzzeitigen Temperaturschwankungen
            if currentLevel == 1:
                waitBeforeChange = 15
            else:
                # must be > 1. Otherwise cangedSince dows not work propperly
                waitBeforeChange = 2

            if itemLastUpdateOlderThen("Ventilation_Fan_Level", getNow().minusMinutes(waitBeforeChange)):
                global autoChangeInProgress
                autoChangeInProgress = True

                sendCommand("Ventilation_Fan_Level", newLevel)
