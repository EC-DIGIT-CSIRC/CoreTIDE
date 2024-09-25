class TideErrors(Exception):
    """
    Container for all custom OpenTIDE errors
    """
    class TideDeploymentErrors(Exception):
        """
        Represents all errors occuring during a deployment procedure 
        """
        ...

    class TenantConnectionError(Exception):
        """
        Raised when failed to establish a connection to the target tenant
        """
        ...

    class DetectionRulesOperationErrors(TideDeploymentErrors):
        """
        Represents all errors related to Detection Rules API operations 
        """

    class DetectionRuleCreationFailed(DetectionRulesOperationErrors): 
        """
        Raised when failed to create a detection rule in the target tenant
        """
        ...

    class DetectionRuleUpdateFailed(DetectionRulesOperationErrors):
        """
        Raised when failed to update a detection rule in the target tenant
        """
        ...

    class DetectionRuleDeletionFailed(DetectionRulesOperationErrors):
        """
        Raised when failed to delete a detection rule in the target tenant
        """
        ...