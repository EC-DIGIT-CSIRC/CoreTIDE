########
# Managed Detection Rules Template
########


TEMPLATEv3 = '''{frontmatter}

{name}

{banner}

{tlp}

{techniques}

{uuid}

---

`{metadata}`

## 👁️‍🗨️ Description

> {description}

{cdm}


&nbsp;

## ⚠️ Response

{response}

&nbsp;

## 💽 Configurations

{configurations}

### 🔎 Queries

{queries}

### 🔗 References

{references}

&nbsp;


'''

TEMPLATEv2 = '''{frontmatter}

{title}

{uuid}

{status}

{priority}

{tlp}

{techniques}

---

## 💽 Description
> {description}
{falsepositives}

### 👣 Playbook

{playbook}

### ‍🚒 Alert Handling Team

{responders}

### 🛡️ Detection Model
{detectionmodel}

### ⚒️ Parameters

{scheduling}

{timeframe}

{throttling}

{threshold}

{logsources}

{fields}

---
## ⚗️ Detections 
{rules}

### 🔗 References

{references}

`{meta}`

'''