import os
import git
import sys
import json
from typing import Literal
from splunklib import client, results
import traceback

import pandas as pd

sys.path.append(str(git.Repo(".", search_parent_directories=True).working_dir))

from Engines.modules.splunk import connect_splunk, create_query, SplunkEngineInit
from Engines.modules.plugins import ValidateQuery
from Engines.modules.logs import log
from Engines.modules.debug import DebugEnvironment
from Engines.modules.tide import DataTide

class SplunkValidateQuery(SplunkEngineInit, ValidateQuery):

    def check_query(self, mdr:dict, service:client.Service):
        
        query:str = mdr["configurations"][self.DEPLOYER_IDENTIFIER].get("query")
        if not query:
            os.environ["VALIDATION_ERROR_RAISED"] = "True"
            log("FATAL", "Missing query in MDR", f"{mdr.get('name')} ({mdr.get('uuid')})")
            return

        query = create_query(mdr)
        if not query.startswith("| "):
            query = "| search" + query
            log("INFO",
                "Adding implicit `| search` as could not find starting command")

        try:
            response = service.parse(query.strip(),
                                     enable_lookups=True,   
                                     output_mode='json',
                                     reload_macros=True)
            status = response["status"]
            
            if status == 19:
                parsing = response["body"].read()
                parsing = json.loads(parsing) #type: ignore
                log("DEBUG", "Parsed Body", parsing) 
                for message in parsing["messages"]:
                    log("FATAL",
                        f"The SPL query is invalid for : {mdr['name']} ({mdr['uuid']})",
                        message.get("text", ""),
                        "Review the error and ensure it can run on the Splunk Search console")
                os.environ["VALIDATION_ERROR_RAISED"] = "True"
            
            elif status == 200:
                parsing = response["body"].read()
                parsing = json.loads(parsing) #type: ignore
                log("SUCCESS", "The query is a valid SPL that can be parsed by Splunk")
            
            else:
                log("FATAL",
                "Unexpected Error Code",
                str(response))


        except Exception as e:
            log("FATAL",
                "An unknown error was found",
                repr(e))
            traceback.print_exc()
            raise 

    def validate(self, deployment: list[str]):
        if not deployment:
            raise Exception("DEPLOYMENT NOT FOUND")

        service = connect_splunk(
                host=self.SPLUNK_URL,
                port=self.SPLUNK_PORT,
                token=self.SPLUNK_TOKEN,
                app=self.SPLUNK_APP,
                allow_http_errors=True,
                ssl_enabled=self.SSL_ENABLED
            )
        # Start deployment routine
        for mdr in deployment:
            mdr_data:dict = DataTide.Models.mdr[mdr]

            # Check if modified MDR contains a platform entry (by safety, but should not happen since
            # the orchestrator will filter for the platform)
            if self.DEPLOYER_IDENTIFIER in mdr_data["configurations"].keys():
                # Connection routine, if not connected yet.
                log("ONGOING",
                    "Validating SPL Query",
                    f"{mdr_data['name']} ({mdr_data['uuid']}")
                self.check_query(mdr_data, service)
            else:
                log(
                    "SKIP",
                    f"🛑 Skipping {mdr_data.get('name')} as does not contain a Splunk configuration section",
                )

def declare():
    return SplunkValidateQuery()    

if __name__ == "__main__" and DebugEnvironment.ENABLED:
    SplunkValidateQuery().validate(DebugEnvironment.MDR_DEPLOYMENT_TEST_UUIDS)