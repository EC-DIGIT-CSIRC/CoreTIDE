from random import randrange
from datetime import datetime
import urllib.request
import sys
import ssl
from splunklib import client
import os
import git
from io import BytesIO
from typing import Literal


sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.logs import log


def splunk_timerange(time: str, skewing: float | int = 1, offset: int = 0) -> str:
    """
    Converts a Nd, Nh or Nm format into an splunk compatible earliest_at equivalent.
    Optionally supports skewing and offset

    Keyword arguments:
    time -- the original timeformat
    skewing -- [optional] splunk parameter to align with the skewing strategy (technique in
    splunk to evenly distribute scheduled search)
    offset -- [optional] added value to the result
    """
    skewing += 1  # So can multiply
    unit = time[-1]
    count = int(time[:-1])

    if unit == "m":
        count = count
    elif unit == "h":
        count = count * 60
    elif unit == "d":
        count = count * 1440
    else:
        raise Exception(
            "⚠️ [FATAL] Time Unit not supported by splunk earliest at converter (expects m, h or d)"
        )

    converted = offset + round(
        count * skewing
    )  # Implementation of time skewing and offset
    converted = f"-{converted}m@m"

    return converted


def cron_to_timeframe(
    frequency: str,
    mode: Literal["random", "current", "custom"] = "current",
    custom_time=None,
) -> str:

    unit = frequency[-1]
    count = int(frequency[:-1])
    min = hour = str()
    if (
        (unit == "m" and count > 59)
        or (unit == "h" and count > 23)
        or (unit == "d" and count > 30)
    ):
        # Non blocking error, normally validation should have catched it al
        log(
            "WARNING",
            "Time boundaries were bypassed, expected usage 1-59m , 1-23h or 1-30d.",
            "Proceeding, but note that behaviour is not guaranteed",
        )

    if mode == "random":
        min = str(randrange(60))
        hour = str(randrange(24))

    if mode == "current":
        now = datetime.now()
        min = now.strftime("%M")
        hour = now.strftime("%H")

    if mode == "custom":
        if not custom_time:
            raise Exception(
                "☢️ [FATAL] When selecting a custom time, you need to input a time in the correct format : HHhmm."
            )
        else:
            hour, min = custom_time.split("h")

    match unit:
        case "m":
            cron = f"*/{count} * * * *"
        case "h":
            cron = f"{min} */{count} * * *"
        case "d":
            cron = f"{min} {hour} */{count} * *"
        case _:
            raise Exception(
                "⚠️ [FATAL] Time Unit not supported by crontab converter (expects m, h or d)"
            )

    return cron


def request(url, message, **kwargs):
    method = message["method"].lower()
    data = message.get("body", "") if method == "post" else None
    headers = dict(message.get("headers", []))
    req = urllib.request.Request(url, data, headers)

    try:
        response = urllib.request.urlopen(req)

    except urllib.error.URLError as response:  # type: ignore
        # Disable SSL certificate validation and try again in case of URL error
        response = urllib.request.urlopen(req, context=ssl._create_unverified_context())

    except urllib.error.HTTPError as response:  # type: ignore
        pass  # Propagate HTTP errors via the returned response message

    return {
        "status": response.code,  # type: ignore
        "reason": response.msg,  # type: ignore
        "headers": dict(response.info()),  # type: ignore
        "body": BytesIO(response.read()),  # type: ignore
    }


def handler(proxy):
    proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)
    return request


def connect_splunk(
    host: str,
    port: str | int,
    token: str,
    app: str,
) -> client.Service:
    port = int(port)
    proxy_data = os.getenv("https_proxy") or os.getenv("http_proxy")
    if proxy_data:
        service = client.connect(
            handler=handler(proxy_data),
            host=host,
            port=port,
            token=token,
            autologin=True,
            app=app,
            sharing="app",
        )
    else:
        service = client.connect(
            host=host, port=port, token=token, autologin=True, app=app, sharing="app"
        )

    print("\n🔗 Successfully connected to Splunk ! ")

    return service


### CUSTOM FUNCTIONALITIES


def create_query(data: dict) -> str:
    """
    Automatically adds certain lines to the analyst defined SPL
    """

    uuid = data["uuid"]
    mdr_splunk = data["configurations"]["splunk"]
    status = mdr_splunk["status"]
    spl = mdr_splunk["query"].strip()

    macro = f'| eval MDR_UUID="{uuid}", MDR_status="{status}" \n|`soc_macro_auto_mdr_mapping(MDR_UUID)`'

    query = spl + "\n" + macro
    return query
