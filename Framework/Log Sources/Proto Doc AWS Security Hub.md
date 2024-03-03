
# aws:securityhub
`Status : PRODUCTION`

`System : Splunk`

### References
- https://docs.aws.amazon.com/securityhub/latest/userguide/what-is-securityhub.html
- https://docs.aws.amazon.com/securityhub/latest/userguide/what-is-securityhub.html

## Description
>AWS Security hub is a CSPM which will raise alerts for non compliant infrastructure setups.

### Observations
>Example observations, for example to describe ongoing issues or expected future developments


### Query
    `aws_securityhub_logs` ```all aws security hub logs```


---
## Mappings
### Datasources
| Name          | Description                                                                                                                                                                                                                          |
|:--------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Cloud Service | Infrastructure, platforms, or software that are hosted on-premise or by third-party providers, made available to users through network connections and/or APIs(Citation: Amazon AWS)(Citation: Azure Products)                       |
| Cloud Storage | Data object storage infrastructure hosted on-premise or by third-party providers, made available to users through network connections and/or APIs(Citation: Amazon S3)(Citation: Azure Blob Storage)(Citation: Google Cloud Storage) |

### Targets
| Name                   | Description   |
|:-----------------------|:--------------|
| Cloud Portal           | Placeholder   |
| Cloud Storage Accounts | Placeholder   |
---

## Fields
| Name        | Type    | Description                                 | Sample                                                        | TERM            | Parsing    | Retrieved   | CIM   | Extraction                                                                             |
|:------------|:--------|:--------------------------------------------|:--------------------------------------------------------------|:----------------|:-----------|:------------|:------|:---------------------------------------------------------------------------------------|
| app         | string  | The application involved in the event       | win:app:trendmicro                                            | TERM(eventid=*) | calculated | True        | *     | N/A                                                                                    |
| id          | string  | The unique identifier of the message        | win:app:trendmicro                                            | N/A             | N/A        | True        | N/A   | detail.findings{}.ProductFields.aws/securityhub/FindingId                              |
| severity    | string  | The severity of a message.                  | HIGH                                                          | N/A             | N/A        | True        | N/A   | EVAL-severity = lower('detail.findings{}.Severity.Label')                              |
| severity_id | numeric | A numeric severity indicator for a message. | 89                                                            | N/A             | N/A        | True        | N/A   | FIELDALIAS-detail.findings.Severity.Normalized = detail.findings{}.Severity.Normalized |
| subject     | string  | The message subject.                        | 1.16 Ensure IAM policies are attached only to groups or roles | N/A             | N/A        | True        | N/A   | FIELDALIAS-detail.findings.Title = detail.findings{}.Title                             |
| body        | string  | The body of a message.                      | raw                                                           | N/A             | N/A        | True        | N/A   | EVAL-body = spath(_raw, "detail.findings{}")                                           |
| type        | string  | The message type.                           | alert                                                         | N/A             | N/A        | True        | N/A   | EVAL-type = "alert"                                                                    |

### Log sample
```
{ [-]
  account: 698751137412
  detail: { [-]
    findings: [ [-]
      { [-]
        AwsAccountId: 698751137412
        Compliance: { [-]
          Status: FAILED
        }
        CreatedAt: 2020-09-09T12:42:20.028Z
        Description: By default, IAM users, groups, and roles h
        FirstObservedAt: 2020-09-09T12:42:20.028Z
        GeneratorId: arn:aws:securityhub:::ruleset/cis-aws-foun
        Id: arn:aws:securityhub:eu-west-1:698751137412:subscrip
        LastObservedAt: 2020-09-23T05:10:34.610Z
        ProductArn: arn:aws:securityhub:eu-west-1::product/aws/
        ProductFields: { [-]
          RecommendationUrl: https://docs.aws.amazon.com/consol
          RelatedAWSResources:0/name: securityhub-iam-user-no-p
          RelatedAWSResources:0/type: AWS::Config::ConfigRule
          RuleId: 1.16
          StandardsControlArn: arn:aws:securityhub:eu-west-1:69
          StandardsGuideArn: arn:aws:securityhub:::ruleset/cisStandardsGuideSubscriptionArn: arn:aws:securityhub:eu
          aws/securityhub/CompanyName: AWS
          aws/securityhub/FindingId: arn:aws:securityhub:eu-wes
          aws/securityhub/ProductName: Security Hub
        }
        RecordState: ACTIVE
        Remediation: { [-]
          Recommendation: { [-]
            Text: For directions on how to fix this issue, plea
            Url: https://docs.aws.amazon.com/console/securityhu
          }
        }
        Resources: [ [-]
          { [-]
            Details: { [-]
              AwsIamUser: { [-]
                AttachedManagedPolicies: [ [-]
                  { [-]
                    PolicyArn: arn:aws:iam::aws:policy/AWSCloud
                    PolicyName: AWSCloudTrailReadOnlyAccess
                  }
                ]
                CreateDate: 2020-09-09T12:33:00.000Z
                Path: /
                UserId: AIDA2FMGQG2CEJZ4WZSWW
                UserName: buissni
              }
            }
            Id: arn:aws:iam::698751137412:user/buissni
            Partition: aws
            Region: eu-west-1
            Type: AwsIamUser
          }
        ]
        SchemaVersion: 2018-10-08
        Severity: { [-]
          Label: LOW
          Normalized: 39
          Original: LOW
          Product: 39
        }
        Title: 1.16 Ensure IAM policies are attached only to gr
        Types: [ [-]
        Software and Configuration Checks/Industry and Regula
        ]
        UpdatedAt: 2020-09-23T05:10:32.552Z
        Workflow: { [-]
          Status: NEW
        }
        WorkflowState: NEW
      }
    ]
  }
  detail-type: Security Hub Findings - Imported
  id: 8cda4c58-5d39-1b72-35c7-302ae3a8909b
  region: eu-west-1
  resources: [ [-]
    arn:aws:securityhub:eu-west-1::product/aws/securityhub/arn:
  ]
  source: aws.securityhub
  time: 2020-09-23T05:10:39Z
  version: 0
}
```

`Version : 3 | Creation Date : 2022-03-02 | Last Modification : 2022-04-11 | Author : amine.besson@ext.ec.europa.eu`

