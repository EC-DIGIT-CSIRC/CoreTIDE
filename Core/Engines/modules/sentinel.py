from datetime import timedelta
from azure.mgmt.securityinsight import SecurityInsights
from azure.identity import ClientSecretCredential


def connect_to_sentinel(
    client_id: str, client_secret: str, tenant_id: str, subscription_id: str
) -> SecurityInsights:

    credentials = ClientSecretCredential(tenant_id, client_id, client_secret)

    client = SecurityInsights(credentials, subscription_id)

    return client


def iso_duration_timedelta(duration: str) -> timedelta:
    """
    Converts an simple duration into an ISO 8601 compliant time duration.
    See https://tc39.es/proposal-temporal/docs/duration.html for more information.
    """

    unit = duration[-1]
    count = int(duration[:-1])

    match unit:
        case "m":
            delta = timedelta(minutes=count)
        case "h":
            delta = timedelta(hours=count)
        case "d":
            delta = timedelta(days=count)
        case _:
            raise Exception(
                f"☢️ [FATAL] Duration {duration} is not in supported unit (m, h or d)"
            )

    return delta


def create_query(query: str, mdr_data: dict) -> str:
    """
    Modifies KQL Query to add customizable capabilities
    """

    uuid = mdr_data["uuid"]
    extend_uuid = f"| extend MDR_UUID = '{uuid}' "
    query += extend_uuid

    return query
