<table align="center"><tr><td align="center" width="9999">
<img src="coretide-logo.png" align="center" width="150" alt="Project icon">

# The first DetectionOps open platform

_Threat Informed Detection Modelling and Engineering as-Code_

Powering DIGIT S2 CATCH Detection Engineering Operations,
CoreTIDE is planned to go open source for the benefit of the European and beyond SOC community.

</td></tr></table>

**🎤 Talks**

- [Lightning Talk] Hack.lu 2023 : [TIDeMEC(CoreTIDE) : A Detection Engineering Platform Homegrown At The EC](https://www.youtube.com/watch?v=lng-87nRTGQ)
- [Slides] FIRST Technical Colloquium Amsterdam 2024 : [CoreTIDE: the First Project of the OpenTIDE Family](https://www.first.org/resources/papers/amsterdam24/Benson-Housmann-Seguy-CoreTIDE-FIRST-TC-Amsterdam-2024.pdf) 
- [Paper] [The OpenTIDE Whitepaper](https://code.europa.eu/groups/ec-digit-s2/opentide/-/wikis/uploads/e66f0f311d758449b350ff4f96105898/OpenTIDE_White_Paper.pdf) 

CoreTIDE is a platform that has been built for the better part of the past 2 years at the EC, and builds on top of years of astute observations of what goes wrong in the detection engineering field. It is an opinionated end-to-end platform, data model, framework and solution built on top of DevOps and as-code principles, with an emphasis on traceability, consistency, safety and automation. The data model of TIDeMEC scales from the input of a threat intelligence signal to the deployment of a detection rule whilst maintaining programmatic relations between actors, threat, detection objectives, and rules.

### Usage

**🚧Documentation Under Construction🚧**

CoreTIDE contains all the automation engines and configurations powering OpenTIDE's DetectionOps workflows. The codebase follows an injection architecture, where the Pipelines and Engines are integrated within the pipeline execution for an OpenTIDE Instance, another project must be created following by cloning the [StartTIDE](https://code.europa.eu/ec-digit-s2/opentide/starttide) layout into another repository of your choice. Out of the box, granted network access, your OpenTIDE instance will fetch this repository dynamically on every pipeline run, including the larger part of the CI Pipeline definitions.

You may also choose to use CoreTIDE locally, and thus beneficiate from a custom development environment, or to respect airgaps. We recommend you to use mirroring, or configure/perform regular pulls from this repository to fetch the latest fixes and features. See [gitlab-ci.yml](https://code.europa.eu/ec-digit-s2/opentide/starttide/-/blob/tide/.gitlab-ci.yml?ref_type=heads) in [StartTIDE](https://code.europa.eu/ec-digit-s2/opentide/starttide) to get a view of the different requirements to run your CoreTIDE Instance.

Configurations are a key part of the CoreTIDE system, and you may override any setting from your OpenTIDE Instance, including the internal settings. 
> NEVER override a setting by modifying your local CoreTIDE instance if you choose to have a local one, since it may clash with future updates and result in merge conflicts when trying to update the repository.

> The system performs a deep merge between Core (this repo) and Tide (client repo) namespaces to resolve a final configuration, always giving priority to the client namespace. Refer to the Configurations file content to discover what can be configured, and what environment variable are expected.

Certain parts of the configurations may receive environment variables, which will be dynamically inserted, this is especially the case for deployers. You may change those variables (prefixed clearly by a dollar sign `$`), as they will try to resolve dynamically from the environment. 

## License
This project is released under [EUPL version 1.2](https://eupl.eu/)

