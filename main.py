import logging
import shelve
from time import sleep

from pyecobee import *


log_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
root_logger = logging.getLogger()

file_handler = logging.FileHandler("ecobee_antifreeze.log")
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(log_formatter)
root_logger.addHandler(consoleHandler)

thermostat_name = "Home"

thermostat_selection = Selection(
    selection_type=SelectionType.REGISTERED.value,
    selection_match="",
    include_settings=True,
)


default_fan_min_on_time = 30


def persist_to_shelf(file_name, ecobee_service):
    pyecobee_db = shelve.open(file_name, protocol=2)
    pyecobee_db[ecobee_service.thermostat_name] = ecobee_service
    pyecobee_db.close()


def refresh_tokens(ecobee_service):
    token_response = ecobee_service.refresh_tokens()
    logging.warning('TokenResponse returned from ecobee_service.refresh_tokens():\n{0}'.format(
        token_response.pretty_format()))

    persist_to_shelf('pyecobee_db', ecobee_service)


def request_tokens(ecobee_service):
    token_response = ecobee_service.request_tokens()
    logging.warning('TokenResponse returned from ecobee_service.request_tokens():\n{0}'.format(
        token_response.pretty_format()))

    persist_to_shelf('pyecobee_db', ecobee_service)


def authorize(ecobee_service):
    authorize_response = ecobee_service.authorize()
    logging.warning('AutorizeResponse returned from ecobee_service.authorize():\n{0}'.format(
        authorize_response.pretty_format()))

    persist_to_shelf('pyecobee_db', ecobee_service)

    logging.warning('Please goto ecobee.com, login to the web portal and click on the settings tab. Ensure the My '
                    'Apps widget is enabled. If it is not click on the My Apps option in the menu on the left. In the '
                    'My Apps widget paste "{0}" and in the textbox labelled "Enter your 4 digit pin to '
                    'install your third party app" and then click "Install App". The next screen will display any '
                    'permissions the app requires and will ask you to click "Authorize" to add the application.\n\n'
                    'After completing this step please hit "Enter" to continue.'.format(authorize_response.ecobee_pin))
    input()


def update_thermostat(hvac_mode, fan_min_on_time):
    try:
        update_thermostat_response = ecobee_service.update_thermostats(
            selection=thermostat_selection,
            thermostat=Thermostat(
                identifier=thermostat_name,
                settings=Settings(hvac_mode=hvac_mode, fan_min_on_time=fan_min_on_time)
            ),
        )
        if update_thermostat_response.status.code != 0:
            logging.error("Failed to update thermostat: %s", update_thermostat_response.pretty_format())

    except EcobeeApiException as e:
        if e.status_code == 14:
            refresh_tokens(ecobee_service)


def cool():
    update_thermostat("cool", default_fan_min_on_time)


def thaw():
    update_thermostat("off", 60)


def get_current_settings():
    try:
        res = ecobee_service.request_thermostats(thermostat_selection)
        hvac_mode = res.thermostat_list[0].settings.hvac_mode
        current_hvac_mode = res.thermostat_list[0].settings.hvac_mode
        current_fan_min_on_time = res.thermostat_list[0].settings.fan_min_on_time
        logging.warning(
            "Current thermostat config - hvacMode=%s, fanMinOnTime=%s",
            current_hvac_mode,
            current_fan_min_on_time
        )
    except EcobeeApiException as e:
        if e.status_code == 14:
            refresh_tokens(ecobee_service)


def main_loop(is_cooling):
    logging.warning("Main loop, is_cooling=%s", is_cooling)
    if is_cooling:
        logging.warning("in cooling mode, starting thaw cycle")
        thaw()
        get_current_settings()
        sleep(600)
        return main_loop(is_cooling=False)

    logging.warning("in thaw mode, starting cooling cycle")
    cool()
    get_current_settings()
    sleep(3000)
    return main_loop(is_cooling=True)


if __name__ == "__main__":
    try:
        pyecobee_db = shelve.open("pyecobee_db", protocol=2)
        ecobee_service = pyecobee_db[thermostat_name]
    except KeyError:
        application_key = input("Please enter the API key of your ecobee App: ")
        ecobee_service = EcobeeService(thermostat_name=thermostat_name, application_key=application_key)
    finally:
        pyecobee_db.close()

    if ecobee_service.authorization_token is None:
        authorize(ecobee_service)

    if ecobee_service.access_token is None:
        request_tokens(ecobee_service)

    try:
        # Start in thaw mode
        main_loop(is_cooling=False)
    except KeyboardInterrupt:
        exit(0)


