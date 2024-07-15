import git
import sys

from cbc_sdk.enterprise_edr import Report, IOC_V2, Watchlist
from cbc_sdk.rest_api import CBCloudAPI

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.framework import techniques_resolver
from Engines.modules.logs import log
from Engines.modules.debug import DebugEnvironment
from Engines.modules.tide import DataTide
from Engines.modules.plugins import DeployMDR
from Engines.modules.carbon_black_cloud import CarbonBlackCloudEngineInit


class CarbonBlackCloudDeploy(CarbonBlackCloudEngineInit, DeployMDR):

    def deploy_mdr(self, data):
        """
        Deployment routine, connecting to the platform and combining base and custom configurations
        """

        # Logic to overwrite target organizations if it is specified on the MDR
        custom_orgs = data["configurations"][self.DEPLOYER_IDENTIFIER].get(
            "organization"
        )
        if custom_orgs:
            deploy_orgs = custom_orgs
        else:
            deploy_orgs = self.ORGANIZATIONS

        for org in deploy_orgs:

            log(
                "ONGOING",
                f" Currently deploying MDR {data['name']} on organization",
                org,
            )

            org = org.strip()  # Remove any whitespace in case there are
            if org in self.CBC_SECRETS:
                org_secrets = self.CBC_SECRETS[org]
                org_key = org_secrets.get("org_key")
                token = org_secrets.get("token")
            else:
                log(
                    "FATAL",
                    "Target organization is not present in Secrets configuration",
                    org,
                    "Double check TOML config to ensure there is a org_key and token entry for this org",
                )
                raise (Exception)

            if not org_key:
                log(
                    "FATAL",
                    "Could not fetch Organization Key for organization",
                    org,
                    "Double check that there is a namespaced entry for this organization in the TOML config",
                )
                raise (Exception)

            if not token:
                log(
                    "FATAL",
                    "Could not fetch Organization Token for organization",
                    org,
                    "Double check that there is a namespaced entry for this organization in the TOML config",
                )
                raise (Exception)

            try:
                service = CBCloudAPI(
                    url=self.CBC_URL,
                    token=token,
                    org_key=org_key,
                    ssl_verify=self.SSL_ENABLED
                )
                log(
                    "SUCCESS",
                    "Successfully connected to Carbon Black Cloud on tenant",
                    org,
                )

            except:
                raise Exception(
                    f"⚠️ [FAILURE] Service could not be reached for organization {org}"
                )

            config_data = data["configurations"][self.DEPLOYER_IDENTIFIER]
            uuid = data["uuid"]
            name = data["name"]
            description = data["description"]
            status = config_data["status"]
            query = config_data["query"]

            # Check if case for removal or deployment, different procedures for each
            deployment = False
            removal = False

            if status in ["DISABLED", "REMOVED"]:
                removal = True
            else:
                deployment = True

            tags = list()
            tags.append(config_data["status"])

            if "detection_model" in data.keys():
                cdm = data["detection_model"]
                techniques = techniques_resolver(uuid)
                tags.append(cdm)
                tags.extend(techniques)

            if "tags" in config_data.keys():
                tags.extend(config_data["tags"])

            # Severity Mapping
            severity = self.SEVERITY_MAPPING[data["response"]["alert_severity"]]

            # TODO Introduce optional deployment mode where one report can group MDR together
            # To implement, the id of the CDM should be the unique ID of the report.
            # The report title should be updated against CDM name on each push.
            selected_watchlist = config_data.get("watchlist") or self.DEFAULT_WATCHLIST
            selected_report = config_data.get("report") or name
            watchlist_list = service.select(Watchlist)
            # Select watchlist and report objects
            report = None
            watchlist = None

            if watchlist_list:
                for w in watchlist_list:
                    if w.name == selected_watchlist:
                        watchlist = w

                if watchlist:
                    for r in watchlist.reports:
                        if r.title == selected_report:
                            report = r
                else:
                    raise Exception(
                        "⚠️ [FATAL] The CBC Deployer cannot create a detection in a non"
                        f"existent Watchlist : {selected_watchlist}. Make sure to create"
                        "one on the console before retriggering the deployment"
                    )

            ioc = IOC_V2.create_query(service, uuid, query)

            # If report already exists, update
            if report:

                # When no reports are selected, we stick to one MDR == one report
                if selected_report == name:
                    if deployment:
                        report.remove_iocs_by_id(str(uuid))
                        report.append_iocs([ioc])

                        if severity != report.severity:
                            report.update(
                                description=description, tags=tags, severity=severity
                            )
                            log(
                                "INFO",
                                "Upgraded severity for this report to allign with MDR",
                                str(severity),
                            )
                        else:
                            report.update(description=description, tags=tags)
                        log("SUCCESS", "Rolled out IOC to report", selected_report)

                    elif removal:
                        report.delete()
                        log(
                            "WARNING",
                            "The report was deleted alongside the rule",
                            selected_report,
                        )

                # When a report is specified, we non destructively extend its data
                else:
                    if deployment:
                        report.remove_iocs_by_id(uuid)
                        report.append_iocs([ioc])

                        # Add only new relevant tags to not block other MDR pushing to the same report
                        tags.extend(t for t in report.tags if t not in tags)

                        # Check for severity, if the MDR is higher than it, we update it
                        if severity > report.severity:
                            report.update(
                                description=description, tags=tags, severity=severity
                            )
                            log(
                                "INFO",
                                "Upgraded severity for this report to allign with MDR",
                                str(severity),
                            )
                        else:
                            report.update(description=description, tags=tags)
                        log("SUCCESS", "Deployed IOC to report", selected_report)

                    elif removal:
                        if len(report.iocs_) > 1:
                            report.remove_iocs_by_id(uuid)
                            report.update()
                            log("SUCCESS", f"Deleted IOC from report", selected_report)

                        else:
                            report.delete()
                            log(
                                "WARNING",
                                "The specified report was automatically"
                                "deleted as they were no other rule",
                                selected_report,
                            )

            # If report does not exist, create a new one and attach the IOC
            else:
                if deployment:
                    report_builder = Report.create(
                        service, selected_report, description, severity
                    )
                    report_builder.add_ioc(ioc)
                    for tag in tags:
                        report_builder.add_tag(tag)
                    report = report_builder.build()
                    report.save_watchlist()
                    watchlist.add_reports([report])  # type: ignore
                    log("SUCCESS", "Created report and deployed IOC", selected_report)

                elif removal:
                    log(
                        "SKIP",
                        f"No report to delete, already removed from system",
                        selected_report,
                    )

        return True

    def deploy(self, deployment: list[str]):

        if not deployment:
            raise Exception("DEPLOYMENT NOT FOUND")

        # Start deployment routine
        for mdr in deployment:
            mdr_data = DataTide.Models.mdr[mdr]

            # Check if modified MDR contains a platform entry (by safety, but should not happen since orchestrator will filter for the platform)
            if self.DEPLOYER_IDENTIFIER in mdr_data["configurations"].keys():
                self.deploy_mdr(mdr_data)
            else:
                log(
                    "SKIP",
                    f"🛑 Skipping as does not contain a CBC rule",
                    mdr_data.get("name"),
                )


def declare():
    return CarbonBlackCloudDeploy()

if __name__ == "__main__" and DebugEnvironment.ENABLED:
    CarbonBlackCloudDeploy().deploy(DebugEnvironment.MDR_DEPLOYMENT_TEST_UUIDS)